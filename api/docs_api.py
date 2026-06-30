from flask import Blueprint, jsonify

docs_bp = Blueprint('docs', __name__)

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Philippines Reverse Geocoding API",
        "version": "1.0.0",
        "description": "High-performance reverse geocoding API using OpenStreetMap Philippines data with PostGIS.",
        "contact": {
            "name": "Support",
            "url": "https://github.com/yourusername/reverse-geocode"
        }
    },
    "servers": [
        {"url": "/", "description": "Current server"}
    ],
    "paths": {
        "/reverse": {
            "get": {
                "tags": ["Geocoding"],
                "summary": "Reverse geocode coordinates",
                "description": "Get detailed address information for a given latitude and longitude",
                "operationId": "reverse_geocode",
                "parameters": [
                    {
                        "name": "lat",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Latitude of the location (WGS84 / EPSG:4326)"
                    },
                    {
                        "name": "lon",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Longitude of the location (WGS84 / EPSG:4326)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Successful reverse geocode result",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "display_name": {"type": "string"},
                                                "elapsed_ms": {"type": "number"},
                                                "address": {
                                                    "type": "object",
                                                    "properties": {
                                                        "unit": {"type": "string"},
                                                        "block": {"type": "string"},
                                                        "lot": {"type": "string"},
                                                        "house_number": {"type": "string"},
                                                        "building": {"type": "string"},
                                                        "road": {"type": "string"},
                                                        "neighbourhood": {"type": "string"},
                                                        "suburb": {"type": "string"},
                                                        "district": {"type": "string"},
                                                        "city": {"type": "string"},
                                                        "county": {"type": "string"},
                                                        "state": {"type": "string"},
                                                        "region": {"type": "string"},
                                                        "postcode": {"type": "string"},
                                                        "country": {"type": "string"},
                                                        "country_code": {"type": "string"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid latitude or longitude"
                    }
                }
            }
        },
        "/search": {
            "get": {
                "tags": ["Search"],
                "summary": "Search for places by name",
                "description": "Search for cities, areas, roads, and landmarks by name pattern",
                "operationId": "search",
                "parameters": [
                    {
                        "name": "q",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Search pattern (name, place, or feature)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Array of matching results with locations",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "results": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "type": {"type": "string"},
                                                    "lon": {"type": "number"},
                                                    "lat": {"type": "number"},
                                                    "min_lon": {"type": "number"},
                                                    "min_lat": {"type": "number"},
                                                    "max_lon": {"type": "number"},
                                                    "max_lat": {"type": "number"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Missing search query"
                    }
                }
            }
        },
        "/debug": {
            "get": {
                "tags": ["Debug"],
                "summary": "Inspect raw OSM data for a location",
                "description": "Get raw OpenStreetMap data (buildings, points, roads, admin boundaries) for debugging",
                "operationId": "debug",
                "parameters": [
                    {
                        "name": "lat",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Latitude of the location"
                    },
                    {
                        "name": "lon",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "number", "format": "double"},
                        "description": "Longitude of the location"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Raw OSM data for debugging",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "buildings": {"type": "array"},
                                        "nearby_points": {"type": "array"},
                                        "admin_boundaries": {"type": "array"},
                                        "roads": {"type": "array"}
                                    }
                                }
                            }
                        }
                    },
                    "400": {
                        "description": "Invalid latitude or longitude"
                    }
                }
            }
        },
        "/tiles/{z}/{x}/{y}.pbf": {
            "get": {
                "tags": ["Tiles"],
                "summary": "Get vector tile for map rendering using Linear Equation",
                "description": "## Using Linear Equation\n Returns a gzipped Mapbox Vector Tile (MVT) for the requested Web Mercator tile coordinates.\n\n" \
                    "## What [z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html), [x](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html), and [y](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html) mean in `/tiles/{z}/{x}/{y}.pbf`\n\n" \
                    "This API uses standard Slippy map tile coordinates in Web Mercator.\n\n" \
                    "To request higher detail, increase the `z` value in the tile URL. For example, `/tiles/18/{x}/{y}.pbf` requests zoom level 18, while `/tiles/14/{x}/{y}.pbf` requests zoom level 14.\n\n" \
                    "- [z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html) = zoom level\n\n" \
                    "- `0` = whole world in one tile\n" \
                    "- each step increases resolution by 2× in both directions\n" \
                    "- at zoom [z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html), there are [2^z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html) tiles across and [2^z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html) tiles down\n" \
                    "- [x](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html) = tile column\n\n" \
                    "- runs from `0` on the left (west) to `2^z - 1` on the right (east)\n" \
                    "- determines horizontal position\n" \
                    "- [y](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html) = tile row\n\n" \
                    "- runs from `0` at the top (north) to `2^z - 1` at the bottom (south)\n" \
                    "- determines vertical position\n" \
                    "So a URL like:\n\n" \
                    "- `/tiles/14/857/863.pbf`\n\n" \
                    "means:\n\n" \
                    "- zoom `14`\n" \
                    "- column `857`\n" \
                    "- row `863`\n\n" \
                    "---\n\n" \
                    "## How tiles are organized\n" \
                    "At each zoom level:\n\n" \
                    "- [z = 0](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html): one tile covers the full globe\n" \
                    "- [z = 1](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html): 2 × 2 tiles\n" \
                    "- [z = 2](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html): 4 × 4 tiles\n" \
                    "- ...\n" \
                    "- [z = n](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html): [2^n × 2^n](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html) tiles\n\n" \
                    "That means at zoom [z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html), the tile grid size is:\n\n" \
                    "- width = [2^z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html)\n" \
                    "- height = [2^z](vscode-file://vscode-app/c:/Users/dev/AppData/Local/Programs/Microsoft%20VS%20Code/7e7950df89/resources/app/out/vs/code/electron-browser/workbench/workbench.html)\n\n" \
                    "This endpoint is the tile source for the project’s built-in map. In a web/mobile renderer such as MapLibre GL, Mapbox GL, or any MVT-capable client, configure a source URL template like `/tiles/{z}/{x}/{y}.pbf` and let the map client request only the tiles required for the current viewport.\n\n" \
                    "Full map rendering: add a vector tile source with the `/tiles/{z}/{x}/{y}.pbf` template and attach one or more layers. The renderer automatically requests the visible tile set for the map bounds and zoom level.\n\n" \
                    "Specific tile or radius rendering: if you need a single tile for offline use or custom rendering, request one exact tile URL using the desired z/x/y coordinates. For a radius-based view, compute the tile range that covers the radius and request the corresponding tiles from `/tiles/{z}/{x}/{y}.pbf`.\n\n" \
                    "This server returns standard Slippy map Web Mercator tiles generated from the Philippines PostGIS OSM database. Responses are gzipped and ETag-cached, so repeated tile requests can return 304 Not Modified. Use this endpoint wherever vector tiles are consumed in your website or mobile map stack.",
                "operationId": "get_tile",
                "parameters": [
                    {
                        "name": "z",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer", "minimum": 0, "maximum": 28},
                        "description": "Zoom level (0-28)"
                    },
                    {
                        "name": "x",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "Tile column (Web Mercator)"
                    },
                    {
                        "name": "y",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "Tile row (Web Mercator)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Gzipped Mapbox Vector Tile",
                        "content": {
                            "application/vnd.mapbox-vector-tile": {
                                "schema": {"type": "string", "format": "binary"}
                            }
                        }
                    },
                    "304": {
                        "description": "Not Modified (cached via ETag)"
                    }
                }
            }
        },
        "/cities": {
            "get": {
                "tags": ["Reference"],
                "summary": "List cities and municipalities",
                "description": "Get list of all cities and municipalities in the Philippines database",
                "operationId": "list_cities",
                "responses": {
                    "200": {
                        "description": "Array of city records",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "cities": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "admin_level": {"type": "integer"},
                                                    "lon": {"type": "number"},
                                                    "lat": {"type": "number"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/meta": {
            "get": {
                "tags": ["Metadata"],
                "summary": "Get API metadata",
                "description": "Get API version and information",
                "operationId": "get_meta",
                "responses": {
                    "200": {
                        "description": "API metadata",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "version": {"type": "string"},
                                        "description": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/fonts/{fontstack}/{range}.pbf": {
            "get": {
                "tags": ["Fonts"],
                "summary": "Get glyph font data",
                "description": "Get Mapbox-compatible glyph font for text rendering",
                "operationId": "get_fonts",
                "parameters": [
                    {
                        "name": "fontstack",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Font stack (e.g., 'Noto Sans Regular')"
                    },
                    {
                        "name": "range",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Unicode range (e.g., '0-255')"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Glyph font data (PBF format)",
                        "content": {
                            "application/x-protobuf": {
                                "schema": {"type": "string", "format": "binary"}
                            }
                        }
                    },
                    "404": {
                        "description": "Font not found"
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "Address": {
                "type": "object",
                "properties": {
                    "unit": {"type": "string"},
                    "block": {"type": "string"},
                    "lot": {"type": "string"},
                    "house_number": {"type": "string"},
                    "building": {"type": "string"},
                    "road": {"type": "string"},
                    "neighbourhood": {"type": "string"},
                    "suburb": {"type": "string"},
                    "district": {"type": "string"},
                    "city": {"type": "string"},
                    "county": {"type": "string"},
                    "state": {"type": "string"},
                    "region": {"type": "string"},
                    "postcode": {"type": "string"},
                    "country": {"type": "string"},
                    "country_code": {"type": "string"}
                }
            },
            "SearchResult": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "lon": {"type": "number"},
                    "lat": {"type": "number"},
                    "min_lon": {"type": "number"},
                    "min_lat": {"type": "number"},
                    "max_lon": {"type": "number"},
                    "max_lat": {"type": "number"}
                }
            }
        }
    },
    "tags": [
        {"name": "Geocoding", "description": "Reverse geocoding operations"},
        {"name": "Search", "description": "Location search"},
        {"name": "Debug", "description": "Raw data inspection"},
        {"name": "Tiles", "description": "Vector tile data for maps"},
        {"name": "Reference", "description": "Reference data"},
        {"name": "Metadata", "description": "API information"},
        {"name": "Fonts", "description": "Font glyphs for rendering"}
    ]
}


@docs_bp.route('/openapi.json', methods=['GET'])
def openapi_spec():
    """Serve OpenAPI specification"""
    return jsonify(OPENAPI_SPEC)


@docs_bp.route('/docs', methods=['GET'])
def swagger_ui():
    """Serve Swagger UI documentation"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Philippines Reverse Geocoding API - Swagger UI</title>
        <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui.css">
        <style>
            html {
                box-sizing: border-box;
                overflow: -moz-scrollbars-vertical;
                overflow-y: scroll;
            }
            *, *:before, *:after {
                box-sizing: inherit;
            }
            body {
                margin: 0;
                padding: 0;
                font-family: sans-serif;
            }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@3/swagger-ui-standalone-preset.js"></script>
        <script>
            const ui = SwaggerUIBundle({
                url: "/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                onComplete: function() {
                    console.log("Swagger UI loaded");
                }
            });
            window.ui = ui;
        </script>
    </body>
    </html>
    """
    return html, 200, {'Content-Type': 'text/html'}
