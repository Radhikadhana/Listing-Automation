# Marketplace Bulk Upload Sheet Generator

Streamlit app that converts a Master Input Sheet + supporting sheets (Image,
Size Chart Template, Category) into a marketplace-ready bulk upload file, per
the spec: title cleaning, parent/child grouping, variations, description
cleaning, pricing, stock=0, default values, images, size chart template
values, and category IDs.

## ⚠️ Before you run this

The column-name constants at the top of `app.py` (`MASTER_COLS`,
`IMAGE_SHEET_COLS`, `SIZE_CHART_TEMPLATE_COLS`, `CATEGORY_SHEET_COLS`) are
**best-guess placeholders** because this app was built without seeing your
real spreadsheets. Open `app.py`, find the `CONFIG` section near the top,
and edit each dictionary value to match your actual column headers exactly
(e.g. if your Master Sheet calls it `"Style No."` instead of
`"Style Number"`, update it there). The output columns/order will always
match whatever you upload as the Sample Upload Format file — that file is
now **required**.

## What changed in this version

- **Tracker Sheet removed.** Price is read directly from a column on the
  Master Input Sheet (you pick which column in the app UI) — no separate
  pricing file upload anymore.
- **Size Chart Sheet replaced with a Size Chart Template Sheet.** Instead of
  fuzzy keyword-in-title matching against a URL, this does a direct key
  lookup: `Age Group-Gender-Article Group-Article Type` → a literal
  `Template Attribute 1` string you define in that sheet (e.g.
  `sizechart=Men Tops`). Add/edit rows in that sheet for every combination
  you need; no code changes required to add new size-chart mappings.
- **Sample Upload Format is now mandatory.** The generated file's columns
  and order always match the Sample Upload Format's headers exactly — any
  column missing from the app's internal output is filled blank, and any
  computed column not present in the sample is dropped.

## Project structure

```
.
├── app.py              # Main Streamlit app (all logic + UI)
├── requirements.txt    # Python dependencies
└── README.md
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

## Push to GitHub

```bash
git init
git add app.py requirements.txt README.md
git commit -m "Marketplace bulk upload sheet generator"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## Deploy on Streamlit Community Cloud (connects directly to GitHub)

1. Push the repo to GitHub as above (repo can be public or private).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **"New app"**.
4. Select your repository, branch (`main`), and set **Main file path** to
   `app.py`.
5. Click **Deploy**. Streamlit Cloud will install `requirements.txt`
   automatically and give you a public URL.
6. Any future `git push` to `main` auto-redeploys the app.

## What the app does (mapped to your spec)

| Spec section | Implemented as |
|---|---|
| 1. Title | `clean_title()` — brand/gender/name/footwear color, word replacements, dedupe |
| 2. Parent & Child Grouping | `build_upload_sheet()` groups by Style Number (or Style+Color for footwear) |
| 3. Variations | Color Family→Color Name, Size→UK Size, sorted via `size_sort_key()` |
| 4. Description Cleaning | `clean_description()` — strips tags, converts headings/bullets, appends Style/Care/Care Label |
| 5. Price | `get_price()` pulls straight from the Master Sheet's selected price column |
| 6. Stock | Hardcoded to `0` for every Parent/Child row |
| 7. Default Values | `DEFAULTS` dict applied to every row |
| 8. Images | `get_images_for_sku()` pulls from the Image Sheet by SKU |
| 9. Size Chart | `match_size_chart_template()` — direct key lookup against the Size Chart Template Sheet |
| 10. Category | `match_category_id()` matches title keywords to the Category Sheet |
| Output columns | Always taken from the required Sample Upload Format file |

## Known adjustments still needed once real files are shared

- Exact column header names in each source sheet (see CONFIG section).
- Category/size-chart-template keys — currently the Category Sheet still
  uses simple keyword-in-title substring matching; if your Category Sheet
  uses structured attributes instead of free-text keywords, switch that to
  an exact-match join the same way the Size Chart Template lookup now works.
- Size Chart Template Sheet must contain one row per
  `Age Group-Gender-Article Group-Article Type` combination you expect to
  see, with the exact `Template Attribute 1` string to output for it.
