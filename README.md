# hesab

One shot: scanned monthly attendance PDF (فرم حضور و غیاب کارکنان) in → Excel workbook out.

- The whole PDF is read by Gemini in **one request** (free API key from [ai.dev](https://aistudio.google.com/apikey)).
  Each page is cropped to its table and rendered at high resolution so handwriting is legible.
- Pages are grouped by person (any order, any number of pages per person).
- Output: one workbook with a **خلاصه** (summary) sheet plus **one right-to-left sheet per person**, covering every day of the month.
- **جمع کارکرد روزانه** is always computed (handwritten totals are ignored), as live Excel formulas:
  `(خروج۱−ورود۱) + (خروج۲−ورود۲) + (ماموریت تا−از) + دورکاری`.
  Fix a misread time in Excel and the daily, monthly and summary totals update.
- Fridays are grey. Days with no page in the scan are light grey. Uncertain or inconsistent cells are **yellow** with a note,
  including days where the handwritten total differs from the computed one by more than 15 minutes (a sign of a misread time).
  Always check yellow cells against the paper.

## Setup

```sh
uv sync
cp .env.example .env   # put your GEMINI_API_KEY in .env
```

## Usage

CLI:

```sh
uv run hesab scans.pdf                 # -> scans.xlsx
uv run hesab scans.pdf -o mehr.xlsx --save-json   # also keep raw extraction (scans.json)
uv run hesab scans.json                # rebuild the Excel from a saved extraction, no API calls
```

Web UI (drag-and-drop, download button):

```sh
uv run streamlit run hesab/web.py
```

## Notes

- Default model is `gemini-2.5-flash`. Override it with `GEMINI_MODEL` or `--model`.
- One PDF = one API request, which matters on the free tier. The request takes a few minutes.
  On `429`/`503` (quota or Google overload) it retries with backoff.
- Scans and generated spreadsheets are git-ignored because they contain personal data.
