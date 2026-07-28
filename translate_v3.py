"""v3 approach: better translation rules + verification pass.

Goals:
- translate labels to real English, not translit
- preserve borders better by using region-aware fill
- allow an extra Gemini verification pass to fix obvious misses
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

FONT_PATH = Path("fonts-GOST/GOST_AU.TTF")
MODEL = "gemini-3.6-flash"

DETECT_PROMPT = """
You are preparing high-quality English replacements for Russian engineering drawing text.

Important translation rules:
1. Translate normal Russian words to natural English. Do NOT transliterate regular labels.
2. Transliterate only standards / codes / abbreviations when they are identifiers:
   - ГОСТ -> GOST
   - СБ -> SB
   - ИГ -> IG
   - гр. -> gr.
   - ТМ -> TM
3. Keep numbers, dimensions, and symbols unchanged whenever possible.
4. Keep English concise but correct. Do not shorten by dropping meaning.
5. If a label is administrative / title-block text, translate it to real English.
6. If item is underlined it should be noted as well to move that underline to english text as well.

Examples:
- Основание -> Base
- Стойка -> Post
- Крышка -> Cover
- Уголок -> Angle bracket
- Наименование -> Name
- Обозначение -> Designation
- Примечание -> Note
- Сборочный чертеж -> Assembly drawing
- Сварное соединение -> Welded joint
- Опора -> Support
- Подп. и дата -> Signature and date
- Перв. примен. -> First use
- Справ. № -> Reference No.
- Инв. № дубл. -> Duplicate inventory No.
- Взам. инв. № -> Replaces inventory No.
- Инв. № подл. -> Original inventory No.

For each item, return:
- id: integer starting from 1
- text_ru: original Russian text
- text_en: English translation
- box: [ymin, xmin, ymax, xmax] normalized 0-1000
- orientation: "horizontal" | "vertical" | "upside_down"
- region_type: "cell" | "field" | "title" | "callout"

Box rules:
- If text is inside a table cell / title-block field, box the full interior region to clear,
  but leave a tiny gap before borders.
- If text is a free callout / note, box only the full text band, not a huge area.
- Do not invent empty cells.
- Skip pure number-only items such as 45, 130, Ø20 if they have no Russian letters.

Return JSON only: an array of objects.
"""

VERIFY_PROMPT = """
Compare the original Russian drawing and the rendered English draft.

Decide whether the result is good enough:
- coverage_ok: no visible Russian/Cyrillic remains inside cleared regions, and text is not clipped

Also decide whether we should regenerate JSON/translation:
- needs_retranslate: true if many labels are clearly mistranslated or transliterated when they must be translated

If something needs fixing, return it in `fixes`:
Each fix must reference the existing numeric `id`.

Fix fields (all optional except id):
- text_en: corrected English (include only if translation is wrong)
- box: revised [ymin,xmin,ymax,xmax] (include only if box positioning is wrong)
- fill_inset_delta: number to apply to fill size for this region
  - negative expands white-fill (more coverage)
  - keep small (range -2..0) to avoid wiping borders

Return JSON ONLY with this exact shape:
{
  "coverage_ok": true/false,
  "needs_retranslate": true/false,
  "fixes": [
    {
      "id": 3,
      "text_en": "Signature and date",
      "box": [ymin, xmin, ymax, xmax],
      "fill_inset_delta": -1
    }
  ]
}
"""

INPUT_PATH = Path("input/image-1.png")
OUTPUT_PATH = Path("output/image-1-v3.json")
DRAFT_PATH = Path("output/image-1-v3-draft.png")
EN_PATH = Path("output/image-1-v3-en.png")


def set_paths(image_path):
    global INPUT_PATH, OUTPUT_PATH, DRAFT_PATH, EN_PATH
    INPUT_PATH = Path(image_path)
    stem = INPUT_PATH.stem
    out = Path("output")
    OUTPUT_PATH = out / f"{stem}-v3.json"
    DRAFT_PATH = out / f"{stem}-v3-draft.png"
    EN_PATH = out / f"{stem}-v3-en.png"


def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing in .env")
    return genai.Client(api_key=api_key)


def safe_print(text):
    try:
        # Avoid Windows console encoding issues by writing UTF-8 bytes directly.
        safe = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        sys.stdout.buffer.write((safe + "\n").encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()
    except Exception:
        # Best-effort fallback; we still want the script to continue.
        pass


def detect_items():
    client = get_client()
    image_bytes = INPUT_PATH.read_bytes()
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            DETECT_PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(response.text, encoding="utf-8")
    safe_print(response.text)
    print(f"\nsaved to {OUTPUT_PATH}")
    return json.loads(response.text)


def clamp(value, low, high):
    return max(low, min(value, high))


def box_to_pixels(box, w, h, inset=0):
    ymin, xmin, ymax, xmax = box
    x0 = xmin / 1000 * w + inset
    y0 = ymin / 1000 * h + inset
    x1 = xmax / 1000 * w - inset
    y1 = ymax / 1000 * h - inset
    return [clamp(x0, 0, w), clamp(y0, 0, h), clamp(x1, 0, w), clamp(y1, 0, h)]


def fill_inset(region_type):
    # Avoid wiping table borders: shrink fill inside the box.
    # (User note: "white over line is BAD")
    if region_type in {"cell", "field", "title"}:
        return 2
    # Callouts / notes: still shrink a bit to not erase nearby arrows/lines.
    return 1


def text_inset(region_type):
    if region_type in {"cell", "field", "title"}:
        return 2
    return 1


def fit_font(text, max_w, max_h):
    size = max(int(max_h), 6)
    while size > 5:
        font = ImageFont.truetype(str(FONT_PATH), size)
        bbox = font.getbbox(text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= max_w and th <= max_h:
            return font
        size -= 1
    return ImageFont.truetype(str(FONT_PATH), 5)


def parse_text_style(text):
    underline = text.startswith("<u>") and text.endswith("</u>")
    if underline:
        text = text[3:-4]
    return text, underline


def should_underline(item):
    text_ru = (item.get("text_ru") or "").strip()
    return text_ru in {"Документация", "Детали"}


def paste_text(img, text, box, orientation, force_underline=False):
    x0, y0, x1, y1 = [int(v) for v in box]
    bw, bh = max(x1 - x0, 1), max(y1 - y0, 1)
    text, underline = parse_text_style(text)
    underline = underline or force_underline

    if orientation == "vertical":
        font = fit_font(text, bh, bw)
        angle = 90
    elif orientation == "upside_down":
        font = fit_font(text, bw, bh)
        angle = 180
    else:
        font = fit_font(text, bw, bh)
        angle = 0

    l, t, r, b = font.getbbox(text)
    tw, th = max(r - l, 1), max(b - t, 1)
    layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.text((-l, -t), text, fill="black", font=font)
    if underline:
        underline_y = max(th - 1, 0)
        layer_draw.line((0, underline_y, tw, underline_y), fill="black", width=1)
    if angle:
        layer = layer.rotate(angle, expand=True)

    px = x0 + (bw - layer.width) // 2
    py = y0 + (bh - layer.height) // 2
    img.paste(layer, (px, py), layer)


def render_items(items, output_path):
    img = Image.open(INPUT_PATH).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for item in items:
        if "box" not in item or not item.get("text_en"):
            continue
        region_type = item.get("region_type", "callout")
        fill_delta = item.get("fill_inset_delta", 0) or 0
        clear_box = box_to_pixels(item["box"], w, h, inset=fill_inset(region_type) + fill_delta)
        text_box = box_to_pixels(item["box"], w, h, inset=text_inset(region_type))
        draw.rectangle(clear_box, fill="white")
        paste_text(
            img,
            item["text_en"],
            text_box,
            item.get("orientation", "horizontal"),
            force_underline=should_underline(item),
        )

    output_path.parent.mkdir(exist_ok=True)
    img.convert("RGB").save(output_path)
    print(f"saved english image to {output_path}")


def verify_and_correct(items):
    client = get_client()
    original = INPUT_PATH.read_bytes()
    draft = DRAFT_PATH.read_bytes()

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_text(text=VERIFY_PROMPT),
            types.Part.from_text(text=json.dumps(items, ensure_ascii=False)),
            types.Part.from_bytes(data=original, mime_type="image/png"),
            types.Part.from_bytes(data=draft, mime_type="image/png"),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    safe_print(response.text)

    parsed = json.loads(response.text) if response.text else {}

    # Backward-compat: old format could be a list of fixes.
    if isinstance(parsed, list):
        corrections = parsed
        out = {**{"coverage_ok": len(corrections) == 0, "needs_retranslate": False}, "fixes": corrections}
    else:
        out = parsed

    coverage_ok = bool(out.get("coverage_ok", False))
    needs_retranslate = bool(out.get("needs_retranslate", False))
    fixes = out.get("fixes", []) or []

    by_id = {item["id"]: item for item in items if "id" in item}
    for fix in fixes:
        item = by_id.get(fix.get("id"))
        if not item:
            continue
        if fix.get("text_en"):
            item["text_en"] = fix["text_en"]
        if fix.get("box"):
            item["box"] = fix["box"]
        if "fill_inset_delta" in fix and fix.get("fill_inset_delta") is not None:
            item["fill_inset_delta"] = fix.get("fill_inset_delta")

    return list(by_id.values()), coverage_ok, needs_retranslate


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python translate_v3.py input/image-1.png [--render-only]")

    set_paths(sys.argv[1])
    if not INPUT_PATH.exists():
        raise SystemExit(f"file not found: {INPUT_PATH}")

    if "--render-only" in sys.argv:
        items = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        render_items(items, EN_PATH)
        return

    items = detect_items()

    # Quality loop: first render+verify, then (optionally) adjust fill and/or re-run detection once.
    # This is meant to catch bad coverage (like the 3rd image) without turning the whole task into a big pipeline.
    max_rounds = 2
    for _ in range(max_rounds):
        render_items(items, DRAFT_PATH)
        items, coverage_ok, needs_retranslate = verify_and_correct(items)

        if coverage_ok and not needs_retranslate:
            break

        if needs_retranslate:
            items = detect_items()

        # else: keep same items but with applied fill_inset_delta fixes; rerender on next round.

    OUTPUT_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    render_items(items, EN_PATH)


if __name__ == "__main__":
    main()
