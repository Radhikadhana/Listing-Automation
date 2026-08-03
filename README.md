# Marketplace Bulk Upload Sheet Generator

Streamlit app that converts a Master Input Sheet + supporting sheets (Tracker,
Image, Size Chart, Category) into a marketplace-ready bulk upload file, per
the spec: title cleaning, parent/child grouping, variations, description
cleaning, pricing, stock=0, default values, images, size charts, and category
IDs.

## ⚠️ Before you run this

**No code editing required.** Column mapping now happens entirely in the app:
after you upload each sheet, dropdowns appear so you can match every field
(Style Number, SKU, Article Number, Brand, etc.) to your sheet's actual
column headers. The constants at the top of `app.py` (`MASTER_COLS`,
`TRACKER_COLS`, `IMAGE_SHEET_COLS`, `SIZE_CHART_COLS`, `CATEGORY_SHEET_COLS`)
are only used as fallback defaults / best-guess pre-selections in those
dropdowns — you never need to open `app.py` to fix a "column mapping
mismatch" error anymore. If you upload a Sample Upload Format file in the
app, the final output columns/order will automatically match it.

**Pricing note:** the Tracker Sheet is keyed by **PIM Article**, not SKU.
The app resolves price by: SKU (Master row) → Article Number (Master row,
mapped in the "Master Sheet — Column Mapping" section) → PIM Article
(Tracker row, mapped in "Tracker Sheet — Column Selection") → Price column
(also selected there). Just make sure you pick the correct Article Number
column for the Master Sheet and the correct PIM Article column for the
Tracker Sheet in their respective dropdowns.

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
| 5. Price | `get_price()` looks up price in the Tracker Sheet by **PIM Article Number** (not SKU). The Master Sheet's Article Number column for each SKU (picked in the in-app column mapping) is resolved first, then used to find the matching row in the Tracker Sheet. |
| 6. Stock | Hardcoded to `0` for every Parent/Child row |
| 7. Default Values | `DEFAULTS` dict applied to every row |
| 8. Images | `get_images_for_sku()` pulls from the Image Sheet by SKU |
| 9. Size Chart | `match_size_chart()` matches title/category to the Size Chart Sheet |
| 10. Category | `match_category_id()` matches title keywords to the Category Sheet |

## Known adjustments still needed once real files are shared

- Exact column header names in each source sheet (see CONFIG section).
- Exact output column names/order (auto-solved if you upload a Sample
  Upload Format file — otherwise edit `output_columns` logic).
- Category/size-chart matching currently uses simple keyword-in-title
  substring matching; if your Category/Size Chart sheets use structured
  attributes (e.g. Product Type + Gender columns) instead of free-text
  keywords, this should be switched to an exact-match join instead.
