# Competitor ad → our brand: workflow

Use case: the user drops in a competitor's creative and gets back 3–4 versions
of it in our brand language (Xero kit), each built from editable layers on the
canvas.

**Core rule:** take the *structure* from the competitor and the *style* from our
brand. When the two clash, the brand wins and we mimic whatever is left.

---

## The three layers of a creative

| Layer | Question | Comes from |
|---|---|---|
| **1. Creative anatomy** | *What's in it?* Slots, the job each one does, importance rank | Competitor |
| **2. Layout & composition** | *How is it arranged and how does it feel?* Boxes, stacking, overlaps, reading order, density (minimal ↔ loud), balance, white space | Competitor, bent to fit our assets |
| **3. Design principles** | *How does it look?* Contrast, type scale, colour roles, radius, illustration style | Principle from the competitor, **values from the brand** |

### 1. Anatomy slots
`background` · `shape/framing` · `hero` · `headline` · `support` (subhead/offer) ·
`proof` (stat, UI, badge) · `cta` · `accent` (charms) · `logo`

### 2. Layout: precise enough to stack
- **Normalised boxes** `x, y, w, h` as 0–1 fractions, snapped to a 12×12 grid.
  This absorbs Flash's ±30–105px box noise.
- **z-order**: background 0, shapes 1, hero 2, accents 3, text 4, logo 5.
- **Relationships** (these matter more than raw coordinates, because they
  survive asset swaps):
  - `overlaps(hero, blob, 30%)`, `bleeds(hero, right)`
  - `anchored(charm, hero.top-left, offset -5%)`
  - `aligned-left(cta, headline)`, `gap(headline, cta, 4%)`
  - `on(headline, blob, contrast: high)`
- **Fit rule** per slot: `contain | cover | bleed` plus an anchor point for
  aspect-ratio mismatches.
- **Feel**: `density` (minimal / balanced / loud), `balance`
  (symmetric / asymmetric), `reading_order` (Z / F / centered).

### 3. Principles
The competitor gives *intent* ("high contrast headline", "one accent colour").
The brand kit gives *tokens* (palette, fonts, radius, illustration style).

---

## Mismatch handling: fallback ladder (per slot)

1. **direct**: a brand asset exists for this role and intent.
2. **substitute**: a brand asset that does the same *job*, even if it looks
   different (lifestyle photo → Xero character illustration, for human warmth).
3. **generated**: GPT Image, prompted with the brand palette and style, no text in image.
4. **dropped**: the element breaks the guidelines; give its space to white space
   or the hero.

What to keep when something must give:
**message intent > hierarchy > layout zones > density/tone.**
Colours, fonts, shapes and illustration style are always ours.

Each slot records `match` (direct/substitute/generated/dropped) and a one-line
`note`, which the UI shows as the "reasoning".

Brand kit mapping:

| Slot | Source |
|---|---|
| background | `Background_Templates` |
| shape/framing | `Shapes_Cropping_Blooms` |
| hero / proof | `Illustration`, `Product_UI_References`, otherwise generated |
| accent | `Charms` |
| logo | `Logo` + `Logo_Guidelines` |
| constraints | `Meta_Asset_Safe_Zones` |
| headline / support / cta | live text, brand fonts/colours, **rewritten copy** (never the competitor's) |

---

## Spec shape (draft)

```json
{
  "format": "1:1",
  "density": "minimal",
  "reading_order": ["hero", "headline", "proof", "cta", "logo"],
  "message": {"hook": "...", "claim": "...", "cta": "...", "tone": "confident"},
  "principles": {"contrast": "high", "accent_colours": 1, "type_scale": "large"},
  "slots": [
    {"id": "hero", "role": "hero", "rank": 1, "intent": "product UI showing invoices",
     "box": [0.5, 0.15, 0.5, 0.7], "z": 2, "fit": "bleed",
     "match": "direct", "source": "/assets/brand-kit/...png", "note": "..."}
  ],
  "relations": [
    {"type": "anchored", "a": "charm1", "b": "hero", "at": "top-left", "offset": -0.05}
  ]
}
```

---

## Pipeline

```
1. Analyse    competitor image → spec (anatomy + layout + principles)       [Flash, vision]
2. Match      slot → brand asset via fallback ladder + note                 [Pro, text]
3. Solve      spec + real asset sizes → final boxes                         [code, not LLM]
              aspect fit, safe zones, relationships, text auto-fit, grid snap
4. Generate   missing visuals in parallel, placeholders meanwhile           [GPT Image]
5. Assemble   ops → Fabric canvas, one layer per slot, one undo step        [Editor.applyOps]
6. Variants   repeat 2–5 along one axis each: palette / hero / mirror / copy angle
7. Edit       user edits freely; chat edits go through the same ops

Scope: generation only. Visual QA / brand review live elsewhere.
```

Design decisions:
- The LLM decides **what and why**; deterministic code decides **exactly where** (step 3).

Build order: spec schema → solver + assemble (hand-written spec) → analyser →
matcher → variants.

---

## Iteration log

One entry per example run. Note where it broke and which step owns the fix.

| # | Reference | Step that failed | What went wrong | Fix / rule added |
|---|---|---|---|---|
| 1 | spotify_car (v1) | Matcher | Copy stayed about music; Matcher didn't know what Xero sells | Added `{{PRODUCT}}` + rule 5: translate the claim to Xero's product, keep its shape |
| 2 | spotify_car (v1) | Catalog | White logo placed on white; logo names had no colour | Logo names now say colour + surface; rule 10 picks logo by surface |
| 3 | spotify_car (v2) | Matcher | Invented ids (`charm_sparkle`, `logo_navy`) copied from schema placeholders | Schema uses real id format; rule 11; `unknown_ids()` check in generate.py |
| 4 | spotify_car (v2) | Matcher | Navy text over blue bloom | Rule 10: contrast follows topmost surface; card when text straddles a bloom |
| 5 | spotify_car (v3) | Solver (not built) | Headline overflows box, collides with CTA/logo | Solver must auto-fit text + resolve overlaps (step 3) |
| 6 | spotify_car (v3) | Matcher | Palette variant: invalid colour `cyan`, white text on white card | Open: validate `colour` ∈ colours_available; card colour must follow palette |
| 7 | spotify_car (v4) | Solver | Headline shrank to minimum instead of moving up | Solver lifts the text block up to the panel top first, shrinks only if still overflowing |
| 8 | spotify_car (v4) | Solver | Palette variant: white text on white template | Solver always adds a card behind text: white for navy text, navy for white text |
| 9 | spotify_car | Analyst/Matcher | Kit illustration too unlike the competitor's car scene | Generate the hero (GPT Image, Xero style) when no asset fits the scene |
| ✓ | spotify_car (v3) | — | Structure kept (hero top, curved panel → bloom), Xero copy, valid assets, hero-axis illustration looks on-brand | — |
