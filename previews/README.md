# Preview worker

Queue-based service that generates derivatives (thumbnails, PDF/PNG
previews) from original files. Originals stay unchanged (immutable);
derivatives reference their original via preview_file_id.

Planned phase M4:

| Format      | Preview            | Tool                        |
|-------------|--------------------|-----------------------------|
| JPG/PNG/WebP| Thumbnail + original | libvips                  |
| SVG/PDF     | native in browser  | content-type                |
| AI/EPS      | PNG derivative     | Inkscape headless / Ghostscript |
| PSD         | PNG flat export    | libvips (rasterizes layers) |

Stack: Python worker (arq/Redis or Postgres job table), libvips.
