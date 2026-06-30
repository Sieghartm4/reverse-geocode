from flask import Blueprint, request, jsonify, current_app
import time

reverse_bp = Blueprint('reverse', __name__)

@reverse_bp.route('/reverse', methods=['GET'])
def reverse_geocode():
    t0 = time.perf_counter()
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid lat/lon'}), 400

    d = current_app.fetch_all_cached(lon, lat)
    addr = current_app.assemble_address(d)
    elapsed = round((time.perf_counter() - t0) * 1000, 1)

    print(
        f"[geocode] {elapsed}ms | blk={addr['block']!r} lot={addr['lot']!r} "
        f"unit={addr['unit']!r} house={addr['house_number']!r} bldg={addr['building']!r} "
        f"road={addr['road']!r} hood={addr['neighbourhood']!r} brgy={addr['suburb']!r} "
        f"city={addr['city']!r} state={addr['state']!r} pc={addr['postcode']!r}"
    )

    return jsonify({
        'data': {
            'display_name': addr['display_name'],
            'elapsed_ms': elapsed,
            'lon': lon,
            'lat': lat,
            'address': {
                'unit': addr['unit'],
                'block': addr['block'],
                'lot': addr['lot'],
                'house_number': addr['house_number'],
                'building': addr['building'],
                'road': addr['road'],
                'neighbourhood': addr['neighbourhood'],
                'suburb': addr['suburb'],
                'district': addr['district'],
                'city': addr['city'],
                'county': addr['county'],
                'state': addr['state'],
                'region': addr['region'],
                'postcode': addr['postcode'],
                'country': 'Philippines',
                'country_code': 'ph',
            },
        },
    })
