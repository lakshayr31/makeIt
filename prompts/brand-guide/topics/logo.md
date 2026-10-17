# Logo

The Xero wordmark is lowercase "xero" in a custom rounded geometric sans, bold. It is always a supplied asset, never typed or redrawn.

## Rules

**LG1 MUST: Every ad carries the lowercase xero wordmark asset with clear space; never redraw, recolour, stretch or add effects.**
- How to apply: use a `logo` catalog asset with `fit: contain`. Default position bottom-left, box about [0.083, 0.833, 0.25, 0.083] (clears the Meta safe zone exactly). Mirror variants move it bottom-right.
- Clear space: the wordmark never touches the edge or corner of its container, card or canvas (no exact ratio defined; leave at least the height of the "x" around it).
- No shadows, outlines, gradients, rotation or squashing. Never set the wordmark in a font.
- Edge cases: the brand book also shows the wordmark featured in a bloom-shaped or rounded colour tab in a corner; that is acceptable if LG2 contrast holds.

**LG2 MUST: Pair wordmark and surface: navy on white or cyan; white or cyan on navy or blue.**
| Wordmark | Surface | Contrast |
|---|---|---|
| Cyan #00B8E4 | Navy #000856 | 9.95:1 (primary) |
| Navy #000856 | Cyan #00B8E4 | 9.95:1 |
| Navy #000856 | White #FFFFFF | 17.96:1 |
| White #FFFFFF | Navy #000856 | 17.96:1 |
- Template blue / saturated blooms: use the white wordmark.
- Read the surface actually behind the logo (topmost layer), not just the background slot.

**LG3 MUST: On a photo or busy bloom area, put the wordmark in a fully rounded pill; no pill on a plain flat surface.**
- How to apply: `pill: true` gives a white capsule with the navy wordmark centred. Use it when the logo sits over a photo, pattern, or the edge where two colours meet.
- On a plain single-colour surface, no pill. "Busy" is a judgement call: if any part of the logo box covers two colours or image detail, use the pill.

**LG4 MUST: Co-brand: Xero left, partner right, "+" between, partner never larger than the Xero wordmark.**
- Align partner logo to the same visual height as the wordmark. Solid single-colour container only.

## Catalog assets
- kind `logo`, 3 assets: `logo-01` white wordmark (for navy/blue), `logo-02` navy wordmark (for white/light), `logo-03` cyan wordmark (for navy).

## Source pages
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/01_xero_wordmark_primary.png
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/02_xero_wordmark_accessibility.png
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/03_xero_online_presence.png
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/04_xero_pill_restricted.png
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/05_xero_products_partnerships.png
- assets/brand-kit/10_Logo/10_Logo/01_0f4c5387-a60d-4a27-93e8-9f5223676154.png
- assets/brand-kit/10_Logo/10_Logo/02_2f020a69-e294-4971-b448-760f8b1827ad.png
- assets/brand-kit/10_Logo/10_Logo/03_a6d69555-61d3-43ba-a7ab-e38d56a3805c.png
