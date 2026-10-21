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

## Windows (double-click)

1. Get the project folder onto the PC: on GitHub, **Code → Download ZIP**, then unzip it (for example to `C:\hesab`).
2. Double-click **`start-web.bat`**.
   - The first time, it installs `uv` and asks for your Gemini API key (paste it and press Enter).
     It then downloads Python and the libraries, which takes a few minutes, only once.
   - The page opens in the browser at http://localhost:8501. Keep the black window open while you use it,
     and close it when you're done.
3. Or drag a PDF onto **`convert.bat`**: the Excel file is written next to the PDF and opened.

Tip: right-click `start-web.bat` → *Send to* → *Desktop (create shortcut)* for a desktop icon.

## Setup (Linux / macOS)

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

Web page (title + upload box; drop the PDF and the Excel downloads when ready):

```sh
uv run hesab-web        # opens http://localhost:8501 in the browser
```

## Notes

- Default model is `gemini-3.8-flash`. Override it with `GEMINI_MODEL` or `--model`.
- One PDF = one API request, which matters on the free tier. The request takes a few minutes.
  On `429`/`503` (quota or Google overload) it retries with backoff.
- Scans and generated spreadsheets are git-ignored because they contain personal data.
