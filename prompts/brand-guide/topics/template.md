# Background templates

Templates are ready-made backgrounds: a white canvas with one large solid blue wave (sometimes with rounded droplets or lobes) cropped by the canvas edges. They are the quickest on-brand background and leave a large white area for copy.

## Rules

**TP1 MUST: Background templates are solid blue + white waves cropped by the canvas edges; add no strokes, gradients, shadows or textures.**
- How to apply: use the template PNG as-is, full-bleed (`fit: cover`, box [0,0,1,1]). Do not add outlines or effects, and do not recolour the blue.
- Edge cases: blooms, photos, UI and charms may be layered on top. Keep the template's blue wave anchored to an edge; never crop so the wave becomes an enclosed island.
- Why: the brand book shows only solid blue and white, the wave always bleeding off the canvas.

**TP2 MUST: Pick the template whose format matches the output (1:1, 9:16, 16:9); never stretch one to fit.**
- How to apply: 1:1 output: a square template (aspect 1.0). 9:16 output: a portrait template (aspect 0.563). 16:9: the book defines landscape templates, but none are in the catalog; use a flat field + bloom instead, or crop a square template with `cover` only if the wave still bleeds off an edge.
- 4:5 output: crop a 1:1 template with `cover` (loses ~10% top/bottom); check the white text area still exists after the crop.
- Never distort the aspect ratio.

**TP3 MUST: Put text on the template's white area (navy text); white text only if it sits fully on the blue area.**
- How to apply: read the asset's `text_safe_area` (e.g. "top 60% plain white") and put headline, support and CTA there. Logo on white: navy wordmark. Some templates offer a large solid blue area ("top 50% plain blue"); white text or a white/cyan wordmark can sit there.
- Edge cases: if a text box crosses the wave edge (part white, part blue), move it, shrink it or add a white card under it (TY4).

**TP4 SHOULD: Template blue is approx. #2E5BFF (observed) and is not navy.**
- The source extracted #2E5BFF from one page; individual PNGs render #1B6BE0 to #2E6BE6. Treat it as a saturated mid-blue: white text works on it, navy text does not reliably. Do not set `background_colour` to navy expecting it to match the template.

## Catalog assets
- kind `background_template`, 18 assets (`background_template-01` .. `-18`): 9 square (aspect 1.0: 01, 02, 03, 05, 06, 08, 09, 10, 11) and 9 portrait 9:16 (aspect 0.563: 04, 07, 12-18). No landscape assets.
- Every template has a `text_safe_area` description; use it to place copy.
- Palette alternatives: for a navy-led look, use a flat navy field + a bloom instead of a template (templates are white-led).

## Source pages
- assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/04_04_background_templates.png
- assets/brand-kit/24_Background_Templates/24_Background_Templates/04_4bd578f8-72e9-4ed3-9361-d7642f371d5a.png
- assets/brand-kit/24_Background_Templates/24_Background_Templates/01_4c697152-6594-4ae4-b069-d5cddec06d2e.png
