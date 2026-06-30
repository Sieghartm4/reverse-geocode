from flask import Blueprint, jsonify, current_app

cities_bp = Blueprint('cities', __name__)

@cities_bp.route('/cities', methods=['GET'])
def cities():
    with current_app.db_cursor() as c:
        c.execute("""
            SELECT name, place,
                   ST_X(ST_Transform(ST_Centroid(way), 4326)) AS lon,
                   ST_Y(ST_Transform(ST_Centroid(way), 4326)) AS lat,
                   ST_XMin(ST_Transform(way, 4326)) AS min_lon,
                   ST_YMin(ST_Transform(way, 4326)) AS min_lat,
                   ST_XMax(ST_Transform(way, 4326)) AS max_lon,
                   ST_YMax(ST_Transform(way, 4326)) AS max_lat
            FROM planet_osm_polygon
            WHERE name IS NOT NULL
              AND place IN ('city','municipality','town','village')
            ORDER BY
              CASE place
                WHEN 'city' THEN 1
                WHEN 'municipality' THEN 2
                WHEN 'town' THEN 3
                WHEN 'village' THEN 4
                ELSE 5
              END,
              ST_Area(way) ASC
            LIMIT 20
        """)
        rows = c.fetchall() or []

    cities = []
    for row in rows:
        cities.append({
            'name': row['name'],
            'type': row['place'] or 'city',
            'lon': float(row['lon']) if row['lon'] is not None else None,
            'lat': float(row['lat']) if row['lat'] is not None else None,
            'bbox': [
                float(row['min_lon']),
                float(row['min_lat']),
                float(row['max_lon']),
                float(row['max_lat']),
            ],
        })

    return jsonify({'cities': cities})
