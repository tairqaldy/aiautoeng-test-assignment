"""v2 approach: full cell/label region fill, not tight glyph boxes.

Ask Gemini for the whole area to clear (table cell or label band),
white-fill that entire region, then draw English shrink-to-fit inside it.
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

FONT_PATH = Path("C:/Windows/Fonts/arial.ttf")

PROMPT = """
Find all Russian text on this engineering drawing.

For each item, the box must cover the FULL region to clear — the whole table
cell, stamp field, or label band — not just the tight letter bounds.
Leave a tiny gap so table grid lines are not erased.

Return JSON only: a list of objects with:
- text_ru: original Russian text
- text_en: English translation (abbreviations -> translit, e.g. ГОСТ->GOST, СБ->SB)
- box: [ymin, xmin, ymax, xmax] normalized 0-1000  (full region, not tight glyphs)
- orientation: "horizontal" | "vertical" | "upside_down"

Skip numbers with no text (45, 130, Ø20, etc).
Keep translations short so they fit in the region.
Do not invent empty cells. Only regions that contain Russian text.
On free-floating notes/callouts, box the full text line/band, not a huge empty area.
"""

INPUT_PATH = Path("input/image-1.png")
OUTPUT_PATH = Path("output/image-1-v2.json")
EN_PATH = Path("output/image-1-v2-en.png")


def set_paths(image_path):
    global INPUT_PATH, OUTPUT_PATH, EN_PATH
    INPUT_PATH = Path(image_path)
    stem = INPUT_PATH.stem
    out = Path("output")
    OUTPUT_PATH = out / f"{stem}-v2.json"
    EN_PATH = out / f"{stem}-v2-en.png"


def call_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing in .env")

    image_bytes = INPUT_PATH.read_bytes()
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(response.text, encoding="utf-8")
    # Windows console may not support all chars (e.g. △) — file is still UTF-8
    try:
        print(response.text)
    except UnicodeEncodeError:
        print(response.text.encode("utf-8", errors="replace").decode("ascii", errors="replace"))
    print(f"\nsaved to {OUTPUT_PATH}")


def box_to_pixels(box, w, h, inset=1):
    ymin, xmin, ymax, xmax = box
    x0 = xmin / 1000 * w + inset
    y0 = ymin / 1000 * h + inset
    x1 = xmax / 1000 * w - inset
    y1 = ymax / 1000 * h - inset
    return [x0, y0, x1, y1]


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


def paste_text(img, text, box, orientation):
    x0, y0, x1, y1 = [int(v) for v in box]
    bw, bh = max(x1 - x0, 1), max(y1 - y0, 1)

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
    ImageDraw.Draw(layer).text((-l, -t), text, fill="black", font=font)
    if angle:
        layer = layer.rotate(angle, expand=True)

    px = x0 + (bw - layer.width) // 2
    py = y0 + (bh - layer.height) // 2
    img.paste(layer, (px, py), layer)


def render_english():
    items = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    img = Image.open(INPUT_PATH).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for item in items:
        if "box" not in item or not item.get("text_en"):
            continue
        # fill the FULL region (tiny inset keeps grid lines)
        region = box_to_pixels(item["box"], w, h, inset=1)
        draw.rectangle(region, fill="white")
        paste_text(img, item["text_en"], region, item.get("orientation", "horizontal"))

    EN_PATH.parent.mkdir(exist_ok=True)
    img.convert("RGB").save(EN_PATH)
    print(f"saved english image to {EN_PATH}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python translate_v2.py input/image-1.png [--render-only]")

    set_paths(sys.argv[1])
    if not INPUT_PATH.exists():
        raise SystemExit(f"file not found: {INPUT_PATH}")

    if "--render-only" not in sys.argv:
        call_gemini()
    render_english()
