# Photography

There are two ways to use photography in Xero assets: cropped into a bloom, or framed with a bloom breaking the frame. Photos show real, candid small-business owners at work, warm and natural light.

## Rules

**PH1 MUST: Top-of-funnel/campaign photos are cropped into a bloom mask; the subject may subtly break the mask for depth.**
- How to apply: give the photo the `hero` slot with `fit: cover` and pair it with a bloom `shape` slot whose `mask_of` names the hero; the renderer clips the photo to the bloom. Place the mask on a flat navy, cyan or white field.
- Subject breaking the mask: a head, hand or object may cross the bloom edge slightly. Keep it subtle; most of the subject stays inside.
- Edge cases: the mask still follows BL1 where possible (a lobe touches an edge). Never put the photo in a plain rectangle in a top-of-funnel ad without either PH1 or PH2.
- Why: cropping photography into blooms is the book's prescribed treatment for out-of-home, campaign and top-of-funnel.

**PH2 SHOULD: Alternative: a rounded-corner framed photo with a bloom breaking out behind or across the frame edge.**
- How to apply: photo in a rectangle with rounded corners, on a flat field; one bloom sits behind it and extends beyond the frame (and ideally off the canvas). The bloom carries the brand when the photo itself is not masked.
- Best for mid/lower funnel, editorial and multi-element layouts where an unmasked photo reads more clearly.

## Text and logo on photos
- Never place headline, CTA or logo directly on a photo. Use a white card or flat field under the text (TY4) and a pill for the wordmark (LG3).

## Photo style (when generating or choosing)
- Real people, candid, smiling or focused, small-business settings (shop, studio, cafe, outdoors). Natural light. No staged stock poses, no text in the image.
- If no suitable photo exists, fall back to a kit illustration (substitute) before generating; generated imagery follows the illustration style unless a photographic look is explicitly needed.

## Catalog assets
- The catalog has no photo kind. `product_ui-01` and `product_ui-06` include photographic context (kitchen counter, hand) and can stand in. Otherwise photos are generated or supplied.
- Masks come from kind `bloom` (12 shapes x 7 colourways).

## Source pages
- assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/06_06_blooms_in_photography.png
- assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/03_03_cropping_and_frames.png
- assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/07_07_examples.png
