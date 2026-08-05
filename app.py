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
    "price_col": None,  # set at runtime via the Streamlit dropdown (user selects the price column)
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

# Region -> Currency Code mapping
REGION_CURRENCY = {
    "SG": "SGD",
    "MY": "MYR",
    "PH": "PHP",
}

MARKETPLACES = ["Lazada", "Shopee", "Zalora", "Tiktok"]
REGIONS = ["SG", "MY", "PH"]

# sizechart value (from Size Chart Sheet match) -> fixed Template Attribute 1 string
SIZECHART_TEMPLATE_MAP = {
    "Infant Clothing": "sizechart=Infant Clothing",
    "Kids Clothing": "sizechart=Kids Clothing",
    "Women Tops": "sizechart=Women Tops",
    "Men Tops": "sizechart=Men Tops",
    "Mens Btm": "sizechart=Mens Btm",
    "Women Skirt": "sizechart=Women Skirt",
    "Boys Tops": "sizechart=Boys Tops",
    "Girls Tops": "sizechart=Girls Tops",
    "Women Btm": "sizechart=Women Btm",
    "Women Footwear": "sizechart=Women Footwear",
    "Cap": "sizechart=Cap",
    "Kids Footwear": "sizechart=Kids Footwear",
    "Mens Footwear": "sizechart=Mens Footwear",
    "Women Bra": "sizechart=Women Bra",
    "Men Socks": "sizechart=Men Socks",
}

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


def build_size_chart_template_attribute(size_chart_label):
    """Map the matched Size Chart Sheet label to its fixed Template Attribute 1 string."""
    if not size_chart_label:
        return ""
    label = str(size_chart_label).strip()
    return SIZECHART_TEMPLATE_MAP.get(label, f"sizechart={label}" if label else "")


# ======================================================================================
# CORE TRANSFORMATION
# ======================================================================================

def build_upload_sheet(master_df, tracker_df, image_df, size_chart_df, category_df,
                        output_columns=None, tracker_sku_col="SKU", tracker_price_col=None,
                        region="PH", marketplace="Lazada"):
    mc = MASTER_COLS
    tc = {"sku": tracker_sku_col, "price_col": tracker_price_col}
    ic = IMAGE_SHEET_COLS
    sc = SIZE_CHART_COLS
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
        size_chart_url = match_size_chart(title, size_chart_df, sc["category_or_title"], sc["size_chart_url"])
        size_chart_label = match_size_chart(title, size_chart_df, sc["category_or_title"], sc["category_or_title"])

        total_variation_count = len(group_df)
        has_variants = total_variation_count > 1

        template_attr_1 = build_size_chart_template_attribute(size_chart_label)
        template_attr_2 = extract_description_main(raw_desc)
        template_attr_3 = extract_productstory(raw_desc)

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
            "size chart Image URL": size_chart_url,
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
                "RRP": get_price(sku, tracker_df, tc["sku"], tc["price_col"]),
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
                "RRP": get_price(sku, tracker_df, tc["sku"], tc["price_col"]),
                "Variation 1": rec.get(mc["color_name"], ""),
                "Variation 2": uk_size,
                "Product Specification 1": f"sku.color_family={color_family}",
                "Product Specification 2": f"sku.size={uk_size}",
                "Stock": 0,
                "Images": "; ".join(get_images_for_sku(sku, image_df, ic["sku"], ic["image_cols"])),
            }
            rows.append(child_row)

    out_df = pd.DataFrame(rows)

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
    tracker_file = st.file_uploader("Tracker Sheet - pricing (.xlsx/.csv)", type=["xlsx", "csv"], key="tracker")
    size_chart_file = st.file_uploader("Size Chart Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="sizechart")
    sample_file = st.file_uploader("Sample Upload Format (.xlsx/.csv) — optional, defines exact output columns", type=["xlsx", "csv"], key="sample")


def load_any(f):
    if f is None:
        return None
    if f.name.lower().endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)


# --- Tracker column pickers (SKU column + Price column) ---
tracker_sku_col = "SKU"
tracker_price_col = None

if tracker_file is not None:
    _tracker_preview_df = load_any(tracker_file)
    tracker_file.seek(0)  # reset pointer so it can be read again later
    tracker_cols_available = list(_tracker_preview_df.columns)

    st.markdown("#### 📌 Tracker Sheet — Column Selection")
    tcol1, tcol2 = st.columns(2)
    with tcol1:
        tracker_sku_col = st.selectbox(
            "SKU column in Tracker Sheet",
            options=tracker_cols_available,
            index=tracker_cols_available.index("SKU") if "SKU" in tracker_cols_available else 0,
            key="tracker_sku_col_select",
        )
    with tcol2:
        tracker_price_col = st.selectbox(
            "Price column to use (Original Price source)",
            options=tracker_cols_available,
            key="tracker_price_col_select",
            help="Choose which column in the Tracker Sheet holds the price you want pulled into the upload sheet.",
        )


if st.button("🚀 Generate Upload Sheet", type="primary"):
    if master_file is None:
        st.error("Master Input Sheet is required.")
    elif tracker_file is not None and tracker_price_col is None:
        st.error("Please select a Price column from the Tracker Sheet.")
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
                    master_df, tracker_df, image_df, size_chart_df, category_df, output_columns,
                    tracker_sku_col=tracker_sku_col,
                    tracker_price_col=tracker_price_col,
                    region=selected_region,
                    marketplace=selected_marketplace,
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
