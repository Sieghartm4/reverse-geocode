from flask import Blueprint, request, make_response, Response, current_app
import os
import gzip
import hashlib
import tempfile
import shutil

tiles_bp = Blueprint('tiles', __name__)

@tiles_bp.route('/tiles/<int:z>/<int:x>/<int:y>.pbf', methods=['GET'])
def tile(z, x, y):
    minx, miny, maxx, maxy = current_app._webmercator_tile_bounds(z, x, y)
    envelope = f"ST_MakeEnvelope({minx},{miny},{maxx},{maxy},3857)"

    tile_width = maxx - minx
    simplify_tolerance = tile_width / 1024.0

    include_points = False
    if z < 7:
        polygon_filter = "(place IS NOT NULL OR landuse IS NOT NULL OR tags ? 'natural' OR tags ? 'water' OR building IS NOT NULL OR boundary = 'administrative')"
        line_filter = "(highway IN ('motorway','trunk','primary','secondary') OR tags ? 'waterway')"
        admin_max = 4
    elif z < 10:
        polygon_filter = "(place IS NOT NULL OR landuse IS NOT NULL OR tags ? 'natural' OR tags ? 'water')"
        line_filter = "(highway IN ('motorway','trunk','primary','secondary') OR tags ? 'waterway')"
        admin_max = 6
    elif z < 13:
        polygon_filter = "(place IS NOT NULL OR landuse IS NOT NULL OR tags ? 'natural' OR tags ? 'water' OR building IS NOT NULL)"
        line_filter = "(highway IN ('motorway','trunk','primary','secondary','tertiary') OR tags ? 'waterway')"
        admin_max = 8
        include_points = True
    elif z < 16:
        polygon_filter = "(building IS NOT NULL OR place IS NOT NULL OR landuse IS NOT NULL OR tags ? 'natural' OR tags ? 'water')"
        line_filter = "(highway IS NOT NULL OR tags ? 'waterway')"
        admin_max = 10
        include_points = True
    else:
        polygon_filter = "(building IS NOT NULL OR place IS NOT NULL OR landuse IS NOT NULL OR tags ? 'natural' OR tags ? 'water')"
        line_filter = "(highway IS NOT NULL OR tags ? 'waterway')"
        admin_max = 12
        include_points = True

    def mvt_select(type_expr, place_expr, landuse_expr, natural_expr, water_expr,
                   highway_expr, amenity_expr, admin_level_expr, waterway_expr, geom_expr):
        return f"""
                SELECT osm_id::text AS id,
                       {type_expr} AS _type,
                       name,
                       {place_expr},
                       {landuse_expr},
                       {natural_expr},
                       {water_expr},
                       {highway_expr},
                       {amenity_expr},
                       {admin_level_expr},
                       {waterway_expr},
                       ST_AsMVTGeom({geom_expr}, {envelope}, 4096, 256, TRUE) AS geom
        """

    point_sql = ''
    if include_points:
        point_sql = f"""
                UNION ALL
                {mvt_select(
                    "'point'",
                    'NULL::text AS place',
                    'NULL::text AS landuse',
                    'NULL::text AS natural',
                    'NULL::text AS water',
                    'NULL::text AS highway',
                    "tags->'amenity' AS amenity",
                    'NULL::text AS admin_level',
                    'NULL::text AS waterway',
                    'way'
                )}
                FROM planet_osm_point
                WHERE way && {envelope}
                  AND ST_Intersects(way, {envelope})
                  AND (tags ? 'amenity' OR name IS NOT NULL)
        """

    admin_sql = f"""
                UNION ALL
                {mvt_select(
                    "'polygon'",
                    'NULL::text AS place',
                    'NULL::text AS landuse',
                    'NULL::text AS natural',
                    'NULL::text AS water',
                    'NULL::text AS highway',
                    'NULL::text AS amenity',
                    'admin_level::text AS admin_level',
                    'NULL::text AS waterway',
                    f'ST_SimplifyPreserveTopology(way, {simplify_tolerance})'
                )}
                FROM planet_osm_polygon
                WHERE boundary = 'administrative'
                  AND admin_level IS NOT NULL
                  AND (admin_level::int <= {admin_max})
                  AND way && {envelope}
                  AND ST_Intersects(way, {envelope})
        """

    cache_path = None
    cache_file = None
    if current_app.TILE_CACHE_DIR:
        cache_path = os.path.join(current_app.TILE_CACHE_DIR, str(z), str(x))
        cache_file = os.path.join(cache_path, f"{y}.pbf.gz")
        if os.path.isfile(cache_file):
            try:
                with open(cache_file, 'rb') as fh:
                    compressed = fh.read() or b''
                etag = '"' + hashlib.md5(compressed).hexdigest() + '"'
                if_none = request.headers.get('If-None-Match')
                if if_none and if_none == etag:
                    resp = make_response('', 304)
                    resp.headers['Cache-Control'] = 'public, max-age=86400'
                    resp.headers['ETag'] = etag
                    resp.headers['X-Cache'] = 'HIT'
                    return resp
                resp = Response(compressed, mimetype='application/vnd.mapbox-vector-tile')
                resp.headers['Content-Encoding'] = 'gzip'
                resp.headers['Vary'] = 'Accept-Encoding'
                resp.headers['Cache-Control'] = 'public, max-age=86400'
                resp.headers['ETag'] = etag
                resp.headers['X-Cache'] = 'HIT'
                return resp
            except Exception:
                pass

    with current_app.db_cursor() as c:
        c.execute(f"""
            SELECT ST_AsMVT(tile, 'osm', 4096, 'geom') FROM (
                SELECT osm_id::text AS id,
                       'polygon' AS _type,
                       name,
                       place,
                       landuse,
                       tags->'natural' AS natural,
                       tags->'water' AS water,
                       NULL::text AS highway,
                       NULL::text AS amenity,
                       NULL::text AS admin_level,
                       NULL::text AS waterway,
                       ST_AsMVTGeom(ST_SimplifyPreserveTopology(way, {simplify_tolerance}), {envelope}, 4096, 256, TRUE) AS geom
                FROM planet_osm_polygon
                WHERE way && {envelope}
                  AND ST_Intersects(way, {envelope})
                  AND {polygon_filter}
                UNION ALL
                SELECT osm_id::text AS id,
                       CASE WHEN tags ? 'waterway' THEN 'waterway' ELSE 'road' END AS _type,
                       name,
                       NULL::text AS place,
                       NULL::text AS landuse,
                       NULL::text AS natural,
                       NULL::text AS water,
                       highway::text AS highway,
                       NULL::text AS amenity,
                       NULL::text AS admin_level,
                       tags->'waterway' AS waterway,
                       ST_AsMVTGeom(ST_SimplifyPreserveTopology(way, {simplify_tolerance}), {envelope}, 4096, 256, TRUE) AS geom
                FROM planet_osm_line
                WHERE way && {envelope}
                  AND ST_Intersects(way, {envelope})
                  AND {line_filter}
                {point_sql}
                {admin_sql}
            ) AS tile
        """)
        row = c.fetchone()
        payload = b''
        if row:
            if isinstance(row, dict):
                payload = next(iter(row.values())) or b''
            else:
                payload = row[0] or b''

    etag = '"' + hashlib.md5(payload).hexdigest() + '"'
    if_none = request.headers.get('If-None-Match')
    if if_none and if_none == etag:
        resp = make_response('', 304)
        resp.headers['Cache-Control'] = 'public, max-age=3600'
        resp.headers['ETag'] = etag
        return resp

    try:
        compressed = gzip.compress(payload)
    except Exception:
        compressed = payload

    if current_app.TILE_CACHE_DIR and payload and cache_file:
        try:
            os.makedirs(cache_path, exist_ok=True)
            tmpfd, tmppath = tempfile.mkstemp(dir=cache_path, prefix=f"{y}.")
            os.close(tmpfd)
            with open(tmppath, 'wb') as fh:
                fh.write(compressed)
            shutil.move(tmppath, cache_file)
        except Exception:
            try:
                if 'tmppath' in locals() and os.path.exists(tmppath):
                    os.remove(tmppath)
            except Exception:
                pass

    resp = Response(compressed, mimetype='application/vnd.mapbox-vector-tile')
    resp.headers['Content-Encoding'] = 'gzip'
    resp.headers['Vary'] = 'Accept-Encoding'
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    resp.headers['ETag'] = etag
    resp.headers['X-Cache'] = 'MISS'
    return resp
