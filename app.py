"""
Marketplace Bulk Upload Sheet Generator
========================================
Streamlit app that takes:
  - Master Input Sheet (product data)
  - Tracker Sheet (pricing)
  - Image Sheet (SKU -> image URLs)
  - Size Chart Sheet (category/title -> size chart image URL)
  - Category Sheet (title keyword -> category ID)
  - Sample Upload Format (defines exact output columns/order)

...and produces a marketplace-ready bulk upload file (Parent/Child rows,
cleaned titles & descriptions, variations, images, category IDs, size charts,
prices, defaults, stock=0, shipping, product specification).

IMPORTANT: Column name constants below are BEST-GUESS based on the spec you
provided. Once you share your actual sheets, update the CONFIG section
(search for "ADJUST ME") to match your real column headers exactly.
"""

import io
import re
import json
from collections import OrderedDict

import pandas as pd
import numpy as np
import streamlit as st

# ======================================================================================
# CONFIG — ADJUST ME to match your real column headers once real files are shared
# ======================================================================================

MASTER_COLS = {
    "style_no": "Style Number",
    "color_no": "Color Number",
    "brand": "Brand",
    "gender": "Gender",
    "title": "Regional Display Name",
    "color_family": "Color Family",
    "color_name": "Color Name",
    "size": "Size",
    "uk_size": "UK Size",
    "sku": "SKU",
    "description": "Description",
    "care": "Care",
    "care_label": "Care Label",
    "category_hint": "Category",  # optional, else derived from title
    "footwear_color": "Footwear Color",
    "product_type": "Product Type",  # e.g. Trainers / Sandals / Slides / Apparel / Accessories
}

TRACKER_COLS = {
    "sku": "SKU",
    "price_col": "Original Price",  # the "selected Tracker column" - adjust to actual column name
}

IMAGE_SHEET_COLS = {
    "sku": "SKU",
    "image_cols": ["Image 1", "Image 2", "Image 3", "Image 4", "Image 5", "Image 6", "Image 7", "Image 8", "Image 9"],
}

SIZE_CHART_COLS = {
    "category_or_title": "Category",
    "size_chart_url": "Size Chart URL",
}

CATEGORY_SHEET_COLS = {
    "keyword": "Title Keyword",
    "category_id": "Category ID",
}

# Default values (spec section 7)
DEFAULTS = {
    "Currency": "PHP",
    "Condition": "Default",
    "Warranty": "No Warranty",
    "Package Weight": 0.5,
    "Package Height": 15,
    "Package Length": 12,
    "Package Width": 12,
    "Shipping Service": "Standard Local",
    "Shipping Fee": 40.00,
    "Product Specification": "Brand: PUMA",
}

# Title word replacements (spec section 1)
TITLE_REPLACEMENTS = OrderedDict([
    (r"\bTrainers\b", "Shoes"),
    (r"\bSandals\b", "Sports Sandals"),
    (r"\bSlides\b", "Slides Slippers"),
])

# Size sort order (spec section 3)
ALPHA_SIZE_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "OSFA", "Youth"]


# ======================================================================================
# HELPERS
# ======================================================================================

def clean_title(brand, gender, title, footwear_color, is_footwear):
    """Build title per spec section 1."""
    title = title or ""
    for pattern, repl in TITLE_REPLACEMENTS.items():
        title = re.sub(pattern, repl, title, flags=re.IGNORECASE)

    parts = ["[NEW]"]
    if brand:
        parts.append(str(brand).strip())
    if gender and str(gender).strip().lower() == "unisex":
        parts.append("Unisex")
    if title:
        parts.append(title.strip())
    if is_footwear and footwear_color:
        parts.append(str(footwear_color).strip())

    # remove duplicate consecutive / anywhere words (case-insensitive), preserve first occurrence
    seen = set()
    deduped = []
    for word in " ".join(parts).split():
        key = word.lower()
        if key in seen and key not in ("[new]",):
            continue
        seen.add(key)
        deduped.append(word)
    return " ".join(deduped).strip()


def clean_description(raw_desc, style_number, care=None, care_label=None):
    """Clean description per spec section 4."""
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        raw_desc = ""
    desc = str(raw_desc)

    # Remove PRODUCT STORY heading
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)

    # Convert headings
    desc = re.sub(r"\bDETAILS\b", '"DETAILS"', desc, flags=re.IGNORECASE)
    desc = re.sub(
        r"FEATURES\s*(&|\+)\s*BENEFITS",
        '"FEATURES & BENEFITS"',
        desc,
        flags=re.IGNORECASE,
    )

    # Convert <li> to bullet (ensure newline separation between list items)
    desc = re.sub(r"<li[^>]*>", "\n- ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</li>", "\n", desc, flags=re.IGNORECASE)

    # Remove specified tags
    for tag in [r"<br\s*/?>", r"<ul[^>]*>", r"</ul>", r"<p[^>]*>", r"</p>"]:
        desc = re.sub(tag, "\n", desc, flags=re.IGNORECASE)

    # Strip any remaining stray HTML tags (safety net)
    desc = re.sub(r"<[^>]+>", "", desc)

    # Trim extra spaces / blank lines
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in desc.splitlines()]
    lines = [ln for ln in lines if ln != ""]
    desc = "\n".join(lines)

    # Append Style, CARE, CARE LABEL
    tail = [f"Style : {style_number}"]
    if care and str(care).strip().lower() not in ("nan", ""):
        tail.append(f'"CARE"\n{str(care).strip()}')
    if care_label and str(care_label).strip().lower() not in ("nan", ""):
        tail.append(f'"CARE LABEL"\n{str(care_label).strip()}')

    desc = desc + "\n\n" + "\n\n".join(tail)
    return desc.strip()


def is_footwear(product_type):
    if not product_type:
        return False
    return str(product_type).strip().lower() in ("footwear", "shoes", "trainers", "sandals", "slides")


def size_sort_key(size_val):
    """Sort key supporting alpha size order or ascending numeric."""
    s = str(size_val).strip().upper()
    if s in ALPHA_SIZE_ORDER:
        return (0, ALPHA_SIZE_ORDER.index(s), 0)
    try:
        num = float(re.sub(r"[^\d.]", "", s))
        return (1, 0, num)
    except (ValueError, TypeError):
        return (2, 0, s)


def match_category_id(title, category_df, keyword_col, id_col):
    if category_df is None or category_df.empty:
        return ""
    title_lower = str(title).lower()
    best_match = ""
    best_len = 0
    for _, row in category_df.iterrows():
        kw = str(row.get(keyword_col, "")).strip().lower()
        if kw and kw in title_lower and len(kw) > best_len:
            best_match = row.get(id_col, "")
            best_len = len(kw)
    return best_match


def match_size_chart(title, size_chart_df, key_col, url_col):
    if size_chart_df is None or size_chart_df.empty:
        return ""
    title_lower = str(title).lower()
    best_match = ""
    best_len = 0
    for _, row in size_chart_df.iterrows():
        kw = str(row.get(key_col, "")).strip().lower()
        if kw and kw in title_lower and len(kw) > best_len:
            best_match = row.get(url_col, "")
            best_len = len(kw)
    return best_match


def get_images_for_sku(sku, image_df, sku_col, image_cols):
    if image_df is None or image_df.empty:
        return []
    row = image_df[image_df[sku_col].astype(str) == str(sku)]
    if row.empty:
        return []
    row = row.iloc[0]
    imgs = []
    for c in image_cols:
        if c in row and pd.notna(row[c]) and str(row[c]).strip():
            imgs.append(str(row[c]).strip())
    return imgs


def get_price(sku, tracker_df, sku_col, price_col):
    if tracker_df is None or tracker_df.empty:
        return ""
    row = tracker_df[tracker_df[sku_col].astype(str) == str(sku)]
    if row.empty:
        return ""
    val = row.iloc[0].get(price_col, "")
    return val


# ======================================================================================
# CORE TRANSFORMATION
# ======================================================================================

def build_upload_sheet(master_df, tracker_df, image_df, size_chart_df, category_df, output_columns=None):
    mc = MASTER_COLS
    tc = TRACKER_COLS
    ic = IMAGE_SHEET_COLS
    sc = SIZE_CHART_COLS
    cc = CATEGORY_SHEET_COLS

    rows = []

    # Determine grouping key: footwear -> style+color, else -> style only
    def group_key(r):
        ptype = r.get(mc["product_type"], "")
        style = r.get(mc["style_no"], "")
        if is_footwear(ptype):
            color_no = r.get(mc["color_no"], "")
            return f"{style}__{color_no}"
        return f"{style}"

    master_df = master_df.copy()
    master_df["_group_key"] = master_df.apply(group_key, axis=1)

    for group_key_val, group_df in master_df.groupby("_group_key", sort=False):
        first = group_df.iloc[0]
        ptype = first.get(mc["product_type"], "")
        footwear = is_footwear(ptype)

        title = clean_title(
            first.get(mc["brand"], ""),
            first.get(mc["gender"], ""),
            first.get(mc["title"], ""),
            first.get(mc["footwear_color"], "") if footwear else "",
            footwear,
        )

        style_number = first.get(mc["style_no"], "")
        desc = clean_description(
            first.get(mc["description"], ""),
            style_number,
            first.get(mc["care"], None),
            first.get(mc["care_label"], None),
        )

        category_id = match_category_id(title, category_df, cc["keyword"], cc["category_id"])
        size_chart_url = match_size_chart(title, size_chart_df, sc["category_or_title"], sc["size_chart_url"])

        has_variants = len(group_df) > 1

        parent_row = {
            "Row Type": "Parent",
            "Title": title,
            "Description": desc,
            "Style Number": style_number,
            "Category ID": category_id,
            "Size Chart": size_chart_url,
            "Stock": 0,
            **DEFAULTS,
        }
        if not has_variants:
            single = group_df.iloc[0]
            sku = single.get(mc["sku"], "")
            parent_row["SKU"] = sku
            parent_row["Price"] = get_price(sku, tracker_df, tc["sku"], tc["price_col"])
            parent_row["Color Family"] = single.get(mc["color_family"], "")
            parent_row["Color Name"] = single.get(mc["color_name"], "")
            parent_row["Size"] = single.get(mc["size"], "")
            parent_row["UK Size"] = single.get(mc["uk_size"], "")
            parent_row["Images"] = "; ".join(
                get_images_for_sku(sku, image_df, ic["sku"], ic["image_cols"])
            )
            rows.append(parent_row)
            continue

        rows.append(parent_row)

        # Sort child rows: by color family/name, then by size order
        child_records = group_df.to_dict("records")
        child_records.sort(
            key=lambda r: (
                str(r.get(mc["color_family"], "")),
                str(r.get(mc["color_name"], "")),
                size_sort_key(r.get(mc["size"], "")),
            )
        )

        for rec in child_records:
            sku = rec.get(mc["sku"], "")
            child_row = {
                "Row Type": "Child",
                "Title": title,
                "Description": "",  # child rows: SKU-specific only, description lives on parent
                "Style Number": style_number,
                "Category ID": category_id,
                "Size Chart": size_chart_url,
                "Stock": 0,
                "SKU": sku,
                "Price": get_price(sku, tracker_df, tc["sku"], tc["price_col"]),
                "Color Family": rec.get(mc["color_family"], ""),
                "Color Name": rec.get(mc["color_name"], ""),
                "Size": rec.get(mc["size"], ""),
                "UK Size": rec.get(mc["uk_size"], ""),
                "Images": "; ".join(
                    get_images_for_sku(sku, image_df, ic["sku"], ic["image_cols"])
                ),
                **DEFAULTS,
            }
            rows.append(child_row)

    out_df = pd.DataFrame(rows)

    # If a sample format was provided, reorder/reindex columns to match exactly
    if output_columns:
        for col in output_columns:
            if col not in out_df.columns:
                out_df[col] = ""
        out_df = out_df[output_columns]

    return out_df


# ======================================================================================
# STREAMLIT UI
# ======================================================================================

st.set_page_config(page_title="Marketplace Upload Sheet Generator", layout="wide")
st.title("🛒 Marketplace Bulk Upload Sheet Generator")

st.markdown(
    """
Upload your source sheets below. Column-name mapping is configured at the top of
`app.py` (`MASTER_COLS`, `TRACKER_COLS`, etc.) — **edit those constants to match
your real spreadsheet headers** before running, since this app was built without
seeing your actual files.
"""
)

col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("Master Input Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="master")
    image_file = st.file_uploader("Image Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="images")
    category_file = st.file_uploader("Category Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="category")
with col2:
    tracker_file = st.file_uploader("Tracker Sheet - pricing (.xlsx/.csv)", type=["xlsx", "csv"], key="tracker")
    size_chart_file = st.file_uploader("Size Chart Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="sizechart")
    sample_file = st.file_uploader("Sample Upload Format (.xlsx/.csv) — optional, defines exact output columns", type=["xlsx", "csv"], key="sample")


def load_any(f):
    if f is None:
        return None
    if f.name.lower().endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)


if st.button("🚀 Generate Upload Sheet", type="primary"):
    if master_file is None:
        st.error("Master Input Sheet is required.")
    else:
        with st.spinner("Processing..."):
            master_df = load_any(master_file)
            tracker_df = load_any(tracker_file)
            image_df = load_any(image_file)
            size_chart_df = load_any(size_chart_file)
            category_df = load_any(category_file)
            sample_df = load_any(sample_file)

            output_columns = list(sample_df.columns) if sample_df is not None else None

            try:
                result_df = build_upload_sheet(
                    master_df, tracker_df, image_df, size_chart_df, category_df, output_columns
                )
            except KeyError as e:
                st.error(
                    f"Column mapping mismatch: {e}. "
                    "Please edit the CONFIG constants (MASTER_COLS, TRACKER_COLS, etc.) "
                    "at the top of app.py to match your actual sheet's column headers, then rerun."
                )
                st.stop()

        st.success(f"Generated {len(result_df)} rows ({(result_df['Row Type']=='Parent').sum()} parent, "
                   f"{(result_df['Row Type']=='Child').sum()} child).")
        st.dataframe(result_df, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Upload")
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Upload Sheet (.xlsx)",
            data=buffer,
            file_name="marketplace_upload_sheet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Upload your files and click **Generate Upload Sheet** to begin.")
