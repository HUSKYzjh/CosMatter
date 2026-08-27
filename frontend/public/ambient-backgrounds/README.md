# CosMatter ambient background assets

All files in this directory are generated original line-art overlays with RGBA alpha. They are intended to be placed above a theme background and below interactive UI content. Every asset was generated on a flat chroma-key background and processed locally to remove the key colour; a one-pixel transparent safety border is present on all four sides.

| Group | Count | Purpose |
| --- | ---: | --- |
| `fleet/` | 5 | Research flagship, fleet formation, flotilla, expedition ship, survey craft. |
| `starfield/` | 5 | Constellation, horizon, scan, sector, and crystal-lattice navigation overlays. |
| `facility/` | 5 | Orbital laboratory, characterization campus, data observatory, synthesis bay, and remote outpost. |

The editable keyed source images are retained in `../background-sources/` with matching names. The files in this directory are the frontend-ready transparent assets.

Generation method: built-in image generation with a flat `#ff00ff` chroma-key background, followed by local `remove_chroma_key.py` processing with a soft matte, despill, and a one-pixel edge cleanup. The images contain no text, logos, or external IP.