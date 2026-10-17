# Type

No typeface file is in the kit; the brand book uses a bold condensed sans for headlines and a clean sans for body. Colour, case and hierarchy are what we can enforce.

## Rules

**TY1 MUST: Text colour follows the topmost surface behind it: navy on white/light, white on navy/blue/saturated bloom; no other text colours.**
- How to apply: find the topmost layer actually under the text box (card, bloom, template area), not just the background slot. White, sky or cyan surface: navy #000856. Navy, template blue, blue/navy/purple/pink blooms: white #FFFFFF.
- Cyan text is allowed only as a highlight on navy (observed on example pages), never as body copy.
- Why: AAA contrast and a consistent look.

**TY2 MUST: Headline is bold condensed sans in sentence case; support copy medium weight; text left-aligned.**
- Headline: bold condensed sans, sentence case (capital first letter and proper nouns only), ends with a full stop in our generated ads. Large, 1-3 lines.
- Support: medium weight, smaller, one line if possible.
- Alignment: left-aligned, headline/support/CTA share a left edge. Centre only the wordmark inside its container.
- Observed exception: example pages show short uppercase italic slogans (2-4 words). Treat it as an exception a designer chooses, not a default; generators should use sentence case.

**TY3 MUST: CTA is a fully rounded pill: navy fill + white text on light surfaces, cyan fill + navy text on navy; at most 22 chars, verb first.**
- Sentence case, starts with a verb ("Try Xero for free", "Start your free trial"). An arrow glyph after the label is fine (observed). No exclamation marks.
- The pill must contrast with the surface it sits on; on template blue use a white pill with navy text.
- One CTA per ad.

**TY4 MUST: Text over a photo, pattern or a bloom edge sits on a white card or flat field, never straddling two surfaces.**
- How to apply: if a text box overlaps two surfaces (part bloom, part background) either move it fully onto one surface or add a `shape` slot `kind: "card"`, white fill, large radius, with an `on` relation. Text on a card follows TY1 for the card's colour.
- Why: half-on, half-off text fails contrast on one side.

## Character budget (from testing)
- Headline: about 20 chars per line at full width (12 cols); a 0.75-wide box holds about 15 per line.
- Support: about 50 chars per line at full width. CTA: at most 22. Proof label: at most 20.

## Source pages
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/01_xero_wordmark_primary.png
- assets/brand-kit/05_Logo_Guidelines/05_Logo_Guidelines/02_xero_wordmark_accessibility.png
- assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/07_07_examples.png
- assets/brand-kit/06_Shapes_Cropping_Blooms/06_Shapes_Cropping_Blooms/03_03_cropping_and_frames.png
