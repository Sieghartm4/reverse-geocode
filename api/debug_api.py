from flask import Blueprint, jsonify, request, current_app

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/debug', methods=['GET'])
def debug():
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid lat/lon"}), 400

    pt = current_app._pt(lon, lat)
    out = {}

    with current_app.db_cursor() as c:
        # 1. BUILDINGS within 150m
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

        # 2. NEARBY POINTS within 300m
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

        # 3. ADMIN BOUNDARIES containing the point
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

        # 4. ROADS within 300m
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
