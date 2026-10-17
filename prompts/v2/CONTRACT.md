# Review pipeline v2 — shared contract

Every prompt in this folder is a SYSTEM prompt for DeepSeek-V4.1-Flash (vision, OpenAI-compatible chat API, `response_format: json_object`).
Code builds the user message (text + images) and parses the JSON reply. Prompts must say "Return ONLY JSON" and give the exact schema.

## Element types (closed set)
`text` · `button` · `logo` · `photo` (a person or scene photo / cut-out) · `product` · `bloom` (Xero organic brand shape, also used as a photo mask) · `charm` (small 3D-ish sticker icons, e.g. coins) · `illustration` · `card` (UI card like "Cashflow £12,500") · `icon` (small glyph or badge, e.g. a checkmark disc) · `decoration` (sparkles, motion lines, small accents) · `background`

## Stage 1 — tagger.md (once per asset)
User message: asset filename + folder, and ONE image: the asset at full size with an 8x8 grid drawn on top; columns A–H left→right, rows 1–8 top→bottom; each cell labelled (A1 … H8).
Reply:
```json
{"asset_type": "photo|product|charm|logo|bloom|illustration|background|card",
 "description": "one sentence",
 "regions": [{"label": "face|head|hands|body|product|text|logo|subject", "cells": ["C2","D2"],
              "must_not_cut": true, "must_not_cover": true}],
 "busy": true,
 "dominant_colors": ["#hex"]}
```
Code turns cells into boxes (union of cells). Cells must cover the WHOLE region (include all hair for a head); over-cover by one cell rather than under-cover.

## Stage 3 — vision checks, ONE prompt per element type group
Files: `vision_text.md` (text + button), `vision_logo.md`, `vision_bloom.md`, `vision_charm_illustration.md`, `vision_photo.md` (photo + product + card).
User message: canvas info, funnel_stage ("ad" default), the relevant brand rules excerpt, and for EACH element of that type:
- element JSON: `{"id","type","bbox":[x,y,w,h],"text","font","fill","source_asset","tags"}` (tags = Stage 1 output for its asset)
- image `crop_<id>`: clean close-up of the element plus ~15% margin of what surrounds it (no labels, no markings)
Plus ONE image `context`: the whole design, clean, small.
Code checks (geometry, palette, fonts, safe zones, overlaps, clear space, cut-off tagged regions, stretch, resolution, contrast) are ALREADY done — vision prompts must NOT re-check them and must say so.
Reply:
```json
{"items": [{"element_id": "4",
  "observations": ["literal description of what is visible: edges, colours, what touches/overlaps it, what is cut at the crop border"],
  "checks": [{"check": "snake_case_name", "verdict": "pass|fail|unsure|n/a",
              "severity": "high|medium|low", "message": "one plain-English sentence for a designer",
              "evidence": "what in the image proves it"}]}]}
```
`observations` MUST be filled before `checks` — it forces looking. Only `fail` checks become findings. `unsure` (rule applies, image can't settle it) and `n/a` (rule doesn't apply to this element) are not findings; `n/a` is hidden. Each prompt lists its allowed `check` names.

## Stage 4 — verifier.md (one call per fail finding)
User message: the claim (check, message, evidence, element JSON), the element crop, the context image.
Reply: `{"verdict": "true|false|unsure", "evidence": "what you see", "confidence": "high|medium|low"}`
Only `true` survives. The verifier is skeptical: it must look for evidence the claim is WRONG first.

## Global rules for all prompts
- Intentional creative choices are not defects (subject breaking out of a bloom, bloom cropped by the canvas edge, overlapping layers that are clearly designed).
- If unsure → `unsure`, never `fail`.
- Never output pixel coordinates; refer to elements by id.
- Plain English in `message`; no jargon.
- Brand rules source: `assets/brand-rules/brand-rules.md` (Xero brand kit).
