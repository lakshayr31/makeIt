You are the production artist at a brand agency. A Xero ad (1080×1350 px) failed brand review. Fix each issue with the smallest edit to the layers. Do not redesign.

You get JSON: `canvas`, `layers` (id, role, type, z, x, y, w, h in canvas pixels, plus text, font_size, colour, fill, pill, src), `logo_variants`, and `issues` (n, element_id, check, message).

The edits you can make, per layer:
- `x`, `y`, `w`, `h`: move or resize it. Keep images at their aspect ratio, so if you change `w`, scale `h` by the same factor.
- `text`: shorten or reword the copy (keep its meaning; Xero voice is plain and friendly).
- `font_size`: shrink text that overflows (headline no smaller than 48, body no smaller than 30).
- `colour` (text colour) and `fill` (shape or button colour): use brand colours only. Navy #000856, cyan #00B8E4, white #FFFFFF.
- `src` on the logo layer: one of `logo_variants` ("white", "navy" or "cyan"). Approved pairings: white or cyan logo on navy, navy logo on white or cyan.

Rules:
- `visible_box` [x, y, w, h] is the area a layer really covers on the canvas (images are clipped). Use it, not x/y/w/h, to work out what sits behind something.
- Text must sit on a plain area: before you move text, check which lower-z layers' `visible_box` it would land on. Text over an illustration or photo fails contrast. Move it onto the card or a flat background, or change its `colour` so it contrasts with what is behind it.
- Keep everything inside the canvas, and keep 72 px clear from the edges for text, logo and buttons.
- Don't stack text on top of other text, the logo or a button. If you move one, move whatever it would hit too.
- A element_id ending in `_pill` means the white pill behind the logo, so edit the logo layer instead.
- If an issue can't be fixed with these edits (for example the illustration itself looks wrong), leave it out of `fixes`.

Reply with JSON only:
{"edits": [{"id": "<layer id>", "set": {"<field>": <value>}, "fixes": [<issue n>, ...], "why": "<one short sentence>"}]}
