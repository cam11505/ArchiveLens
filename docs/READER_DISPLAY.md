# Reader display policy (v1.2)

ArchiveLens applies fit, rotation and trimming only to the in-memory display. It
never writes these operations to an archive, image, folder or PDF source.

## Fit and zoom

- **Fit Page/Spread** (`0`) fits both dimensions.
- **Fit Width** (`2`) fills the viewport width and allows vertical scrolling.
- **Fit Height** (`3`) fills the viewport height and allows horizontal scrolling.
- **Actual Size** (`1`) maps one rendered/image pixel to one physical display pixel.
- User zoom switches to a custom mode. Resizing preserves a selected fit mode and
  recalculates its scale; it does not reset the logical page or reading position.
- PDF viewport and device-pixel-ratio changes request a fresh bounded QtPdf render.
  Fit Width and Fit Height request enough pixels along their fitted axis.

The selected mode, custom zoom and rotation are stored per source in the local
reading-state file. Passwords and rendered images are not stored.

## Border trimming

- **Off** displays the complete decoded/rendered page.
- **Auto** recognizes only neutral, low-variance, near-white or near-black outer
  borders. It inspects a maximum 512-pixel-long preview, trims at most 20 percent
  from each edge and keeps at least 60 percent of both dimensions. Ambiguous pages
  are deliberately left unchanged.
- **Manual** uses independent left/top/right/bottom percentages, each bounded to
  0–40 percent. Invalid margins fall back to the complete page.

Trimming runs only for displayed pages; it does not eagerly scan the book. For PDF,
auto/manual trim uses the current bounded raster render and is recalculated after a
fresh render. Animated GIF frames reuse the crop rectangle established from the
first frame. Trim mode and manual percentages are stored per source.
