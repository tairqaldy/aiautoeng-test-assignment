# Test task: drawing translator (RU -> EN)

This repo contains my solution for the test task.

Goal: take a Russian engineering drawing, find Russian text on it, translate it to English, and write the English back onto the same image.

I treated the task as **RU -> EN**, because even though the very first line in the brief says otherwise, the actual body and input/output description clearly say: Russian image in, English image out.

## Final version

My final script is:

- `translate_v3.py`

Older versions are still here because they show how I moved step by step:

- `translate.py` — first working end-to-end version
- `translate_v2.py` — experiment with full cell / label region fill

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Put your Gemini API key into `.env`:

```bash
GEMINI_API_KEY=...
```

## Run

Run final version:

```bash
python translate_v3.py input/image-1.png
python translate_v3.py input/image-2.png
python translate_v3.py input/image-3.png
```

If JSON already exists and I only want to rerender:

```bash
python translate_v3.py input/image-1.png --render-only
```

Main outputs:

- `output/<name>-v3.json`
- `output/<name>-v3-draft.png`
- `output/<name>-v3-en.png`

## What `v3` does

Pipeline:

```text
image
-> Gemini detect + translate
-> render draft
-> Gemini verify / quality check
-> optional one more correction round
-> final render
```

The final version does a few things differently from the first one:

1. asks Gemini not just for text and translation, but also for:
   - box
   - orientation
   - region type (`cell`, `field`, `title`, `callout`)
2. uses a GOST font for rendering:
   - `fonts-GOST/GOST_AU.TTF`
3. tries to preserve borders better by not overfilling white over table lines
4. does a small quality loop:
   - render draft
   - ask Gemini whether coverage is OK
   - if not, apply small fixes / rerender
5. supports underlined section labels where needed

## How I approached it

I intentionally did this in small steps instead of trying to build a “smart” system from the start.

Order of work:

1. basic repo + requirements
2. one Gemini call, dump raw JSON
3. draw debug boxes on top of the image
4. white-fill Russian text
5. render English
6. handle rotated / upside-down text
7. improve translation quality
8. improve coverage / borders
9. improve font
10. add verification loop

For this task I think this was the right tradeoff: get a real end-to-end result first, then polish the weak spots.

## Main decisions

| Problem / choice | What I did |
|------------------|------------|
| Brief contradicts itself | Followed the body of the task: **RU -> EN** |
| Fewer Gemini calls are secondary | Started with 1 call/image, then allowed extra verification in `v3` |
| Numbers without Russian text | Left them unchanged |
| Abbreviations / standards | Transliterate codes like `GOST`, `SB`, `IG`, `TM`; translate normal Russian labels to English |
| Vertical / upside-down text | Ask Gemini for orientation, then rotate text in Pillow |
| White fill can damage borders | Use region-aware fill insets and a small correction loop |
| Generic font looked too off | Switched final version to GOST font |
| Small title-block cells were messy | Added compact rendering / alignment tweaks |
| Underlined labels existed in the drawing | Added underline rendering in final version |

## Final results

### Final outputs (`v3`)

| Input | Final output |
|-------|--------------|
| [`input/image-1.png`](input/image-1.png) | [`output/image-1-v3-en.png`](output/image-1-v3-en.png) |
| [`input/image-2.png`](input/image-2.png) | [`output/image-2-v3-en.png`](output/image-2-v3-en.png) |
| [`input/image-3.png`](input/image-3.png) | [`output/image-3-v3-en.png`](output/image-3-v3-en.png) |

Also kept:

- draft images: `output/*-v3-draft.png`
- structured Gemini output: `output/*-v3.json`

### Intermediate versions

I kept older outputs too:

- `output/image-1-en.png`, `output/image-2-en.png`, `output/image-3-en.png`
- `output/image-1-v2-en.png`, `output/image-2-v2-en.png`, `output/image-3-v2-en.png`

They are useful to see how the result improved from a simple pipeline to the final version.

## Notes about quality

What I specifically tried to improve in the final version:

- better real English instead of lazy translit for normal labels
- less damage to borders / grid lines
- better font fit
- better handling of tiny title-block cells
- better handling of underlined labels
- small verification loop for missed coverage

## Known limitations

Even in `v3`, some limitations remain:

- Gemini can still give imperfect boxes in hard areas
- some weld / special symbols are sensitive and may still need manual polish
- tiny title-block cells are the hardest area on these drawings
- verification loop is intentionally small, not an unlimited retry system
- one of the issues I noticed during development was normal labels being transliterated instead of actually translated; that is improved in `v3`, but it is still something I would keep checking

## What I would improve next with more time

If I had more time, I would improve:

1. targeted crop-based reprocessing for only failed areas
2. better handling of special weld symbols and notation
3. merging of split multi-line text automatically
4. smarter line reconstruction instead of only white-fill + rerender
5. stronger verification for title-block microtext

## Summary

My final answer is `translate_v3.py`.

It is not over-engineered, but it is more than just a single naive render:

- detection
- translation
- orientation handling
- GOST font rendering
- underline handling
- quality verification loop

That felt like the best balance between quality and time for this task.
