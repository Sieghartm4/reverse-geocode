Generating glyph PBFs for MapLibre (quick guide)

This project expects glyph PBFs at `./fonts/{fontstack}/{range}.pbf`, for example:

fonts/Open Sans Regular/0-255.pbf
fonts/Open Sans Semibold/0-255.pbf

If a requested PBF is missing the server will now try to proxy to the MapLibre demo glyph server, but to fully fix missing glyphs you should generate and store them locally.

Recommended (Node.js) method

1. Install Node.js and npm (or use npx). On Windows, use WSL or PowerShell.

2. Install `fontnik` and `glyph-pbf-compress` (these are common tools used to generate glyph PBFs):

```bash
npm install -g @mapbox/fontnik glyph-pbf-compress
```

3. Generate ranges for a TrueType font (example uses Open Sans TTF file):

```bash
# create directory for the font
mkdir -p "fonts/Open Sans Regular"
# generate the 0-255 range
fontnik --output fonts/Open\ Sans\ Regular/0-255.pbf /path/to/OpenSans-Regular.ttf 0 255
# generate more ranges as needed (256-511, 512-767, ...)
```

Note: CLI names or package names may differ across systems; consult the package docs if the CLI name isn't available. An alternative is `node-fontnik` usage via a tiny Node script.

Alternative: use `glyphhanger` (subsets fonts) or online services to get PBFs.

What to place in the repo

- Create `fonts/<fontstack>/` directories and copy the generated `*.pbf` files there.
- Example layout:

```
fonts/
  Open Sans Regular/
    0-255.pbf
    256-511.pbf
  Open Sans Semibold/
    0-255.pbf
```

After adding files, restart the backend server and reload the frontend. The browser should stop logging 404s for glyph requests.

If you want, I can produce a small Node script to generate ranges automatically given a TTF file — tell me which font files you have and I will add the script.
