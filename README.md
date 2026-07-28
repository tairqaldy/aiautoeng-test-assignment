# Drawing text translator (RU → EN)

Translates Russian text on engineering drawings to English using Gemini, then draws the English back onto the image.

**Assumption:** the brief's first line says "translate into Russian", but the body and I/O spec both say Russian in → English out. This project does **RU → EN**.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # put your GEMINI_API_KEY there
```

## Run

**v1** — main pipeline (tight text boxes + expand fill), 1 Gemini call per image:

```bash
python translate.py input/image-1.png
python translate.py input/image-2.png
python translate.py input/image-3.png
```

**v2** — experiment: full cell/label region fill:

```bash
python translate_v2.py input/image-1.png
python translate_v2.py input/image-2.png
python translate_v2.py input/image-3.png
```

Reuse existing JSON (no Gemini call):

```bash
python translate.py input/image-1.png --render-only
python translate_v2.py input/image-1.png --render-only
```

Outputs land in `output/`:
- `<name>.json` / `<name>-v2.json` — detections + translations
- `<name>-en.png` / `<name>-v2-en.png` — English drawings

---

## How it works

```
image → Gemini (1 call: OCR + boxes + EN + orientation)
      → white-fill regions
      → draw English (shrink-to-fit, rotate if needed)
      → save PNG
```

Gemini returns JSON like:

```json
[
  {
    "text_ru": "Основание",
    "text_en": "Base",
    "box": [ymin, xmin, ymax, xmax],
    "orientation": "horizontal"
  }
]
```

Boxes are normalized **0–1000** (`[ymin, xmin, ymax, xmax]`), then scaled to pixels. Font size comes from box height; text shrinks until it fits width and height. Vertical / upside-down labels are drawn on a transparent layer, rotated, then pasted.

---

## How I built it (step by step)

I kept commits small and checked visuals after each step — no big rewrite until the previous step looked sane.

1. **Skeleton** — repo, `.env`, `requirements.txt`, input images
2. **Gemini smoke test** — one call, dump raw JSON only (no drawing yet)
3. **Debug boxes** — draw red rectangles on the image to verify coordinates
4. **White-fill** — cover Russian (meets the task minimum bar by itself)
5. **Render English** — shrink-to-fit into boxes
6. **Rotated text** — left margin + upside-down drawing numbers
7. **CLI** — `python translate.py input/image-N.png` for all three drawings
8. **v2 experiment** — full region fill (see below)
9. **README** — process, decisions, results

Checkpoint that mattered most: step 3. If boxes are wrong, everything downstream is wasted.

---

## Decisions & problem handling

| Problem / choice | What I did |
|------------------|------------|
| Brief contradicts itself (RU vs EN) | Followed body + I/O: **RU → EN**, stated in README |
| Max 20 Gemini calls / image | **1 call** — detect + translate + orientation together |
| Bare numbers must stay (rule 7) | Prompt skips number-only items; don't paint `45`, `Ø20`, etc. |
| Font size vs cell bounds (rules 2 & 4) | Rule 4 wins: shrink-to-fit. Font type = Arial (rule 3 allows any) |
| Abbreviations | Translit in prompt: `ГОСТ`→`GOST`, `СБ`→`SB`, `ИГ`→`IG` |
| Vertical / 180° text | Ask Gemini for `orientation`, rotate PIL layer |
| Tight boxes left Russian edges | Expanded white fill (`inset=-3`) in v1 |
| Fill still looked patchy on tables | Tried **v2**: ask for full cell/label region, fill whole box |
| Didn't use n8n | Task asks for code + `requirements.txt`; Pillow pixel work is simpler as a script |

Things I **did not** do on purpose (avoid over-engineering):
- font detection / matching
- second Gemini validation loop
- full table-grid reconstruction
- separate OCR service + translator chain

---

## Results (evidence)

### v1 — `translate.py`

| Input | Output |
|-------|--------|
| [`input/image-1.png`](input/image-1.png) | [`output/image-1-en.png`](output/image-1-en.png) |
| [`input/image-2.png`](input/image-2.png) | [`output/image-2-en.png`](output/image-2-en.png) |
| [`input/image-3.png`](input/image-3.png) | [`output/image-3-en.png`](output/image-3-en.png) |

Also kept debug / intermediate: [`output/image-1-boxes.png`](output/image-1-boxes.png), [`output/image-1-masked.png`](output/image-1-masked.png).

### v2 — `translate_v2.py` (experiment)

Idea: don't hug the glyphs. Ask Gemini for the **full region to clear** (table cell, stamp field, or label band), white-fill that entire region, then write English inside it. Goal: fewer leftover Russian pixels and cleaner cells.

| Input | Output |
|-------|--------|
| [`input/image-1.png`](input/image-1.png) | [`output/image-1-v2-en.png`](output/image-1-v2-en.png) |
| [`input/image-2.png`](input/image-2.png) | [`output/image-2-v2-en.png`](output/image-2-v2-en.png) |
| [`input/image-3.png`](input/image-3.png) | [`output/image-3-v2-en.png`](output/image-3-v2-en.png) |

**Takeaway:** v2 is a bit cleaner on table-heavy `image-1`. On drawings 2 and 3 (free-floating notes / callouts) both approaches work; oversized regions can still eat nearby lines if Gemini returns a box that is too large. v1 stays the main script; v2 is kept as a documented alternative.

---

## Rules followed

1. Russian removed (white fill) and replaced with English  
2. Font size from box height, shrink-to-fit  
3. Any font OK (Arial)  
4. Text kept inside the region  
5. Abbreviations → translit  
6. ≤20 Gemini calls (uses **1**)  
7. Bare numbers left alone  

## Known limitations

- Gemini boxes can still be slightly off → leftover pixels or over-paint  
- Some stamp/margin labels come back as translit instead of real English  
- Multi-line cells can split (`Примечание`)  
- Weld callouts / special symbols may be incomplete  
- Rotation works, not perfect on every label  
