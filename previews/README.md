# Preview-Worker

Queue-basierter Service, der aus Original-Dateien Derivate (Thumbnails,
PDF/PNG-Previews) erzeugt. Originale bleiben unveraendert (immutable);
Derivate verweisen via preview_file_id auf ihr Original.

Geplante Phase M4:

| Format | Preview | Werkzeug |
|--------|---------|-----------|
| JPG/PNG/WebP | Thumbnail + Original | libvips |
| SVG/PDF | nativ im Browser | Content-Type |
| AI/EPS | PNG-Derivat | Inkscape headless / Ghostscript |
| PSD | PNG-Flat-Export | libvips (rastert Layer) |

Stack: Python-Worker (arq/Redis oder Postgres-Jobtabelle), libvips.
