import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

INPUT_PATH = Path("input/image-1.png")
OUTPUT_PATH = Path("output/image-1.json")

PROMPT = """
Find all Russian text on this engineering drawing.

Return JSON only: a list of objects with:
- text_ru: original Russian text
- text_en: English translation (abbreviations -> translit, e.g. alike ГОСТ->GOST, СБ->SB)
- box: [ymin, xmin, ymax, xmax] normalized 0-1000
- orientation: "horizontal" | "vertical" | "upside_down"

Skip numbers with no text (45, 130, Ø20, etc).
Keep translations short so they fit in table cells.
"""


def main():
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

    print(response.text)
    print(f"\nsaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()