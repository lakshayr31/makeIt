# Layout and safe zones

Ads are laid out on a 12 x 12 grid (boxes in 1/12 steps, values 0-1 of canvas width/height). Copy stacks left-aligned; brand shapes bleed off the edges; essential content stays inside Meta's safe zones.

## Rules

**LY1 MUST: Meta safe zones: nothing essential (text, CTA, logo) in the top or bottom 1/12 (8.3%) of the canvas.**
- How to apply: for every text, CTA, proof and logo box, y >= 0.083 and y + h <= 0.917. The default logo box [0.083, 0.833, 0.25, 0.083] clears this exactly. Also keep these boxes at least 6% from the left and right edges (observed top margin is 6%).
- Not essential: background templates, blooms and photos may (and should) bleed through the safe-zone margins.
- Why: Meta overlays profile, captions and buttons on the edges; content there gets covered.

**LY2 SHOULD: 9:16 Stories/Reels: keep text, CTA and logo clear of the top ~14% and bottom ~21% UI overlays (observed); keep generous white space.**
- The safe-zone page (portrait) marks: 6% top margin, 14% offset at the top-right, 21% bottom margin, and large side margins (35% left / 40% right marked around the right-hand action buttons). These are observed from one portrait reference; landscape and square values are unconfirmed, so LY1 is the hard floor and LY2 the portrait best practice.
- White space: elements never crowd each other or touch the canvas edge (except bleeding blooms/templates). Leave at least one grid unit (1/12) between text blocks and the hero.

## Composition principles
- Reading order top to bottom: headline, support, CTA; hero and brand shape share the remaining area. Logo at the bottom (left by default).
- Left-align text; headline, support and CTA share a left edge.
- Use organic curves (template wave or bloom) to divide the space and create movement; one dominant shape is usually enough.
- Preserve relative sizes when adapting a layout: the most important element stays the largest.
- Re-flowing to a different aspect: stack slots top to bottom in reading order, keep left alignment, re-check LY1.
- Busy surfaces under text need a card (TY4); the logo needs a pill (LG3).

## Formats
- 1:1 square, 4:5 portrait feed, 9:16 Stories/Reels, 16:9 landscape. Templates exist for 1:1 and 9:16 in the catalog (see template topic).

## Source pages
- assets/brand-kit/17_Meta_Asset_Safe_Zones/17_Meta_Asset_Safe_Zones/01_1ff2bdc3-da9f-46cb-b99f-045689144ba5_download.webp
- assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/07_07_examples.png
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/01_xero_wordmark_primary.png
