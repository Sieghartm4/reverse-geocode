from flask import Blueprint, request, make_response, Response
import os
import hashlib

fonts_bp = Blueprint('fonts', __name__)

@fonts_bp.route('/fonts/<path:fontstack>/<path:range_pbf>', methods=['GET'])
def serve_glyphs(fontstack, range_pbf):
    base = os.path.dirname(__file__)
    fonts_root = os.path.join(base, '..', 'fonts')
    fonts_root = os.path.abspath(fonts_root)
    fontstack_path = os.path.normpath(os.path.join(fonts_root, fontstack))

    if not fontstack_path.startswith(fonts_root + os.sep):
        return ('', 404)

    file_path = os.path.join(fontstack_path, range_pbf)
    if os.path.isfile(file_path):
        with open(file_path, 'rb') as fh:
            data = fh.read()

        etag = '"' + hashlib.md5(data).hexdigest() + '"'
        if_none = request.headers.get('If-None-Match')
        if if_none and if_none == etag:
            resp = make_response('', 304)
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            resp.headers['ETag'] = etag
            return resp

        resp = Response(data, mimetype='application/x-protobuf')
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        resp.headers['ETag'] = etag
        return resp

    return ('', 404)
