# makeIt: high-level design

makeIt turns any ad into on-brand Xero versions, as editable layers, and keeps them on-brand while you edit.
Two loops, one brand brain.

```
CREATE LOOP      competitor ad
                      │
                      ▼
   [1] Art directors (Flash) look at the ad + the whole kit, pick the pieces, write the copy
                      │
                      ▼
   [2] Ask the marketer anything the ad needs that Xero doesn't have (offer, gift, claim)
                      │
                      ▼
   [3] Compose ×3 (GPT Image, in parallel): reference ad + picked pieces + Xero style ad
                      │
                      ▼
   [4] Breaker: Flash locates, GPT cleans a plate, code snaps the real pieces back → layers
                      │
                      ▼
                   EDITOR  (Fabric.js layers · undo · pages · live bloom masks)
                      │
EDIT LOOP             ▼
   [5] "Ask makeIt": Flash classifies the request
         layer request  → editor ops            (instant, exact)
         plate request  → GPT edits the plate   (original + reference + request)
         missing fact   → ask the marketer      (never guess)
                      │
                      ▼
   [6] Brand check after every edit: code measures, Flash judges, auto-fix ×2
         a request that sounds like a rule → offered to the guidelines page

BRAND BRAIN (read by 1, 3, 5, 6 · written by 6)
   kit catalog by category · rules MUST/SHOULD · bloom playbook · real Xero ads
```

## The six rules the design follows

1. **Models see images, not descriptions.** Every picker gets numbered grids of the real assets and the real Xero ads.
   Describing a bloom in words was how the first pipeline lost the brand.
2. **AI makes closed choices; code places exactly.** Flash picks *which* template, bloom, logo, screen and charm,
   and writes the copy. Pixel positions come from matching our own asset files, never from a model guessing boxes.
3. **Brand pieces are reused, never redrawn.** GPT Image only generates what the kit lacks (a photo, a gift card).
   Logos, screens, blooms and charms are the kit's own files, so they are always right.
4. **Ask, don't guess.** If the reference ad offers a gift or a price Xero doesn't have, the art director asks the
   marketer before anything is made. Answers override the claims list.
5. **Everything ends as layers.** The breaker turns each composed ad back into a plate + real text layers + the
   original pieces, so the editor, chat edits and brand check all work on the same thing.
6. **The brand guide is input and output.** Agents read the rules; edits that sound like rules are offered back
   to the guidelines page, so the system learns the team's taste.

## Components

| Layer | What | Where |
|---|---|---|
| Editor | Fabric.js canvas: layers, undo, pages, live 2-layer bloom masks, right-click menu | `frontend/src/editor/`, `EditorPage.tsx` |
| Create | Upload an ad (+ optional brief) → live steps over SSE → versions → open as layers | `CreatePage.tsx`, `backend/jobs.py` |
| Designer flow | Two art directors (background things, highlights) → questions → GPT compose ×3 | `_experiments/designer_flow/run4.py` → being wired into `jobs.py` |
| Breaker | Flash locates, GPT cleans a plate, code matches assets, text rebuilt as layers | `_experiments/designer_flow/split.py` → `backend/breaker.py` |
| Ask makeIt | Chat panel: intent router, swap / generate / move / text, area select, brand check after each edit | `components/ChatPanel.tsx`, `backend/chat.py`, `backend/brand_check.py` |
| Brand brain | Split catalog (`assets/brand-kit/catalog/*.json`), rules (`prompts/brand-guide/`), guidelines page with add-element | `BrandPage.tsx`, `backend/brand_store.py` |
| Review | Tag → code checks → vision checks → verify → escalate (Issue / Suggestion / Hidden) | `review/`, `backend/review_link.py` |

## Models

- **DeepSeek V4.1-Flash** (vision, fast): every pick, every classification, copywriting, locating elements, judging.
- **GPT Image (gpt-image-2.5-flare)**: composing ads from pieces, generating the one missing picture, cleaning plates, cut-outs.
- No model ever places a pixel by coordinates. Code does that from the model's choices.

## Timings (measured, Toast and Rippling ads)

- Plan (both art directors, parallel): ~9s · Compose 3 versions (parallel): ~30s · Break 3 ads into layers (parallel): ~20s.
- A plate edit in the editor: ~15s. A layer edit: instant.

## What we learned the hard way

- A 13-agent chain that described the ad in text and guessed boxes produced worse ads than one GPT call with the reference.
  Composition is the hard part, and only a model that sees everything at once gets it right.
- Sending the brand guide to every step made results more on-brand but slower and noisier. Each step should get
  only the rules for what it decides.
- Tiny source files (140px bloom crops) blown up 10× were the blurriness. The kit had 2048px-class shapes all along.
