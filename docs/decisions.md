# makeIt — decisions log

Hackathon: GetCrux "Agentic Image Editor", 17 Oct 2026. Judging: output quality > system design > speed/features > UI/UX > presentation.

## Decided

| # | Decision | Why |
|---|---|---|
| 1 | **Editor = Fabric.js + our own thin React UI** | MIT, commercial use, we own the code. Polotno/tldraw need paid licences; Doory forces a launch banner and brings Django/Postgres. |
| 2 | **Layer splitting = APIs only** (DeepSeek Flash + GPT Image Flare). SAM 2 parked. | Flare cut-outs are high quality and need no extra install. |
| 3 | **Brand rules doc generated** — Flash read all 103 brand-kit images (90s), Pro merged them (10.7 min). | Source of truth for generator + reviewer. Lives in `assets/brand-rules/` (git-ignored). |
| 4 | **Generator gets text rules only; reviewer also gets single-element example crops** (one bloom, one charm, logo-in-pill), scoped to one rule per check. | Full example designs would make every output look the same. |
| 5 | **Default to DeepSeek-V4.1-Flash for anything user-facing** | Pro took 10.7 min on the rules merge (hidden reasoning + shared endpoint). |
| 6 | **Brand kit, references, brief stay out of git** (`assets/`, `docs/brief/`, `.env` ignored) | Not ours to publish; brief has live keys. |

## What the API tests showed (Xero ad, `references/04_*`)

- **Flash** names every layer and its text correctly, but boxes are off by 30–100px (photo box started 105px low → head cut off). Asking for 0–1000 coordinates improved the photo box; curve outlines are still wrong.
- **Flare edit, transparent background** → clean, high-quality cut-out of the woman, but **redrawn**: resized, repositioned, hidden parts invented. Needs re-fitting into Flash's box.
- **Flare edit, "remove text/card/coins/logo"** → usable clean background plate, layout and photo curve kept.

## Planned pipeline (not built)

1. Flash → layer spec (types, text, rough boxes)
2. Flare → clean background plate
3. Flare → transparent cut-outs per object, scaled into Flash's box
4. Rebuild text/buttons as editable Fabric objects; swap logos/charms from the brand kit
5. Review loop: code checks (`brand-rules.json`) + Flash style check → fix → max 3 rounds

## Review system v2 (decided after first reviewer test)

**First test (v1 prompts, one big call per reviewer):** caught the cut-off head and cut logo; false alarm "badge covers Cashflow" caused by our own number labels; wrongly said hands were cut; missed the broken graph and a stray white bar; judged charms with illustration rules; "logo clear space: passed" was a guess.

**Principle:** look carefully once (at asset import), then measure. We generate the designs, so element boxes/crops are ground truth — most "is it broken" questions become geometry.

| Stage | Agency role | Runs | What it does |
|---|---|---|---|
| 1. Tag | Digital Asset Manager | Once per asset, cached | Flash on the full-size asset + grid → type + must-not-cut/cover regions (face, head, hands, product, text) |
| 2. Code checks | Production artist (preflight) | Every review, <1s | Cut-off subject, covered face/product/text, overlaps, off canvas, Meta safe zones (6% sides, 14% top, 35% bottom-left, 40% bottom-right), stretched / low-res images, text overflow, palette, fonts, logo pair, clear space, partner logo size, contrast |
| 3. Vision checks | Brand Guardian + Art Director | Every review, ~6s parallel | Flash, ONE call per element TYPE, clean close-up crops (no labels), that type's rules only, must fill `observations` before `verdict` |
| 4. Verify | Creative Director sign-off | ~2s parallel | Flash re-checks each vision finding: true / false + evidence; false ones dropped |
| Merge | Project manager / traffic | — | One list for the designer: auto-fixed ✅ / needs you 🔴 |
| Test set | Brand book + training | After every prompt change | Clean designs (expect 0 findings) + designs broken on purpose (expect each break found) → catch rate + false alarms per check |

**Cut for speed:** 3-vote majority → single verify; describe-then-judge in one call; per-element calls → per-type calls; hand-made broken set instead of a generator. **Not cut:** tagging, code checks, no labels on the design.

## Escalation (built)

score = rule strength (1.0 written · 0.8 universal defect · 0.5 observed · 0.3 taste) × verifier agreement (high-severity asked twice) × (1 − rule's false-alarm rate on the 20 good ads, leave-one-out, smoothed). ≥0.7 Issue · 0.4–0.7 Suggestion · <0.4 Hidden. Code findings are always Issues.
Calibration run (20 good Xero ads, ~17s each): 7 raw fails → 0 Issues, 4 Suggestions, 3 Hidden; 20/20 ads show no issue. Highest false-alarm rule: charm_style (17%). Not yet re-checked: whether escalation demotes real catches on the 12 broken test designs.

## Parked / open

- Review eval v2 (12 test designs): caught 10/11 planted defects, 0 false alarms on clean designs. Open fixes: merge duplicate findings per element; awkward-crop verdict flips on the same photo (cache per asset, stricter verifier — it dropped nothing); code check for stray thin shapes (missed). 45s request timeout added.
- Good-ad test (flat images, vision + verify only): 11_9795 → 0 issues; 09_88726 → 1 false alarm: ALL-CAPS product list ("ACCOUNTING • PAYMENTS…") failed `case_and_emphasis`. The rule is "(observed)" and too strict; the verifier confirmed the fact, not whether the rule applies. Parked.

- `brand-rules.json` (checkable values: palette, fonts, logo clear space, Meta safe zones) — not made yet.
- Spot-check two shaky rules in the doc: background blue "#2E5BFF approximate" (logo section says navy #000856); charm colour order cites an Illustration file.
- SAM 2 (Apache 2.0, tiny ≈150 MB + PyTorch) if Flare cut-outs fail to align.
- Brand panel in the editor = the visual guide + asset library.
