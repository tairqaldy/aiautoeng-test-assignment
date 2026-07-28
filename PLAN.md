# Plan

Working notes — the logic I'm following, written before the code.

## Goal

Russian engineering drawing in → same drawing with English text out.

**Assumption:** the task's first line says "translate into Russian", but the body and the
I/O spec both say Russian in → English out. Going with RU → EN.

## Pipeline

One pass, five steps:

1. Send the image to Gemini, get back JSON: for each text item its box, the Russian, the
   English, and its orientation.
2. Convert boxes from Gemini's normalised `[ymin, xmin, ymax, xmax]` (0–1000) to pixels.
3. Drop every item with no Cyrillic in it.
4. White-fill each remaining box.
5. Draw the English back, shrunk to fit the box.

## Decisions

**One Gemini call per image.** Budget allows 20. Detection and translation in a single
JSON response is enough; if small text in the title block comes back wrong, the upgrade is
a second call on a crop of that region. "Fewer is better" is secondary — correctness first.

**Filter numbers in code, not in the prompt.** Rule 7 says leave bare numbers alone. Rather
than asking the model to decide, I drop any item containing no Cyrillic. `45`, `Ø20`, `210`
are then untouched by construction, and GOST callouts can't get mangled.

**Font size comes from the box, not the model.** Rule 2 wants sizes preserved. Box height
gives that directly and for free, so there's no reason to ask for it.

**When rule 2 and rule 4 conflict, rule 4 wins.** English runs longer than Russian and the
cells are tight. Text must not leave its cell (hard rule), size is only "where possible" —
so shrink to fit. The prompt also asks for terse translations to reduce how often that bites.

**Orientation as a field, not geometry.** The left margin of image-1 is vertical, and images
2 and 3 have the drawing number rotated 180°. Bounding boxes carry no rotation, so the model
returns an orientation and I render onto a transparent layer, rotate, paste.

**Structured output, not JSON-from-text.** Using the SDK's response schema so there's no
fence-stripping or retry code to write. `temperature=0` so prompt changes are measurable.

**Inset the fill by ~2px** so erasing text doesn't eat the table borders.

## Order of work

1. Skeleton, requirements, keys
2. Gemini call → dump raw JSON, no drawing yet
3. Draw the boxes on the image to eyeball them ← real checkpoint; everything downstream
   depends on the boxes being right
4. White-fill only (this alone meets the task's stated minimum bar)
5. Render English, shrink to fit
6. Rotated text
7. README with results and honest limitations

Steps 4 and 7 are the floor. If time runs out, everything after 5 gets cut and documented
rather than half-built.

## Open

- Small text in the title block may suffer from Gemini downsampling the image. If boxes look
  sloppy there, first lever is upscaling before sending.
- Overlapping or multi-line cells aren't handled specially yet — checking whether they
  actually occur in these three drawings before writing code for it.
- **Cell-first approach, to test if time is left.** Instead of finding text boxes, find the
  table cells first, then ask whether each cell has text in it, read it, fill the whole cell
  rather than just the text's bounding box, and write the English on top at the same size.
  Filling the entire cell means no Russian pixels can survive at the edges, and the text
  can't leave the cell because the cell *is* the box. Only covers the table though — the
  free-floating notes and GOST callouts on images 2 and 3 still need the box approach.
