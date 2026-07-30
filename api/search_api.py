from flask import Blueprint, request, jsonify, current_app
from difflib import SequenceMatcher
import json
import re
import time

search_bp = Blueprint('search', __name__)

@search_bp.route('/search', methods=['GET'])
def search():
    t0 = time.perf_counter()
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'results': [], 'elapsed_ms': 0})

    def parse_coordinate_pair(text: str):
        parts = [p.strip() for p in text.split(',')]
        if len(parts) != 2:
            return None
        try:
            a = float(parts[0])
            b = float(parts[1])
        except ValueError:
            return None

        def is_lat(value):
            return -90.0 <= value <= 90.0

        def is_lon(value):
            return -180.0 <= value <= 180.0

        if is_lat(a) and is_lon(b) and not is_lat(b):
            return a, b
        if is_lon(a) and is_lat(b) and not is_lon(b):
            return b, a
        if is_lat(a) and is_lon(b):
            return a, b
        if is_lon(a) and is_lat(b):
            return b, a
        return None

    coord_pair = parse_coordinate_pair(query)
    if coord_pair is not None:
        lat, lon = coord_pair
        try:
            d = current_app.fetch_all_cached(lon, lat)
            addr = current_app.assemble_address(d)
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            return jsonify({'results': [{
                'name': addr['display_name'],
                'type': 'coordinates',
                'lon': lon,
                'lat': lat,
                'subtitle': addr['display_name'],
            }], 'elapsed_ms': elapsed})
        except Exception:
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            return jsonify({'results': [], 'elapsed_ms': elapsed})

    # Tokenize for better LIKE matching and ignore commas/separators.
    tokens = [token for token in re.split(r"[\s,]+", query) if token]
    if len(tokens) > 3:
        tokens = tokens[:3]  # Limit tokens for DB performance
    
    def fuzzy_score(text: str) -> float:
        """Quick fuzzy score - only used for sorting top results."""
        if not text:
            return 0.0
        score = SequenceMatcher(None, query.lower(), text.lower()).ratio()
        if text.lower().startswith(query.lower()):
            score += 0.15
        return score

    try:
        rows = json.loads(current_app._search_db_cached(tuple(tokens)))
    except Exception:
        rows = []

    # Single pass through results with dedupe and scoring
    results = []
    seen_display = set()

    for row in rows:
        name = (row['name'] or '').strip()
        if not name:
            continue

        type_value = (row['type'] or 'place').strip()
        lon = float(row['lon']) if row['lon'] is not None else None
        lat = float(row['lat']) if row['lat'] is not None else None
        addr_street = (row.get('addr_street') or '').strip()
        addr_neighbourhood = (row.get('addr_neighbourhood') or '').strip()
        addr_suburb = (row.get('addr_suburb') or '').strip()
        addr_city = (row.get('addr_city') or '').strip()
        addr_province = (row.get('addr_province') or '').strip()
        addr_region = (row.get('addr_region') or '').strip()
        place_tag = (row.get('place_tag') or '').strip()
        priority = int(row.get('priority') or 99)

        # Dedupe by display
        display_key = (name.lower(), type_value.lower(), lon, lat)
        if display_key in seen_display:
            continue
        seen_display.add(display_key)

        # Build subtitle from address fragments
        location_parts = []
        if addr_street and addr_street.lower() != name.lower():
            location_parts.append(addr_street.title())
        if addr_neighbourhood and addr_neighbourhood.lower() not in (name.lower(), addr_street.lower()):
            location_parts.append(addr_neighbourhood.title())
        if addr_suburb and addr_suburb.lower() not in (name.lower(), addr_street.lower(), addr_neighbourhood.lower()):
            location_parts.append(addr_suburb.title())
        if addr_city and addr_city.lower() not in (name.lower(), addr_suburb.lower(), addr_neighbourhood.lower()):
            location_parts.append(addr_city.title())
        if addr_province and addr_province.lower() not in (name.lower(), addr_city.lower()):
            location_parts.append(addr_province.title())
        if addr_region and addr_region.lower() not in (name.lower(), addr_province.lower()):
            location_parts.append(addr_region.title())

        type_label = type_value.title()
        if type_value.lower() in ('point', 'place', 'residential', 'hamlet', 'quarter', 'neighbourhood') and place_tag:
            type_label = place_tag.title()
        elif type_value.lower() == 'polygon':
            type_label = 'Area'

        address_display = None
        if lon is not None and lat is not None:
            try:
                d2 = current_app.fetch_all_cached(lon, lat)
                address_display = current_app.assemble_address(d2).get('display_name')
            except Exception:
                address_display = None

        subtitle = type_label
        if location_parts:
            subtitle = f"{subtitle} • {', '.join(location_parts)}"
        elif address_display:
            subtitle = address_display

        result = {
            'name': name,
            'type': type_value or 'place',
            'lon': lon,
            'lat': lat,
            'subtitle': subtitle,
            'priority': priority,
            'score': fuzzy_score(name),
        }
        if row.get('min_lon') is not None:
            result['bbox'] = [
                float(row['min_lon']),
                float(row['min_lat']),
                float(row['max_lon']),
                float(row['max_lat']),
            ]
        results.append(result)

    # Sort by result quality: exact/priority then fuzzy score then name
    results.sort(key=lambda r: (r['priority'], r['score'], r['name']), reverse=False)
    for r in results:
        r.pop('score', None)
        r.pop('priority', None)

    elapsed = round((time.perf_counter() - t0) * 1000, 1)
    return jsonify({'results': results, 'elapsed_ms': elapsed})
