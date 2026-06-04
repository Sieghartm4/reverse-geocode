"""
Reverse geocoder for Philippine OSM data.
Optimised:
  - ThreadedConnectionPool (replaces single _conn) — handles concurrent requests
  - Merged polygon queries 2+5 — one DB round-trip instead of two
  - Removed sequential postcode fallback loop — postcode pulled inline
  - LRU in-memory cache (2 048 slots, coords rounded to ~11 m) — repeat hits are free
  - /debug endpoint to inspect raw OSM tags for any coordinate

Run in production with Gunicorn + gevent:
  pip install gunicorn gevent
  gunicorn -w 4 -k gevent --worker-connections 100 -b 0.0.0.0:5111 app:app
  gunicorn -c gunicorn.conf.py app:app

Run on Windows with Waitress:
  pip install waitress
  python waitress_run.py

PostgreSQL tuning (add to postgresql.conf, then reload):
  shared_buffers      = 2GB          # ~25 % of RAM
  effective_cache_size = 6GB         # ~75 % of RAM
  work_mem            = 64MB
  max_connections     = 100
  random_page_cost    = 1.1          # SSD only
  # After changing, run: SELECT pg_reload_conf();
  # Also run periodically: ANALYZE planet_osm_polygon; ANALYZE planet_osm_line; ANALYZE planet_osm_point;
"""

from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras
from psycopg2 import pool as pg_pool
from contextlib import contextmanager
from functools import lru_cache
import re
import time
import os
import json

app = Flask(__name__)

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Philippines Reverse Geocoding API",
        "version": "1.0.0",
        "description": "Reverse geocode Philippine coordinates using OSM/PostGIS data."
    },
    "servers": [{"url": "/"}],
    "paths": {
        "/reverse": {
            "get": {
                "summary": "Reverse geocode coordinates",
                "parameters": [
                    {
                        "name": "lat",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Latitude of the location."
                    },
                    {
                        "name": "lon",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Longitude of the location."
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful reverse geocode result",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid latitude or longitude"
                    }
                }
            }
        },
        "/debug": {
            "get": {
                "summary": "Inspect raw OSM data for a location",
                "parameters": [
                    {
                        "name": "lat",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Latitude of the location."
                    },
                    {
                        "name": "lon",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Longitude of the location."
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Debug information from raw OSM tables",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid latitude or longitude"
                    }
                }
            }
        }
    }
}

# --------------------------------------------------------------------------- #
# Load Environment Variables                                                   #
# --------------------------------------------------------------------------- #

if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if line.strip() and '=' in line:
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# --------------------------------------------------------------------------- #
# Database Configuration                                                       #
# --------------------------------------------------------------------------- #

try:
    DB_NAME     = os.environ["DB_NAME"]
    DB_USER     = os.environ["DB_USER"]
    DB_PASSWORD = os.environ["DB_PASSWORD"]
    DB_HOST     = os.environ["DB_HOST"]
    DB_PORT     = os.environ["DB_PORT"]
except KeyError as e:
    missing_var = str(e).strip("'")
    print(f"[ERROR] Missing required environment variable: {missing_var}")
    print("[ERROR] Please create a .env file with the required database configuration:")
    print("[ERROR]   DB_NAME=your_database_name")
    print("[ERROR]   DB_USER=your_username")
    print("[ERROR]   DB_PASSWORD=your_password")
    print("[ERROR]   DB_HOST=your_host_or_localhost")
    print("[ERROR]   DB_PORT=your_port_or_5432")
    exit(1)

# Pool size: raise maxconn if you run more Gunicorn workers
# Rule of thumb: maxconn = num_workers * 5  (never exceed postgres max_connections)
POOL_MIN = int(os.environ.get("DB_POOL_MIN", "4"))
POOL_MAX = int(os.environ.get("DB_POOL_MAX", "20"))

FLASK_HOST  = os.environ.get("FLASK_HOST",  "127.0.0.1")
FLASK_PORT  = int(os.environ.get("FLASK_PORT",  "5111"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

print(f"[startup] Database config: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
print(f"[startup] Pool: min={POOL_MIN} max={POOL_MAX}")
print(f"[startup] Flask server: {FLASK_HOST}:{FLASK_PORT} (debug={FLASK_DEBUG})")

# --------------------------------------------------------------------------- #
# Connection Pool  (replaces single _conn global)                             #
# --------------------------------------------------------------------------- #

def _build_dsn() -> str:
    dsn = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} port={DB_PORT}"
    if DB_HOST:
        dsn += f" host={DB_HOST}"
    return dsn


_pool: pg_pool.ThreadedConnectionPool | None = None


def get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=POOL_MIN,
            maxconn=POOL_MAX,
            dsn=_build_dsn(),
            application_name="reverse_geocoder",
        )
        print("[startup] Connection pool created.")
    return _pool


@contextmanager
def db_cursor():
    """Grab a connection from the pool, yield a RealDictCursor, return it on exit."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
            yield c
    except Exception:
        # If the connection is broken, discard it so the pool replaces it
        pool.putconn(conn, close=True)
        raise
    else:
        pool.putconn(conn)


# --------------------------------------------------------------------------- #
# Schema validation (runs once at import time)                                #
# --------------------------------------------------------------------------- #

def _column_exists(table: str, column: str) -> bool:
    with db_cursor() as c:
        c.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=%s AND column_name=%s",
            (table, column),
        )
        return c.fetchone() is not None


def _ensure_required_osm_columns() -> None:
    required = {
        'planet_osm_polygon': ['tags', 'admin_level', 'place', 'way', 'name'],
        'planet_osm_point':   ['tags', 'way', 'name'],
        'planet_osm_line':    ['way', 'highway', 'name'],
    }
    missing = [
        f"{tbl}.{col}"
        for tbl, cols in required.items()
        for col in cols
        if not _column_exists(tbl, col)
    ]
    if missing:
        print("[ERROR] Your PostGIS database is missing required OSM columns.")
        print("[ERROR] Missing columns:")
        for col in missing:
            print(f"  - {col}")
        print("[ERROR] Example import command:")
        print("  osm2pgsql -d ph_geodata -U postgres --create --slim --hstore "
              "--number-processes 4 philippines-latest.osm.pbf")
        exit(1)


_ensure_required_osm_columns()

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _pt(lon: float, lat: float) -> str:
    """Native EPSG:3857 point expression — keeps spatial index hits."""
    return f"ST_Transform(ST_SetSRID(ST_MakePoint({lon},{lat}),4326),3857)"


def _tv(tags, key: str) -> str:
    """Extract a tag value from a psycopg2 hstore dict or raw hstore text."""
    if not tags:
        return ""
    if isinstance(tags, dict):
        return (tags.get(key) or "").strip()
    m = re.search(rf'{re.escape(key)}=>"([^"]*)"', str(tags))
    return m.group(1).strip() if m else ""


_BLK_RE  = re.compile(r'\b(?:Blk|Block|B)\.?\s*(\w+)',                re.IGNORECASE)
_LOT_RE  = re.compile(r'\b(?:Lot|L(?=[\s\d]))\.?\s*(\w+)',            re.IGNORECASE)
_UNIT_RE = re.compile(r'\b(?:Unit|Room|Rm|Apt|Apartment)\.?\s*(\w+)', re.IGNORECASE)


def parse_hn(hn: str):
    """Split addr:housenumber into (block, lot, unit, remainder)."""
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


SUBDIV_KW = (
    'village', 'subdivision', 'phase', 'estate', 'compound',
    'homes', 'residences', 'heights', 'springs', 'gardens',
)

# --------------------------------------------------------------------------- #
# DB Fetch  (merged polygon queries 2+5, no postcode fallback loop)           #
# --------------------------------------------------------------------------- #

def fetch_all(lon: float, lat: float) -> dict:
    pt = _pt(lon, lat)
    t0 = time.perf_counter()

    with db_cursor() as c:

        # ── 1. Best local road ────────────────────────────────────────────────
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

        # ── 2+5 MERGED: Admin boundaries + nearby named polygons ─────────────
        # One query covers both use-cases; split by contains_pt in Python.
        # Also pulls postcode inline — no separate postcode query needed.
        c.execute(f"""
            SELECT
                name, admin_level, place, tags, landuse,
                ST_Area(way)             AS area_m2,
                ST_Distance(way, {pt})  AS dist,
                ST_Contains(way, {pt})  AS contains_pt,
                CASE
                    WHEN tags ? 'addr:postcode'
                         AND tags->'addr:postcode' ~ '^[0-9]{{3,6}}$'
                    THEN tags->'addr:postcode'
                    ELSE NULL
                END AS inline_postcode
            FROM planet_osm_polygon
            WHERE way IS NOT NULL
              AND way && ST_Expand({pt}, 200000)
              AND (
                  -- admin / place polygons that contain the point
                  (ST_Contains(way, {pt})
                   AND (admin_level IS NOT NULL
                        OR place IN ('city','municipality','town','village',
                                     'suburb','quarter','neighbourhood')))
                  OR
                  -- nearby named polygons (subdivision / neighbourhood)
                  (name IS NOT NULL
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
                   ))
              )
            ORDER BY area_m2 ASC
            LIMIT 30
        """)
        combined_poly_rows = c.fetchall() or []

        # ── 3. Buildings at / near the point ──────────────────────────────────
        c.execute(f"""
            SELECT name, tags, building,
                   ST_Contains(way, {pt}) AS exact,
                   ST_Area(way)           AS area_m2,
                   ST_Distance(way, {pt}) AS dist
            FROM planet_osm_polygon
            WHERE building IS NOT NULL
              AND way && ST_Expand({pt}, 60)
              AND ST_DWithin(way, {pt}, 60)
            ORDER BY exact DESC, area_m2 ASC, dist ASC
            LIMIT 5
        """)
        building_rows = c.fetchall() or []

        # ── 4. Address nodes ──────────────────────────────────────────────────
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

        # ── 5. Generic nearby points ──────────────────────────────────────────
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

    # Split combined polygon rows into admin vs nearby-poly buckets
    admin_rows   = [r for r in combined_poly_rows if r.get("contains_pt")]
    nearby_polys = [r for r in combined_poly_rows if not r.get("contains_pt")]

    # Extract postcode inline (no extra DB round-trip)
    postcode_val = ""
    for row in combined_poly_rows:
        pc = row.get("inline_postcode")
        if pc:
            postcode_val = pc
            break

    print(f"[geocode] DB done in {(time.perf_counter()-t0)*1000:.0f} ms  "
          f"(admin={len(admin_rows)} nearby={len(nearby_polys)} "
          f"bldg={len(building_rows)} addr={len(addr_points)})")

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
# LRU Cache wrapper                                                            #
# Coords are rounded to 4 decimal places (~11 m) before caching.             #
# Cache is per-process; with Gunicorn multi-worker each worker has its own.  #
# For a shared cache across workers, swap to Redis (see comment below).       #
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=2048)
def _fetch_all_cached(lon_r: float, lat_r: float) -> str:
    """Returns JSON-serialised fetch_all result (lru_cache requires hashable args)."""
    result = fetch_all(lon_r, lat_r)
    # Convert RealDictRow objects to plain dicts so they serialise cleanly
    def _clean(obj):
        if isinstance(obj, list):
            return [_clean(i) for i in obj]
        if hasattr(obj, 'items'):
            return {k: _clean(v) for k, v in obj.items()}
        return obj
    return json.dumps(_clean(result))


def fetch_all_cached(lon: float, lat: float) -> dict:
    lon_r = round(lon, 4)
    lat_r = round(lat, 4)
    return json.loads(_fetch_all_cached(lon_r, lat_r))


# --------------------------------------------------------------------------- #
# Optional Redis cache (multi-worker shared cache)                            #
# Uncomment and set REDIS_URL in .env to enable.                              #
# --------------------------------------------------------------------------- #
# import redis as _redis, hashlib as _hashlib
# _redis_client = _redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
#                                  decode_responses=True)
# CACHE_TTL = 3600
#
# def fetch_all_cached(lon: float, lat: float) -> dict:
#     key = "rgeo:" + _hashlib.md5(f"{round(lon,4)},{round(lat,4)}".encode()).hexdigest()
#     cached = _redis_client.get(key)
#     if cached:
#         return json.loads(cached)
#     result = fetch_all(lon, lat)
#     def _clean(obj):
#         if isinstance(obj, list): return [_clean(i) for i in obj]
#         if hasattr(obj, 'items'): return {k: _clean(v) for k, v in obj.items()}
#         return obj
#     _redis_client.setex(key, CACHE_TTL, json.dumps(_clean(result)))
#     return result


# --------------------------------------------------------------------------- #
# Address assembly (unchanged logic, extracted for clarity)                   #
# --------------------------------------------------------------------------- #

def _apply_hn(tags, state: dict):
    hn = _tv(tags, "addr:housenumber")
    if hn and not (state['block_number'] or state['lot_number'] or state['house_number']):
        blk, lot, unit, rem = parse_hn(hn)
        if blk  and not state['block_number']: state['block_number'] = blk
        if lot  and not state['lot_number']:   state['lot_number']   = lot
        if unit and not state['unit_number']:  state['unit_number']  = unit
        if rem:                                state['house_number'] = rem
        elif not blk and not lot:              state['house_number'] = hn


def _apply_explicit(tags, state: dict):
    if not state['block_number']:
        state['block_number'] = _tv(tags, "addr:block_number") or _tv(tags, "addr:block")
    if not state['lot_number']:
        state['lot_number']   = _tv(tags, "addr:lot_number")   or _tv(tags, "addr:lot")
    if not state['unit_number']:
        state['unit_number']  = _tv(tags, "addr:unit")         or _tv(tags, "addr:flats")


def assemble_address(d: dict) -> dict:
    road_name    = ((d["road_row"] or {}).get("name") or "").strip()
    barangay = district = city = county = province = region = postcode = ""
    neighbourhood = ""
    s = dict(
        house_number="", block_number="", lot_number="",
        unit_number="", building_name="",
    )

    # Admin boundaries
    for row in d["admin_rows"]:
        name  = (row.get("name") or "").strip()
        al    = row.get("admin_level") or ""
        place = (row.get("place") or "").lower()
        tags  = row.get("tags")
        if not name:
            continue
        pc = _tv(tags, "addr:postcode") or _tv(tags, "postal_code")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc
        lv = int(al) if al.isdigit() else 99
        if   lv == 10 and not barangay:  barangay = name
        elif lv ==  7 and not district:  district = name
        elif lv ==  6 and not city:      city     = name
        elif lv ==  5 and not county:    county   = name
        elif lv ==  4 and not province:  province = name
        elif lv in (3, 2) and not region: region  = name
        if place in ('city', 'municipality', 'town') and not city:     city     = name
        if place in ('suburb', 'neighbourhood')       and not barangay: barangay = name

    # Neighbourhood from nearby polygons
    for row in d["nearby_polys"]:
        name  = (row.get("name") or "").strip()
        place = (row.get("place") or "").lower()
        dist  = row.get("dist") or 9999
        if not name or dist > 380:
            continue
        if place in ('neighbourhood', 'quarter') or any(kw in name.lower() for kw in SUBDIV_KW):
            neighbourhood = name
            break

    # Buildings
    for row in d["building_rows"]:
        tags  = row.get("tags")
        bname = (row.get("name") or "").strip()
        if bname and not s['building_name']:
            s['building_name'] = bname
        _apply_hn(tags, s)
        _apply_explicit(tags, s)
        sn = _tv(tags, "addr:street")
        if sn and not road_name:
            road_name = sn
        pc = _tv(tags, "addr:postcode")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc

    # Address nodes
    for row in d["addr_points"]:
        tags = row.get("tags")
        dist = row.get("dist") or 9999
        if dist > 120:
            continue
        _apply_hn(tags, s)
        _apply_explicit(tags, s)
        if dist < 80:
            sn = _tv(tags, "addr:street")
            if sn: road_name = sn
        pc = _tv(tags, "addr:postcode")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc
        if not neighbourhood:
            nb = _tv(tags, "addr:neighbourhood") or _tv(tags, "addr:quarter")
            if nb: neighbourhood = nb

    # Generic nearby points
    for row in d["near_points"]:
        name = (row.get("name") or "").strip()
        tags = row.get("tags")
        dist = row.get("dist") or 9999
        if dist > 160:
            continue
        if not neighbourhood and any(kw in name.lower() for kw in SUBDIV_KW):
            neighbourhood = name
        pc = _tv(tags, "addr:postcode")
        if pc and re.match(r'^\d{3,6}$', pc) and not postcode:
            postcode = pc

    # Postcode last-resort (from merged query inline extraction)
    if not postcode:
        postcode = d["postcode_val"]

    state_val = province or region
    prefix = []
    if s['unit_number']:
        prefix.append(f"Unit {s['unit_number']}")
    if s['block_number'] and s['lot_number']:
        prefix.append(f"Blk {s['block_number']} Lot {s['lot_number']}")
    elif s['block_number']:
        prefix.append(f"Blk {s['block_number']}")
    elif s['lot_number']:
        prefix.append(f"Lot {s['lot_number']}")
    if s['house_number'] and road_name:
        prefix.append(f"{s['house_number']} {road_name}")
    elif s['house_number']:
        prefix.append(s['house_number'])
    elif road_name:
        prefix.append(road_name)

    parts = prefix[:]
    if s['building_name']:             parts.append(s['building_name'])
    if neighbourhood:                  parts.append(neighbourhood)
    if barangay:                       parts.append(barangay)
    if district:                       parts.append(district)
    if city:                           parts.append(city)
    if county:                         parts.append(county)
    if state_val:                      parts.append(state_val)
    if region and region != state_val: parts.append(region)
    if postcode:                       parts.append(postcode)
    parts.append("Philippines")

    return dict(
        display_name=", ".join(parts),
        unit=s['unit_number'],
        block=s['block_number'],
        lot=s['lot_number'],
        house_number=s['house_number'],
        building=s['building_name'],
        road=road_name,
        neighbourhood=neighbourhood,
        suburb=barangay,
        district=district,
        city=city,
        county=county,
        state=state_val,
        region=region,
        postcode=postcode,
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

    d    = fetch_all_cached(lon, lat)
    addr = assemble_address(d)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)

    print(
        f"[geocode] {elapsed}ms | blk={addr['block']!r} lot={addr['lot']!r} "
        f"unit={addr['unit']!r} house={addr['house_number']!r} bldg={addr['building']!r} "
        f"road={addr['road']!r} hood={addr['neighbourhood']!r} brgy={addr['suburb']!r} "
        f"city={addr['city']!r} state={addr['state']!r} pc={addr['postcode']!r}"
    )

    return jsonify({
        "data": {
            "display_name": addr["display_name"],
            "elapsed_ms":   elapsed,
            "address": {
                "unit":          addr["unit"],
                "block":         addr["block"],
                "lot":           addr["lot"],
                "house_number":  addr["house_number"],
                "building":      addr["building"],
                "road":          addr["road"],
                "neighbourhood": addr["neighbourhood"],
                "suburb":        addr["suburb"],
                "district":      addr["district"],
                "city":          addr["city"],
                "county":        addr["county"],
                "state":         addr["state"],
                "region":        addr["region"],
                "postcode":      addr["postcode"],
                "country":       "Philippines",
                "country_code":  "ph",
            }
        }
    })


# --------------------------------------------------------------------------- #
# /debug                                                                       #
# --------------------------------------------------------------------------- #

@app.route('/debug', methods=['GET'])
def debug():
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid lat/lon"}), 400

    pt  = _pt(lon, lat)
    out = {}

    with db_cursor() as c:
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


@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    return jsonify(OPENAPI_SPEC)


@app.route('/docs', methods=['GET'])
def swagger_ui():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Reverse Geocode API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@4/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@4/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@4/swagger-ui-standalone-preset.js"></script>
  <script>
    window.UI = SwaggerUIBundle({
      url: '/openapi.json',
      dom_id: '#swagger-ui',
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
      ],
      layout: 'BaseLayout',
      deepLinking: true
    });
  </script>
</body>
</html>'''


# --------------------------------------------------------------------------- #
# Spatial indexes (run once at startup)                                        #
# --------------------------------------------------------------------------- #

def ensure_indexes():
    with db_cursor() as c:
        for name, table, col in [
            ("idx_osm_line_way",    "planet_osm_line",    "way"),
            ("idx_osm_point_way",   "planet_osm_point",   "way"),
            ("idx_osm_polygon_way", "planet_osm_polygon", "way"),
        ]:
            c.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} USING GIST({col});")
    print("[startup] Spatial indexes verified.")


# --------------------------------------------------------------------------- #
# Entry point (dev only — use Gunicorn in production)                         #
# --------------------------------------------------------------------------- #

if __name__ == '__main__':
    ensure_indexes()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)