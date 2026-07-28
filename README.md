# Drawing text translator (RU → EN)

Translates Russian text on engineering drawings to English using Gemini, then draws the English back onto the image.

**Assumption:** the brief's first line says "into Russian", but the body and I/O spec say Russian in → English out. This project does **RU → EN**.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # put your GEMINI_API_KEY there
```

## Run

Main pipeline (1 Gemini call per image):

```bash
python translate.py input/image-1.png
python translate.py input/image-2.png
python translate.py input/image-3.png
```

Outputs:
- `output/<name>.json` — detected text + boxes + translations
- `output/<name>-en.png` — English drawing

Reuse existing JSON without calling Gemini:

```bash
python translate.py input/image-1.png --render-only
```

Optional alternate approach (full cell/label region fill):

```bash
python translate_v2.py input/image-1.png
```

## Rules followed

1. Russian text is covered (white fill) and replaced with English
2. Font size derived from box height, shrink-to-fit so text stays in bounds
3. Any font is fine (Arial)
4. Abbreviations transliterated (`ГОСТ`→`GOST`, `СБ`→`SB`, …)
5. Bare numbers left unchanged
6. ≤20 Gemini calls per image (this uses **1**)

## Known limitations

- Boxes from Gemini are sometimes slightly tight → small leftover Russian pixels
- Some stamp/margin labels come back as translit instead of English
- Multi-line cells can split (`Примечание`)
- Free-floating weld symbols may be incomplete
- Vertical/upside-down text is handled, but not perfect on every label

Sample results are in `output/`.
