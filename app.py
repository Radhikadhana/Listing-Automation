"""
Marketplace Bulk Upload Sheet Generator
========================================
Streamlit app that takes:
  - Master Input Sheet (product data, including price)
  - Image Sheet (SKU -> image URLs)
  - Size Chart Template Sheet (category/title -> size chart template attribute)
  - Category Sheet (title keyword -> category ID)
  - Sample Upload Format (defines exact output columns/order — REQUIRED)

...and produces a marketplace-ready bulk upload file (Parent/Child rows,
cleaned titles & descriptions, variations, images, category IDs, size chart
template values, prices, defaults, stock=0, shipping, product specification).

CHANGES IN THIS VERSION:
  - Tracker Sheet (separate pricing file) REMOVED. Price is now read straight
    from a price column on the Master Input Sheet.
  - Size Chart Sheet REPLACED with a Size Chart Template Sheet: instead of
    matching free-text title keywords to a URL, this matches a Size Chart Key
    (built from Age Group / Gender / Article Group / Article Type, same as
    before) to a Template Attribute 1 string you define directly in that sheet.
  - Output columns now STRICTLY follow the Sample Upload Format headers.
    The Sample Upload Format file is now REQUIRED (not optional) — the app
    will not guess an output layout on its own.

IMPORTANT: Column name constants below are BEST-GUESS based on the spec you
provided. Once you share your actual sheets, update the CONFIG section
(search for "ADJUST ME") to match your real column headers exactly.
"""

import io
import re
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
    "price": "Price",              # NEW: price now lives on the Master Sheet directly
    "description": "Description",
    "care": "Care",
    "care_label": "Care Label",
    "category_hint": "Category",   # optional, else derived from title
    "footwear_color": "Footwear Color",
    "product_type": "Product Type",  # e.g. Trainers / Sandals / Slides / Apparel / Accessories
    "age_group": "Age Group",
    "article_group": "Article Group",
    "article_type": "Article Type",
}

IMAGE_SHEET_COLS = {
    "sku": "SKU",
    "image_cols": ["Image 1", "Image 2", "Image 3", "Image 4", "Image 5", "Image 6", "Image 7", "Image 8", "Image 9"],
}

# Size Chart TEMPLATE sheet (replaces old free-text Size Chart Sheet).
# Expected columns: a lookup key (Age Group-Gender-Article Group-Article Type,
# same composite key used elsewhere) and the literal Template Attribute 1 value
# to place on the row — no keyword matching, no URL, just a direct key lookup.
SIZE_CHART_TEMPLATE_COLS = {
    "key": "Size Chart Key",                 # e.g. "Adult-Men-Tops-Tee"
    "template_attribute_1": "Template Attribute 1",  # literal string to output, e.g. "sizechart=Men Tops"
}

CATEGORY_SHEET_COLS = {
    "keyword": "Title Keyword",
    "category_id": "Category ID",
}

# Region -> Currency Code mapping
REGION_CURRENCY = {
    "SG": "SGD",
    "MY": "MYR",
    "PH": "PHP",
}

MARKETPLACES = ["Lazada", "Shopee", "Zalora", "Tiktok"]
REGIONS = ["SG", "MY", "PH"]

USER_TEMPLATE_NAME = "userTemplate-PumaAccessories"

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


def build_size_chart_key(age_group, gender, article_group, article_type):
    """Composite lookup key used against the Size Chart Template Sheet."""
    parts = [age_group, gender, article_group, article_type]
    return "-".join(str(p).strip() if p is not None else "" for p in parts)


def match_size_chart_template(size_chart_key, size_chart_template_df, key_col, attr_col):
    """
    Direct key lookup (NOT keyword/title matching) against the Size Chart
    Template Sheet. Returns the literal Template Attribute 1 string, or ""
    if the key isn't found.
    """
    if size_chart_template_df is None or size_chart_template_df.empty:
        return ""
    match = size_chart_template_df[
        size_chart_template_df[key_col].astype(str).str.strip() == str(size_chart_key).strip()
    ]
    if match.empty:
        return ""
    return match.iloc[0].get(attr_col, "")


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


def get_price(row, price_col):
    """Price now comes straight from the Master Sheet row (no Tracker Sheet lookup)."""
    if price_col not in row or pd.isna(row.get(price_col, None)):
        return ""
    return row.get(price_col, "")


def extract_description_main(raw_desc):
    """Extract the plain main description content (before DETAILS/FEATURES sections) for Template Attribute 2."""
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        return ""
    desc = str(raw_desc)
    desc = re.sub(r"<p>\s*product\s*story\s*</p>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)
    split_pattern = re.compile(r"(FEATURES\s*(&|\+)\s*BENEFITS|DETAILS)", re.IGNORECASE)
    match = split_pattern.search(desc)
    main_part = desc[:match.start()] if match else desc
    main_part = main_part.strip()
    if main_part and not re.match(r"^\s*<p", main_part, flags=re.IGNORECASE):
        main_part = f"<p>{main_part}</p>"
    return f"description={main_part}"


def extract_productstory(raw_desc):
    """Extract FEATURES & BENEFITS + DETAILS sections (raw HTML) for Template Attribute 3."""
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        return ""
    desc = str(raw_desc)
    match = re.search(r"(FEATURES\s*(&|\+)\s*BENEFITS.*)", desc, flags=re.IGNORECASE | re.DOTALL)
    story_part = match.group(1).strip() if match else ""
    return f"productstory={story_part}" if story_part else ""


# ======================================================================================
# CORE TRANSFORMATION
# ======================================================================================

def build_upload_sheet(master_df, image_df, size_chart_template_df, category_df,
                        output_columns, price_col,
                        region="PH", marketplace="Lazada"):
    mc = MASTER_COLS
    ic = IMAGE_SHEET_COLS
    sct = SIZE_CHART_TEMPLATE_COLS
    cc = CATEGORY_SHEET_COLS

    currency_code = REGION_CURRENCY.get(region, "PHP")

    rows = []

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
        raw_desc = first.get(mc["description"], "")
        desc = clean_description(
            raw_desc,
            style_number,
            first.get(mc["care"], None),
            first.get(mc["care_label"], None),
        )

        category_id = match_category_id(title, category_df, cc["keyword"], cc["category_id"])

        # --- Size Chart Template lookup (replaces old free-text Size Chart Sheet) ---
        size_chart_key = build_size_chart_key(
            first.get(mc["age_group"], ""),
            first.get(mc["gender"], ""),
            first.get(mc["article_group"], ""),
            first.get(mc["article_type"], ""),
        )
        template_attr_1 = match_size_chart_template(
            size_chart_key, size_chart_template_df, sct["key"], sct["template_attribute_1"]
        )

        template_attr_2 = extract_description_main(raw_desc)
        template_attr_3 = extract_productstory(raw_desc)

        total_variation_count = len(group_df)
        has_variants = total_variation_count > 1

        base_row = {
            "Product Description 1": USER_TEMPLATE_NAME,
            "Title": title,
            "Description": desc,
            "Total variation": total_variation_count,
            "Currency Code": currency_code,
            "Quantity": 0,
            "Category ID": category_id,
            "Tax Class": "Default",
            "Brand": "PUMA",
            "Model": style_number,
            "Warranty Type": "No Warranty",
            "Package Weight (kg)": 0.5,
            "Package Height(cm)": 15,
            "Package Length(cm)": 12,
            "Package Width(cm)": 12,
            "What's in the Box": f"1 X {title}",
            "Template Attribute 1": template_attr_1,
            "Template Attribute 2": template_attr_2,
            "Template Attribute 3": template_attr_3,
            "Region": region,
            "Marketplace": marketplace,
        }

        if not has_variants:
            single = group_df.iloc[0]
            sku = single.get(mc["sku"], "")
            color_family = single.get(mc["color_family"], "")
            uk_size = single.get(mc["uk_size"], "")
            row = {
                "Row Type": "Parent",
                **base_row,
                "SKU": sku,
                "RRP": get_price(single, price_col),
                "Variation 1": single.get(mc["color_name"], ""),
                "Variation 2": uk_size,
                "Product Specification 1": f"sku.color_family={color_family}",
                "Product Specification 2": f"sku.size={uk_size}",
                "Stock": 0,
                "Images": "; ".join(get_images_for_sku(sku, image_df, ic["sku"], ic["image_cols"])),
            }
            rows.append(row)
            continue

        parent_row = {
            "Row Type": "Parent",
            **base_row,
            "Stock": 0,
        }
        rows.append(parent_row)

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
            color_family = rec.get(mc["color_family"], "")
            uk_size = rec.get(mc["uk_size"], "")
            child_row = {
                "Row Type": "Child",
                **base_row,
                "Description": "",  # child rows: SKU-specific only
                "SKU": sku,
                "RRP": get_price(rec, price_col),
                "Variation 1": rec.get(mc["color_name"], ""),
                "Variation 2": uk_size,
                "Product Specification 1": f"sku.color_family={color_family}",
                "Product Specification 2": f"sku.size={uk_size}",
                "Stock": 0,
                "Images": "; ".join(get_images_for_sku(sku, image_df, ic["sku"], ic["image_cols"])),
            }
            rows.append(child_row)

    out_df = pd.DataFrame(rows)

    # Output STRICTLY follows the Sample Upload Format headers — no extra columns,
    # no reordering, missing ones filled blank.
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
`app.py` (`MASTER_COLS`, `IMAGE_SHEET_COLS`, etc.) — **edit those constants to match
your real spreadsheet headers** before running, since this app was built without
seeing your actual files.

**Note:** the Tracker Sheet has been removed — price is now read directly from a
column on the Master Input Sheet. The Size Chart Sheet has been replaced with a
Size Chart Template Sheet (direct key → Template Attribute 1 lookup, no keyword
matching). The **Sample Upload Format is now required** — output columns/order will
always match it exactly.
"""
)

st.markdown("### 🌏 Region & Marketplace")
rcol1, rcol2 = st.columns(2)
with rcol1:
    selected_region = st.selectbox("Region", options=REGIONS, index=REGIONS.index("PH"))
with rcol2:
    selected_marketplace = st.selectbox("Marketplace", options=MARKETPLACES, index=MARKETPLACES.index("Lazada"))

st.markdown("### 📁 Source Files")
col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("Master Input Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="master")
    image_file = st.file_uploader("Image Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="images")
    category_file = st.file_uploader("Category Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="category")
with col2:
    size_chart_template_file = st.file_uploader(
        "Size Chart Template Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="sizecharttemplate"
    )
    sample_file = st.file_uploader(
        "Sample Upload Format (.xlsx/.csv) — REQUIRED, defines exact output columns",
        type=["xlsx", "csv"], key="sample",
    )


def load_any(f):
    if f is None:
        return None
    if f.name.lower().endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)


# --- Master Sheet price column picker ---
price_col = MASTER_COLS["price"]

if master_file is not None:
    _master_preview_df = load_any(master_file)
    master_file.seek(0)  # reset pointer so it can be read again later
    master_cols_available = list(_master_preview_df.columns)

    st.markdown("#### 📌 Master Sheet — Price Column Selection")
    default_price_idx = (
        master_cols_available.index(price_col) if price_col in master_cols_available else 0
    )
    price_col = st.selectbox(
        "Price column in Master Input Sheet",
        options=master_cols_available,
        index=default_price_idx,
        key="master_price_col_select",
        help="Choose which column in the Master Input Sheet holds the price to pull into the upload sheet.",
    )


if st.button("🚀 Generate Upload Sheet", type="primary"):
    if master_file is None:
        st.error("Master Input Sheet is required.")
    elif sample_file is None:
        st.error("Sample Upload Format is required — it defines the exact output columns/order.")
    else:
        with st.spinner("Processing..."):
            master_df = load_any(master_file)
            image_df = load_any(image_file)
            size_chart_template_df = load_any(size_chart_template_file)
            category_df = load_any(category_file)
            sample_df = load_any(sample_file)

            output_columns = list(sample_df.columns)

            try:
                result_df = build_upload_sheet(
                    master_df, image_df, size_chart_template_df, category_df, output_columns,
                    price_col=price_col,
                    region=selected_region,
                    marketplace=selected_marketplace,
                )
            except KeyError as e:
                st.error(
                    f"Column mapping mismatch: {e}. "
                    "Please edit the CONFIG constants (MASTER_COLS, IMAGE_SHEET_COLS, "
                    "SIZE_CHART_TEMPLATE_COLS, CATEGORY_SHEET_COLS) at the top of app.py "
                    "to match your actual sheet's column headers, then rerun."
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
