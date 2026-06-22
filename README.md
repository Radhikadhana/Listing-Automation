# Lazada SG Listing Converter

Converts the product **Input.xlsx** sheet into a Lazada SG marketplace upload
file using the official **Header** column layout, with Category IDs
auto-matched from a Lazada category export.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints, upload `Input.xlsx` and
`Lazada_SG_Category_Sheet.xlsx`, and click **Generate Output**.

## Deploy

1. Push this folder to a GitHub repo.
2. On [share.streamlit.io](https://share.streamlit.io), create a new app
   pointing at the repo, branch, and `app.py`.
3. Streamlit Cloud installs `requirements.txt` automatically.

## What gets mapped

| Output column | Source |
|---|---|
| Seller SKU | `EAN` |
| Product Name | `Regional Display Name (English)` (falls back to `Style Name`) |
| Product Description 1 / Short Description | `Short Description (English)` |
| Product Description 2 | `Long Description (English)` |
| Total variation | count of rows sharing the same `Style No` |
| Variation 1 / 2 | `Color Name` / `Size No.` |
| SRP & RRP | `Price` |
| Currency Code | hardcoded `SGD` |
| Category ID | auto-matched (see below) |
| Brand | `Brand` |
| Model | `Style No` |
| Package Weight/Height/Length/Width | `Product Wt/Ht/Len/Wd (SEA,Metric)` |
| Product Specification 1–25 | Material, Technology, Fit, Body Style, Mid Sole, Upper, Outer Sole, Profile, Collection, Country of Origin, etc. — see `SPEC_SOURCE_COLUMNS` in `mapper.py` |
| Template Attribute 1–5 | Age Group, Gender, Article Group, Article Type, Activity Group |
| Post As Non Variant | `"No"` if a style has more than one SKU variant, else `"Yes"` |

**Left blank (no source field in Input.xlsx):** Graas SKU, Status, Remarks,
Sale Start/End Date, Quantity, Product Image URL(s), Tax Class, Warranty
Type, What's in the Box, Size chart Image URL. Fill these in manually
after export, or tell me the source/default you want and I'll wire it in.

## Category ID matching

Since Input.xlsx has no Category ID column, each row's
`Age Group / Gender / Article Group / Article Type / Activity Group /
Product Division` is scored against every path in the Lazada category
sheet:

- Matching is restricted to apparel/footwear/accessories-relevant
  branches (Sports Shoes and Clothing, Sports & Outdoors Equipment,
  Men's/Women's Shoes & Clothing, Kids' Fashion, Fashion Accessories,
  Bags and Travel, Lingerie/Sleep/Lounge) to avoid nonsense matches
  like Automotive or Pet Supplies.
- Article Type/Group keyword overlap is weighted heaviest; Gender and
  Age Group give bonuses/penalties (e.g. an Adults item is penalized
  from landing in Kids' Fashion).
- A **Sports**-branch match is used whenever it's reasonably
  competitive; otherwise the best Fashion/Bags/Shoes match is used.

This is a heuristic, not a certainty — review the **Category Match Log**
sheet included in every output file before bulk uploading to Lazada Seller
Center, and correct any rows that look off.
