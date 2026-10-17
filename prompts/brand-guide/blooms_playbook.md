# Xero blooms playbook

The source is the 7 brand-book pages in `06_Shapes_Cropping_Blooms` (01–07). Blooms are Xero's main graphic device, so every agent that composes, edits or reviews a design reads this in full. Each technique below gives what it is, when to use it, its parameters, and its don'ts. Canvas fractions refer to the ad canvas (1.0 = full width or height).

## 0. What a bloom is (page 01 intro, page 02 set)
- Organic, rounded, single-colour flat shapes inspired by the New Zealand fern. They stand for growth, energy and optimism. "Crafted with intention. Built for expression. Yours to push, play with and bring to life."
- There are 12 named shapes, each with a personality. Pick one by the feeling you want:
  - Peace: calm lozenge with a notch, for steady, reassuring messages
  - Energy: two joined circles, for friendly, simple claims
  - X: four-lobed cross, playful and attention-grabbing
  - Spark: jagged zig-zag, for bold, fast, excitement
  - Grow: long rising wedge, for progress and upward movement
  - Pulse: lightning zig-zag, for speed and urgency
  - Harmony: rounded teardrop with a curl, soft and caring
  - Motion: two offset strokes, for forward movement
  - Balance: wave with two lobes, for steady rhythm
  - Ease: hook plus a long tail, relaxed
  - Surge: S-loop, dynamic
  - Stride: W-wave, momentum
- Kit files: each shape exists as a large single-colour file in cyan (#40C8FF), bright blue (#2167D8) and navy (#030A55), plus a small sheet with all 7 colourways. Fills are flat, so any colourway is a straight recolour of the shape.
- Shapes are never distorted: scale them evenly and rotate them freely. Never stretch, outline, gradient or shadow them.

## 1. Bloom field: cropping inside frames (page 03, top)
- What: one bloom scaled so large that only part of its edge shows. That curve splits the frame into 2 flat colour zones (e.g. bright blue and white). It reads as a sweeping curve, not as a shape.
- When: backgrounds; any time you want movement and energy without a picture; text-led ads.
- Parameters:
  - scale 3–6× the frame width, so the visible edge is one smooth sweep with at most one lobe or droplet
  - the split is roughly 40/60 to 60/40 between the two colours
  - the curve enters and leaves through frame edges and never closes inside the frame
  - 2 colours: a saturated one (bright blue, navy, pink, cyan) plus white or another flat colour
- Text goes on the calmer, larger zone, fully inside one colour and never straddling the curve.
- The background templates (page 04) are ready-made bloom fields. Use one when the format matches.
- Don't: show the whole bloom; show more than one lobe in small frames; put a tiny bloom in the middle of a frame.

## 2. Frame break: cropping that breaks the frame (page 03, bottom)
- What: a rounded-rectangle frame (a photo, card or colour panel, corner radius ≈ 3–4% of its width) sits ON TOP, with a second bloom in a contrasting colour BEHIND it that peeks past 1–2 of its edges.
- When: to add depth and a stronger sense of motion to a framed photo or card.
- Parameters:
  - the bloom is behind the frame (lower z), never in front of the photo subject
  - it shows past the frame by about 5–12% of the frame size on 1–2 sides (often one long side + one corner)
  - it is still large (2–4× the frame) so only a curve shows, not the whole shape
  - its colour contrasts with both the frame and the background (e.g. cyan behind bright blue, yellow or pink behind a photo on navy)
- Don't: let the bloom peek out on all 4 sides (it reads as a border); use the same colour as the frame; put it in front of faces.

## 3. Background templates (page 04)
- What: ready-made bright-blue + white bloom fields in 3 formats, 1:1 (9), 9:16 (9) and 16:9 (6). Every template is a bloom crop, with the blue cut by the canvas edges.
- When: the quickest correct background; good for lower-funnel or text-led ads.
- Parameters:
  - pick the template in the output's format; for 4:5 use a 1:1 or 9:16 one, cropped so the curve still crosses the frame
  - never stretch a template
  - text sits in the large white area (navy text) or fully in the blue area (white text)
- Don't: add strokes, gradients or shadows; recolour the blue to off-palette colours.

## 4. Patterning (page 05)
- What: 3–6 blooms layered and cropped over a navy base, filling the frame like a texture.
- When: only with clear intent, where it adds meaning, supports the message or improves the composition; e.g. a bold awareness ad with very little copy. Never as decorative filler.
- Parameters:
  - at most 3 colours on navy; seen sets are purple + cyan + bright blue, bright blue + navy tones, and green + mid-blue
  - the blooms are consistent in form and orientation (they flow the same way)
  - most blooms are cropped by the canvas edges
- Don't: put text directly on a pattern (use a card or a calm panel); mix more than 3 colours; scatter small isolated blooms.

## 5. Blooms in photography (page 06): two ways
- A) Photo cropped INTO a bloom (top row): the photo is masked by a large bloom on a flat field (navy). The bloom silhouette is the photo's edge, and the subject may slightly break out of the mask (head, hand, product) for depth.
  - When: out-of-home, campaign, top-of-funnel.
  - Parameters: the bloom-shaped photo covers about 45–70% of the canvas; the subject's face sits inside the mask; the bloom may bleed off 1 edge; the field behind is flat (navy most often).
- B) Framed photo + bloom (bottom row): the photo sits in a rounded-rectangle frame, with a bloom in a contrasting colour (cyan, yellow, pink) behind it, breaking past the frame (technique 2).
  - When: mid and lower funnel, product and feature ads, or any time the photo needs to stay a clean rectangle.
- Don't: crop through faces or key product details; use more than one masked photo per ad.

## 6. Examples: how the techniques combine in finished ads (page 07)
- Sweeping curves across backgrounds: a bloom field (technique 1) in 2 strong colours (e.g. pink field + navy curves) with a big bold headline in the calm zone. It can also hold a white stat card overlapping the curve.
- Cropping imagery and adding movement: a photo cropped by a bloom crossing its corner, or a framed photo with a bloom behind (technique 2). A white rounded text box may overlap the photo edge.
- Framing assets and featuring the logo: a blue or navy field with the photo cut by a large bloom curve; the Xero wordmark sits on a bloom lobe or corner of its own colour (e.g. white wordmark on a pink bloom bottom-left, or a navy wordmark on a white lobe).
- Common to all: elements overlap on purpose (a card over the curve, a chip over the photo); one dominant curve per ad; 2–3 colours in total; the headline is the largest type.

## 7. Funnel rule (page 03 text)
- Top of funnel, out-of-home and advertising: go bold, with bigger crops, more colour (up to 3 bloom colours), photo in bloom, layering.
- Lower funnel and internal: simpler, with fewer colours, cleaner curves (Peace, Energy, Harmony, Grow) and often a template.

## How agents express this in our layout
- bloom field: `background.type: "bloom_field"` with 2 colours and scale 3–6, or `template`
- frame break: `visual.treatment: "framed_bloom_break"`; bloom role `behind_visual`, scale 2–4, peeking past 1–2 sides
- photo in bloom: `visual.treatment: "in_bloom"`; bloom role `mask`, scale 1.2–2.0 so the photo shape is mostly visible, bleeding 0–1 edges
- pattern: `background.type: "pattern"`, 3–6 blooms, ≤3 colours, navy base, text on a card
- accent blooms: scale ≥ 1.0 and bleeding; never a small shape floating mid-canvas
