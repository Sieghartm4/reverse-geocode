from flask import Blueprint, jsonify, current_app

meta_bp = Blueprint('meta', __name__)

@meta_bp.route('/meta', methods=['GET'])
def meta():
    return jsonify({
        'name': 'reverse-geocode',
        'version': current_app.APP_VERSION,
        'description': 'Reverse geocoding API for Philippines OSM data',
    })
