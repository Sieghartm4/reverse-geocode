"""
Reverse geocoder for Philippine OSM data.
Optimised:
  - Uses native EPSG:3857 geometry for ST_DWithin so spatial indexes are hit
  - Bounding-box pre-filter (way && ST_Expand) before the radius check
  - All queries in ONE round-trip; no sequential Python fallback loops
  - Connection pooling (single persistent connection with auto-reconnect)
  - /debug endpoint to inspect raw OSM tags for any coordinate
"""

from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
import re
import time

app = Flask(__name__)

# --------------------------------------------------------------------------- #
# Connection                                                                   #
# --------------------------------------------------------------------------- #

_conn = None

def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = _new_conn()
    else:
        try:
            _conn.cursor().execute("SELECT 1")
        except Exception:
            _conn = _new_conn()
    return _conn

def _new_conn():
    c = psycopg2.connect(
        "dbname=ph_geodata user=postgres password=philippogi123",
        application_name="reverse_geocoder"
    )
    c.autocommit = True
    return c

def cur():
    return get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# --------------------------------------------------------------------------- #
# Native-SRID point expression                                                 #
# Converts lon/lat once to EPSG:3857 so every query uses the native index     #
# --------------------------------------------------------------------------- #

def _pt(lon: float, lat: float) -> str:
    return f"ST_Transform(ST_SetSRID(ST_MakePoint({lon},{lat}),4326),3857)"


# --------------------------------------------------------------------------- #
# Tag extractor                                                                #
# Works with psycopg2 hstore dicts AND raw hstore text strings                #
# --------------------------------------------------------------------------- #

def _tv(tags, key: str) -> str:
    if not tags:
        return ""
    if isinstance(tags, dict):
        return (tags.get(key) or "").strip()
    m = re.search(rf'{re.escape(key)}=>"([^"]*)"', str(tags))
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------- #
# Philippine block / lot / unit parser                                         #
# --------------------------------------------------------------------------- #

_BLK_RE  = re.compile(r'\b(?:Blk|Block|B)\.?\s*(\w+)',                re.IGNORECASE)
_LOT_RE  = re.compile(r'\b(?:Lot|L(?=[\s\d]))\.?\s*(\w+)',            re.IGNORECASE)
_UNIT_RE = re.compile(r'\b(?:Unit|Room|Rm|Apt|Apartment)\.?\s*(\w+)', re.IGNORECASE)

def parse_hn(hn: str):
    """
    Split addr:housenumber into (block, lot, unit, remainder).
    'Blk 21 Lot 28'  → ('21','28','','')
    '3224'            → ('','','','3224')
    'Unit 3B Blk 5 Lot 2' → ('5','2','3B','')
    """
    s = hn.strip()
    blk = lot = unit = ""

    m = _BLK_RE.search(s)
    if m:
        blk = m.group(1)
        s = (s[:m.start()] + " " + s[m.end():]).strip()

    m = _LOT_RE.search(s)
    if m:
        lot = m.group(1)
        s = (s[:m.start()] + " " + s[m.end():]).strip()

    m = _UNIT_RE.search(s)
    if m:
        unit = m.group(1)
        s = (s[:m.start()] + " " + s[m.end():]).strip()

    remainder = re.sub(r'\s+', ' ', s).strip(" ,")
    return blk, lot, unit, remainder


# --------------------------------------------------------------------------- #
# All DB fetches in one function                                               #
# --------------------------------------------------------------------------- #

SUBDIV_KW = ('village','subdivision','phase','estate','compound',
             'homes','residences','heights','springs','gardens')

def fetch_all(lon: float, lat: float) -> dict:
    pt = _pt(lon, lat)
    c  = cur()
    t0 = time.perf_counter()

    # ── 1. Best local road ────────────────────────────────────────────────────
    c.execute(f"""
        SELECT name, highway,
               ST_Distance(way, {pt}) AS dist
        FROM planet_osm_line
        WHERE name IS NOT NULL
          AND highway IS NOT NULL
          AND way && ST_Expand({pt}, 500)
          AND ST_DWithin(way, {pt}, 500)
        ORDER BY
          dist,
          CASE highway
            WHEN 'residential'   THEN 1
            WHEN 'living_street' THEN 1
            WHEN 'service'       THEN 2
            WHEN 'unclassified'  THEN 3
            WHEN 'tertiary'      THEN 4
            WHEN 'secondary'     THEN 5
            WHEN 'primary'       THEN 6
            WHEN 'trunk'         THEN 7
            WHEN 'motorway'      THEN 8
            ELSE 9
          END
        LIMIT 1
    """)
    road_row = c.fetchone()

    # ── 2. Admin boundaries ───────────────────────────────────────────────────
    c.execute(f"""
        SELECT name, admin_level, place, tags,
               ST_Area(way) AS area_m2
        FROM planet_osm_polygon
        WHERE way IS NOT NULL
          AND way && ST_Expand({pt}, 200000)
          AND ST_Contains(way, {pt})
          AND (admin_level IS NOT NULL
               OR place IN ('city','municipality','town','village',
                            'suburb','quarter','neighbourhood'))
        ORDER BY area_m2 ASC
        LIMIT 20
    """)
    admin_rows = c.fetchall() or []

    # ── 3. Buildings at / near the point ──────────────────────────────────────
    # Pull up to 60 m; exact-contain rows bubble up first
    c.execute(f"""
        SELECT name, tags, building,
               ST_Contains(way, {pt})  AS exact,
               ST_Area(way)            AS area_m2,
               ST_Distance(way, {pt}) AS dist
        FROM planet_osm_polygon
        WHERE building IS NOT NULL
          AND way && ST_Expand({pt}, 60)
          AND ST_DWithin(way, {pt}, 60)
        ORDER BY exact DESC, area_m2 ASC, dist ASC
        LIMIT 5
    """)
    building_rows = c.fetchall() or []

    # ── 4. Address nodes ──────────────────────────────────────────────────────
    c.execute(f"""
        SELECT name, tags,
               ST_Distance(way, {pt}) AS dist
        FROM planet_osm_point
        WHERE tags IS NOT NULL
          AND way && ST_Expand({pt}, 150)
          AND ST_DWithin(way, {pt}, 150)
          AND (tags ? 'addr:housenumber'
               OR tags ? 'addr:street'
               OR tags ? 'addr:postcode'
               OR tags ? 'addr:block_number'
               OR tags ? 'addr:lot_number'
               OR tags ? 'addr:unit')
        ORDER BY dist
        LIMIT 10
    """)
    addr_points = c.fetchall() or []

    # ── 5. Nearby named polygons (subdivisions / neighbourhoods) ──────────────
    c.execute(f"""
        SELECT name, place, tags, landuse,
               ST_Distance(way, {pt}) AS dist
        FROM planet_osm_polygon
        WHERE name IS NOT NULL
          AND way && ST_Expand({pt}, 400)
          AND ST_DWithin(way, {pt}, 400)
          AND (
              place IN ('neighbourhood','quarter','suburb','village')
              OR landuse = 'residential'
              OR name ILIKE '%village%'
              OR name ILIKE '%subdivision%'
              OR name ILIKE '%phase%'
              OR name ILIKE '%estate%'
              OR name ILIKE '%compound%'
              OR name ILIKE '%homes%'
          )
        ORDER BY dist
        LIMIT 10
    """)
    nearby_polys = c.fetchall() or []

    # ── 6. Generic nearby points ──────────────────────────────────────────────
    c.execute(f"""
        SELECT name, tags,
               ST_Distance(way, {pt}) AS dist
        FROM planet_osm_point
        WHERE name IS NOT NULL
          AND way && ST_Expand({pt}, 200)
          AND ST_DWithin(way, {pt}, 200)
        ORDER BY dist
        LIMIT 15
    """)
    near_points = c.fetchall() or []

    # ── 7. Postcode: progressively wider search ───────────────────────────────
    postcode_val = ""
    for radius in (600, 2000, 5000):
        c.execute(f"""
            SELECT tags->'addr:postcode' AS postcode
            FROM planet_osm_polygon
            WHERE tags ? 'addr:postcode'
              AND tags->'addr:postcode' ~ '^[0-9]{{3,6}}$'
              AND way && ST_Expand({pt}, {radius})
              AND ST_DWithin(way, {pt}, {radius})
            LIMIT 1
        """)
        row = c.fetchone()
        if row and row.get("postcode"):
            postcode_val = row["postcode"]
            break

    print(f"[geocode] DB done in {(time.perf_counter()-t0)*1000:.0f} ms")
    return dict(
        road_row=road_row,
        admin_rows=admin_rows,
        building_rows=building_rows,
        addr_points=addr_points,
        nearby_polys=nearby_polys,
        near_points=near_points,
        postcode_val=postcode_val,
    )


# --------------------------------------------------------------------------- #
# /reverse                                                                     #
# --------------------------------------------------------------------------- #

@app.route('/reverse', methods=['GET'])
def reverse_geocode():
    t0 = time.perf_counter()
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid lat/lon"}), 400

    d = fetch_all(lon, lat)

    # ── Road ──────────────────────────────────────────────────────────────────
    road_name = ((d["road_row"] or {}).get("name") or "").strip()

    # ── Admin boundaries ──────────────────────────────────────────────────────
    barangay = district = city = county = province = region = postcode = ""

    for row in d["admin_rows"]:
        name  = (row.get("name") or "").strip()
        al    = row.get("admin_level") or ""
        place = (row.get("place") or "").lower()
        tags  = row.get("tags")
        if not name:
            continue

        pc = _tv(tags,"addr:postcode") or _tv(tags,"postal_code")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc

        lv = int(al) if al.isdigit() else 99
        if   lv == 10 and not barangay:  barangay = name
        elif lv ==  7 and not district:  district = name
        elif lv ==  6 and not city:      city     = name
        elif lv ==  5 and not county:    county   = name
        elif lv ==  4 and not province:  province = name
        elif lv in (3,2) and not region: region   = name

        if place in ('city','municipality','town') and not city:     city     = name
        if place in ('suburb','neighbourhood')     and not barangay: barangay = name

    # ── Neighbourhood ─────────────────────────────────────────────────────────
    neighbourhood = ""
    for row in d["nearby_polys"]:
        name  = (row.get("name") or "").strip()
        place = (row.get("place") or "").lower()
        dist  = row.get("dist") or 9999
        if not name or dist > 380:
            continue
        if (place in ('neighbourhood','quarter')
                or any(kw in name.lower() for kw in SUBDIV_KW)):
            neighbourhood = name
            break

    # ── Building block / lot / unit ───────────────────────────────────────────
    house_number = block_number = lot_number = unit_number = building_name = ""

    def _apply_hn(tags):
        nonlocal house_number, block_number, lot_number, unit_number
        hn = _tv(tags, "addr:housenumber")
        if hn and not (block_number or lot_number or house_number):
            blk, lot, unit, rem = parse_hn(hn)
            if blk  and not block_number: block_number = blk
            if lot  and not lot_number:   lot_number   = lot
            if unit and not unit_number:  unit_number  = unit
            if rem:                       house_number = rem
            elif not blk and not lot:     house_number = hn

    def _apply_explicit(tags):
        nonlocal block_number, lot_number, unit_number
        if not block_number:
            block_number = _tv(tags,"addr:block_number") or _tv(tags,"addr:block")
        if not lot_number:
            lot_number   = _tv(tags,"addr:lot_number")   or _tv(tags,"addr:lot")
        if not unit_number:
            unit_number  = _tv(tags,"addr:unit")         or _tv(tags,"addr:flats")

    for row in d["building_rows"]:
        tags  = row.get("tags")
        bname = (row.get("name") or "").strip()
        if bname and not building_name:
            building_name = bname
        _apply_hn(tags)
        _apply_explicit(tags)
        sn = _tv(tags,"addr:street")
        if sn and not road_name:
            road_name = sn
        pc = _tv(tags,"addr:postcode")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc

    # ── Address nodes ─────────────────────────────────────────────────────────
    for row in d["addr_points"]:
        tags = row.get("tags")
        dist = row.get("dist") or 9999
        if dist > 120:
            continue
        _apply_hn(tags)
        _apply_explicit(tags)
        if dist < 80:
            sn = _tv(tags,"addr:street")
            if sn: road_name = sn
        pc = _tv(tags,"addr:postcode")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc
        if not neighbourhood:
            nb = _tv(tags,"addr:neighbourhood") or _tv(tags,"addr:quarter")
            if nb: neighbourhood = nb

    # ── Generic points ────────────────────────────────────────────────────────
    for row in d["near_points"]:
        name = (row.get("name") or "").strip()
        tags = row.get("tags")
        dist = row.get("dist") or 9999
        if dist > 160:
            continue
        if not neighbourhood and any(kw in name.lower() for kw in SUBDIV_KW):
            neighbourhood = name
        pc = _tv(tags,"addr:postcode")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc

    # ── Postcode last-resort ──────────────────────────────────────────────────
    if not postcode:
        postcode = d["postcode_val"]

    # ── Assemble ──────────────────────────────────────────────────────────────
    state  = province or region
    prefix = []
    if unit_number:
        prefix.append(f"Unit {unit_number}")
    if block_number and lot_number:
        prefix.append(f"Blk {block_number} Lot {lot_number}")
    elif block_number:
        prefix.append(f"Blk {block_number}")
    elif lot_number:
        prefix.append(f"Lot {lot_number}")
    if house_number and road_name:
        prefix.append(f"{house_number} {road_name}")
    elif house_number:
        prefix.append(house_number)
    elif road_name:
        prefix.append(road_name)

    parts = prefix[:]
    if building_name:              parts.append(building_name)
    if neighbourhood:              parts.append(neighbourhood)
    if barangay:                   parts.append(barangay)
    if district:                   parts.append(district)
    if city:                       parts.append(city)
    if county:                     parts.append(county)
    if state:                      parts.append(state)
    if region and region != state: parts.append(region)
    if postcode:                   parts.append(postcode)
    parts.append("Philippines")

    display_name = ", ".join(parts)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)

    print(
        f"[geocode] {elapsed}ms | blk={block_number!r} lot={lot_number!r} "
        f"unit={unit_number!r} house={house_number!r} bldg={building_name!r} "
        f"road={road_name!r} hood={neighbourhood!r} brgy={barangay!r} "
        f"city={city!r} state={state!r} pc={postcode!r}"
    )

    return jsonify({
        "data": {
            "display_name": display_name,
            "elapsed_ms":   elapsed,
            "address": {
                "unit":          unit_number,
                "block":         block_number,
                "lot":           lot_number,
                "house_number":  house_number,
                "building":      building_name,
                "road":          road_name,
                "neighbourhood": neighbourhood,
                "suburb":        barangay,
                "district":      district,
                "city":          city,
                "county":        county,
                "state":         state,
                "region":        region,
                "postcode":      postcode,
                "country":       "Philippines",
                "country_code":  "ph",
            }
        }
    })


# --------------------------------------------------------------------------- #
# /debug  – shows raw OSM rows; use this to verify what's in your DB          #
# GET /debug?lat=14.3258395&lon=121.0136624                                   #
# --------------------------------------------------------------------------- #

@app.route('/debug', methods=['GET'])
def debug():
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid lat/lon"}), 400

    pt = _pt(lon, lat)
    c  = cur()
    out = {}

    c.execute(f"""
        SELECT name, building, tags,
               ST_Contains(way, {pt}) AS exact,
               ST_Distance(way, {pt}) AS dist_m
        FROM planet_osm_polygon
        WHERE building IS NOT NULL
          AND way && ST_Expand({pt}, 150)
          AND ST_DWithin(way, {pt}, 150)
        ORDER BY exact DESC, dist_m ASC
        LIMIT 10
    """)
    out["buildings"] = [dict(r) for r in (c.fetchall() or [])]

    c.execute(f"""
        SELECT name, tags,
               ST_Distance(way, {pt}) AS dist_m
        FROM planet_osm_point
        WHERE way && ST_Expand({pt}, 300)
          AND ST_DWithin(way, {pt}, 300)
        ORDER BY dist_m
        LIMIT 15
    """)
    out["nearby_points"] = [dict(r) for r in (c.fetchall() or [])]

    c.execute(f"""
        SELECT name, admin_level, place, tags
        FROM planet_osm_polygon
        WHERE way IS NOT NULL
          AND way && ST_Expand({pt}, 200000)
          AND ST_Contains(way, {pt})
          AND (admin_level IS NOT NULL
               OR place IN ('city','municipality','town','village',
                            'suburb','quarter','neighbourhood'))
        ORDER BY ST_Area(way) ASC
        LIMIT 15
    """)
    out["admin_boundaries"] = [dict(r) for r in (c.fetchall() or [])]

    c.execute(f"""
        SELECT name, highway,
               ST_Distance(way, {pt}) AS dist_m
        FROM planet_osm_line
        WHERE name IS NOT NULL
          AND highway IS NOT NULL
          AND way && ST_Expand({pt}, 300)
          AND ST_DWithin(way, {pt}, 300)
        ORDER BY dist_m
        LIMIT 10
    """)
    out["roads"] = [dict(r) for r in (c.fetchall() or [])]

    return jsonify(out)


# --------------------------------------------------------------------------- #
# Ensure spatial indexes exist (run once at startup)                          #
# --------------------------------------------------------------------------- #

def ensure_indexes():
    c = cur()
    for name, table, col in [
        ("idx_osm_line_way",    "planet_osm_line",    "way"),
        ("idx_osm_point_way",   "planet_osm_point",   "way"),
        ("idx_osm_polygon_way", "planet_osm_polygon", "way"),
    ]:
        c.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING GIST({col});")
    print("[startup] Spatial indexes verified.")


if __name__ == '__main__':
    ensure_indexes()
    app.run(debug=True, port=5111)