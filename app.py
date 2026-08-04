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
    "article": "Article Number",  # PIM Article Number column in the Master Sheet — used to look up price in Tracker Sheet (Tracker only has Article, not SKU)
    "description": "Description",
    "care": "Care",
    "care_label": "Care Label",
    "category_hint": "Category",  # optional, else derived from title
    "footwear_color": "Footwear Color",
    "product_type": "Product Type",  # e.g. Trainers / Sandals / Slides / Apparel / Accessories
    "division": "Product Division",  # e.g. Footwear / Apparel / Accessories — primary signal for grouping logic
}

TRACKER_COLS = {
    "article": "PIM Article",  # Tracker Sheet only has an Article column, not SKU
    "price_col": None,  # set at runtime via the Streamlit dropdown (user selects the price column)
}

IMAGE_SHEET_COLS = {
    "article": "Article No",  # Image Sheet is keyed by Article Number, not SKU
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

    # Remove <h3>PRODUCT STORY</h3> (and variations: extra spaces, lowercase tags, etc.)
    desc = re.sub(r"<h3[^>]*>\s*product\s*story\s*</h3>", "", desc, flags=re.IGNORECASE)
    # Safety net: also strip a bare "product story" heading text if it slipped through without a clean tag pair
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)

    # Convert <h3>DETAILS</h3> (and variations) -> two newlines + "DETAILS"
    desc = re.sub(r"<h3[^>]*>\s*DETAILS\s*</h3>", "\n\nDETAILS", desc, flags=re.IGNORECASE)
    # Convert <h3>FEATURES & BENEFITS</h3> / <h3>FEATURES + BENEFITS</h3> (and variations) -> two newlines + heading
    desc = re.sub(
        r"<h3[^>]*>\s*FEATURES\s*(&|\+)\s*BENEFITS\s*</h3>",
        "\n\nFEATURES & BENEFITS",
        desc,
        flags=re.IGNORECASE,
    )

    # Convert <li> to bullet; </li> is stripped out entirely (no injected newline) per spec
    desc = re.sub(r"<li[^>]*>", "\n- ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</li>", "", desc, flags=re.IGNORECASE)

    # Remove specified tags
    for tag in [r"<br\s*/?>", r"</br>", r"<ul[^>]*>", r"</ul>", r"<p[^>]*>", r"</p>"]:
        desc = re.sub(tag, "\n", desc, flags=re.IGNORECASE)

    # Strip any remaining stray HTML tags (safety net)
    desc = re.sub(r"<[^>]+>", "", desc)

    # Trim extra spaces, collapse runs of blank lines down to a single blank line
    # (preserves the intentional blank line before DETAILS / FEATURES & BENEFITS headings)
    raw_lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in desc.splitlines()]
    lines = []
    prev_blank = False
    for ln in raw_lines:
        if ln == "":
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        lines.append(ln)
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    desc = "\n".join(lines)

    # Append Style, CARE, CARE LABEL
    tail = [f"Style : {style_number}"]
    if care and str(care).strip().lower() not in ("nan", ""):
        tail.append(f"CARE\n{str(care).strip()}")
    if care_label and str(care_label).strip().lower() not in ("nan", ""):
        tail.append(f"CARE LABEL\n{str(care_label).strip()}")

    desc = desc + "\n\n" + "\n\n".join(tail)
    return desc.strip()


def is_footwear(division, product_type=None):
    """Determine footwear-ness primarily via Product Division (spec: 'using Product Division checks'),
    falling back to Product Type keyword matching if Division is blank/unavailable."""
    div = str(division).strip().lower() if division not in (None, "") and not (isinstance(division, float) and pd.isna(division)) else ""
    if div:
        return div == "footwear"
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


def get_images_for_article(article, image_df, article_col, image_cols):
    """Look up images in the Image Sheet by Article Number (the Image Sheet is
    keyed by Article No, not SKU, per spec)."""
    if image_df is None or image_df.empty or not article or str(article).strip() == "":
        return []
    row = image_df[image_df[article_col].astype(str).str.strip() == str(article).strip()]
    if row.empty:
        return []
    row = row.iloc[0]
    imgs = []
    for c in image_cols:
        if c in row and pd.notna(row[c]) and str(row[c]).strip():
            imgs.append(str(row[c]).strip())
    return imgs


def get_price(article, tracker_df, article_col, price_col):
    """Look up price in the Tracker Sheet by Article Number.

    The Tracker Sheet only contains a PIM Article column (no SKU), so the
    Master Sheet's Article Number for a given SKU must be resolved first and
    passed in here as `article`.
    """
    if tracker_df is None or tracker_df.empty or not article or str(article).strip() == "":
        return ""
    row = tracker_df[tracker_df[article_col].astype(str).str.strip() == str(article).strip()]
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
                        tracker_article_col="PIM Article", tracker_price_col=None,
                        master_cols=None, image_cols=None, sizechart_cols=None, category_cols=None,
                        region="PH", marketplace="Lazada"):
    mc = master_cols or MASTER_COLS
    tc = {"article": tracker_article_col, "price_col": tracker_price_col}
    ic = image_cols or IMAGE_SHEET_COLS
    sc = sizechart_cols or SIZE_CHART_COLS
    cc = category_cols or CATEGORY_SHEET_COLS

    currency_code = REGION_CURRENCY.get(region, "PHP")

    rows = []

    def group_key(r):
        division = r.get(mc["division"], "") if "division" in mc else ""
        ptype = r.get(mc["product_type"], "")
        style = r.get(mc["style_no"], "")
        if is_footwear(division, ptype):
            color_no = r.get(mc["color_no"], "")
            return f"{style}__{color_no}"
        return f"{style}"

    master_df = master_df.copy()
    master_df["_group_key"] = master_df.apply(group_key, axis=1)

    for group_key_val, group_df in master_df.groupby("_group_key", sort=False):
        first = group_df.iloc[0]
        division = first.get(mc["division"], "") if "division" in mc else ""
        ptype = first.get(mc["product_type"], "")
        footwear = is_footwear(division, ptype)

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
            "Product Specification 1": "Brand:PUMA",
            "Shipping Service Details": "Standard Local:40.00",
            "Region": region,
            "Marketplace": marketplace,
        }

        if not has_variants:
            single = group_df.iloc[0]
            sku = single.get(mc["sku"], "")
            article = single.get(mc["article"], "")
            color_family = single.get(mc["color_family"], "")
            uk_size = single.get(mc["uk_size"], "")
            row = {
                "Row Type": "Parent",
                **base_row,
                "SKU": sku,
                "RRP": get_price(article, tracker_df, tc["article"], tc["price_col"]),
                "Variation 1": single.get(mc["color_name"], ""),
                "Variation 2": uk_size,
                "Product Specification 2": f"sku.color_family={color_family}",
                "Product Specification 3": f"sku.size={uk_size}",
                "Stock": 0,
                "Images": "; ".join(get_images_for_article(article, image_df, ic["article"], ic["image_cols"])),
            }
            rows.append(row)
            continue

        parent_row = {
            "Row Type": "Parent",
            **base_row,
            "Variation 1": "Color Family",  # axis name, not a value — per spec
            "Variation 2": "Size",  # axis name, not a value — per spec
            "Stock": 0,
        }
        rows.append(parent_row)

        child_records = group_df.to_dict("records")
        child_records.sort(
            key=lambda r: (
                str(r.get(mc["color_family"], "")),
                str(r.get(mc["color_name"], "")),
                size_sort_key(r.get(mc["uk_size"], "")),
            )
        )

        for rec in child_records:
            sku = rec.get(mc["sku"], "")
            article = rec.get(mc["article"], "")
            color_family = rec.get(mc["color_family"], "")
            uk_size = rec.get(mc["uk_size"], "")
            child_row = {
                "Row Type": "Child",
                **base_row,
                "Description": "",  # child rows: SKU-specific only
                "SKU": sku,
                "RRP": get_price(article, tracker_df, tc["article"], tc["price_col"]),
                "Variation 1": rec.get(mc["color_name"], ""),
                "Variation 2": uk_size,
                "Product Specification 2": f"sku.color_family={color_family}",
                "Product Specification 3": f"sku.size={uk_size}",
                "Stock": 0,
                "Images": "; ".join(get_images_for_article(article, image_df, ic["article"], ic["image_cols"])),
            }
            rows.append(child_row)

    out_df = pd.DataFrame(rows)
    return out_df


# ======================================================================================
# STREAMLIT UI
# ======================================================================================

st.set_page_config(page_title="Marketplace Upload Sheet Generator", layout="wide")
st.title("🛒 Marketplace Bulk Upload Sheet Generator")

st.markdown(
    """
Upload your source sheets below. **Column mapping happens right here in the app** —
after you upload a file, dropdowns will appear so you can match each field to your
sheet's actual column headers. Nothing needs to be edited in `app.py`.
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


def guess_index(options, keywords):
    """Best-guess default index into `options` by substring match against `keywords`."""
    options_str = [str(o) for o in options]
    for kw in keywords:
        for i, o in enumerate(options_str):
            if kw.lower() in o.lower():
                return i
    return 0


NONE_LABEL = "-- None / not in this sheet --"


def mapped_select(label, options, keywords, key, allow_none=False, help_text=None):
    opts = ([NONE_LABEL] + list(options)) if allow_none else list(options)
    guessed = guess_index(options, keywords)
    idx = (guessed + 1) if allow_none else guessed
    choice = st.selectbox(label, options=opts, index=idx, key=key, help=help_text)
    return None if (allow_none and choice == NONE_LABEL) else choice


def excel_letter_to_index(letter):
    """Convert an Excel-style column letter ('A', 'H', 'BW', ...) to a 0-based column index.
    Returns None if the input isn't a valid letter sequence."""
    letter = str(letter).strip().upper()
    if not letter or not letter.isalpha():
        return None
    idx = 0
    for ch in letter:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def mapped_select_with_letter(label, df, keywords, key, help_text=None):
    """Column picker with an optional 'or column letter' override, for sheets whose real
    headers are blank/garbled (pandas shows these as 'Unnamed: N')."""
    options = list(df.columns)
    selected = mapped_select(label, options, keywords, key, help_text=help_text)
    letter = st.text_input(
        f"…or Excel column letter for \u201c{label}\u201d (only if the header above looks wrong, e.g. \u201cUnnamed: 8\u201d)",
        value="", key=f"{key}_letter",
    )
    if letter.strip():
        idx = excel_letter_to_index(letter)
        if idx is not None and 0 <= idx < len(df.columns):
            return df.columns[idx]
        else:
            st.warning(f"'{letter}' isn't a valid column letter for this sheet (it has {len(df.columns)} columns) — falling back to the dropdown selection.")
    return selected


# --- Master Sheet column mapping ---
master_cols_map = dict(MASTER_COLS)  # fallback defaults
if master_file is not None:
    _master_preview_df = load_any(master_file)
    master_file.seek(0)
    master_cols_available = list(_master_preview_df.columns)

    st.markdown("#### 📌 Master Sheet — Column Mapping")
    st.caption("Match each field below to the actual column header in your Master Sheet.")
    mm1, mm2, mm3 = st.columns(3)
    with mm1:
        master_cols_map["style_no"] = mapped_select("Style Number", master_cols_available, ["style"], "mc_style_no")
        master_cols_map["color_no"] = mapped_select("Color Number", master_cols_available, ["color no", "colour no", "color number"], "mc_color_no", allow_none=True)
        master_cols_map["division"] = mapped_select(
            "Product Division", master_cols_available, ["division"], "mc_division", allow_none=True,
            help_text="e.g. Footwear / Apparel / Accessories — used to decide grouping & UK-size handling. Leave as None if your sheet doesn't have this column; Product Type will be used instead.",
        )
        master_cols_map["brand"] = mapped_select("Brand", master_cols_available, ["brand"], "mc_brand")
        master_cols_map["gender"] = mapped_select("Gender", master_cols_available, ["gender"], "mc_gender")
        master_cols_map["title"] = mapped_select("Title / Display Name", master_cols_available, ["display name", "title"], "mc_title")
        master_cols_map["product_type"] = mapped_select("Product Type", master_cols_available, ["product type"], "mc_product_type")
    with mm2:
        master_cols_map["color_family"] = mapped_select("Color Family", master_cols_available, ["color family", "colour family"], "mc_color_family")
        master_cols_map["color_name"] = mapped_select("Color Name", master_cols_available, ["color name", "colour name"], "mc_color_name")
        master_cols_map["size"] = mapped_select("Size", master_cols_available, ["size"], "mc_size")
        master_cols_map["uk_size"] = mapped_select("UK Size", master_cols_available, ["uk size"], "mc_uk_size")
        master_cols_map["sku"] = mapped_select_with_letter(
            "SKU (EAN)", _master_preview_df, ["ean", "sku"], "mc_sku",
            help_text="If your sheet calls this 'EAN' rather than 'SKU', that's fine — EAN is used as the SKU value.",
        )
        master_cols_map["article"] = mapped_select_with_letter(
            "Article Number (Color No)", _master_preview_df, ["article", "color no", "colour no"], "mc_article",
            help_text="Used to look up price in the Tracker Sheet (keyed by PIM Article, not SKU). If your sheet calls this 'Color No' rather than 'Article Number', that's fine — Color No is used as the Article Number for pricing.",
        )
    with mm3:
        master_cols_map["description"] = mapped_select("Description", master_cols_available, ["description"], "mc_description")
        master_cols_map["care"] = mapped_select("Care", master_cols_available, ["care"], "mc_care", allow_none=True)
        master_cols_map["care_label"] = mapped_select("Care Label", master_cols_available, ["care label"], "mc_care_label", allow_none=True)
        master_cols_map["footwear_color"] = mapped_select("Footwear Color", master_cols_available, ["footwear color"], "mc_footwear_color", allow_none=True)


# --- Tracker column pickers (Article column + Price column) ---
# The Tracker Sheet only contains a PIM Article column, not SKU. The Master
# Sheet has both SKU and Article Number, so pricing is matched via:
#   SKU (Master row) -> Article Number (Master row) -> Article (Tracker row) -> Price
tracker_article_col = "PIM Article"
tracker_price_col = None

if tracker_file is not None:
    _tracker_preview_df = load_any(tracker_file)
    tracker_file.seek(0)  # reset pointer so it can be read again later
    tracker_cols_available = list(_tracker_preview_df.columns)

    st.markdown("#### 📌 Tracker Sheet — Column Selection")
    tcol1, tcol2 = st.columns(2)
    with tcol1:
        tracker_article_col = mapped_select_with_letter(
            "PIM Article column in Tracker Sheet", _tracker_preview_df, ["pim article", "article"],
            "tracker_article_col_select",
            help_text="The Tracker Sheet is keyed by PIM Article Number, not SKU. Select that column here.",
        )
    with tcol2:
        tracker_price_col = mapped_select_with_letter(
            "Price column to use (Original Price source)", _tracker_preview_df, ["original price", "price"],
            "tracker_price_col_select",
            help_text="Choose which column in the Tracker Sheet holds the price you want pulled into the upload sheet.",
        )


# --- Image Sheet column mapping ---
image_cols_map = dict(IMAGE_SHEET_COLS)
image_gsheet_url = st.text_input(
    "Image Sheet Google Sheets link (optional — paste instead of/in addition to uploading a file)",
    value="", key="image_gsheet_url",
    help="If your Image Sheet lives in Google Sheets, paste a link that ends in /export?format=csv (File > Share > Publish, or swap /edit... for /export?format=csv on a shared link). Uploading a file above still works too.",
)
if image_gsheet_url.strip():
    try:
        _gs_url = image_gsheet_url.strip()
        if "/export" not in _gs_url and "docs.google.com/spreadsheets" in _gs_url:
            _gs_url = re.sub(r"/edit.*$", "", _gs_url) + "/export?format=csv"
        _image_preview_df = pd.read_csv(_gs_url)
        image_cols_available = list(_image_preview_df.columns)
        st.success(f"Loaded {len(_image_preview_df)} rows from the Google Sheets link.")
    except Exception as e:
        st.error(f"Couldn't load that Google Sheets link ({e}). Make sure it's shared as 'Anyone with the link' and try again, or upload the file instead.")
        _image_preview_df = None
        image_cols_available = []
elif image_file is not None:
    _image_preview_df = load_any(image_file)
    image_file.seek(0)
    image_cols_available = list(_image_preview_df.columns)
else:
    _image_preview_df = None
    image_cols_available = []

if _image_preview_df is not None:
    st.markdown("#### 📌 Image Sheet — Column Selection")
    icol1, icol2 = st.columns(2)
    with icol1:
        image_cols_map["article"] = mapped_select_with_letter(
            "Article No column in Image Sheet", _image_preview_df, ["article no", "article"], "image_article_col",
            help_text="The Image Sheet is keyed by Article Number, matched at the SKU level (each SKU's Article Number is looked up here).",
        )
    with icol2:
        default_image_cols = [c for c in image_cols_available if "image" in str(c).lower()]
        image_cols_map["image_cols"] = st.multiselect(
            "Image columns (select all that apply, in order)",
            options=image_cols_available,
            default=default_image_cols,
            key="image_cols_select",
        )


# --- Size Chart Sheet column mapping ---
sizechart_cols_map = dict(SIZE_CHART_COLS)
if size_chart_file is not None:
    _sizechart_preview_df = load_any(size_chart_file)
    size_chart_file.seek(0)
    sizechart_cols_available = list(_sizechart_preview_df.columns)

    st.markdown("#### 📌 Size Chart Sheet — Column Selection")
    scol1, scol2 = st.columns(2)
    with scol1:
        sizechart_cols_map["category_or_title"] = mapped_select(
            "Category / Title match column", sizechart_cols_available, ["category", "title"], "sizechart_key_col"
        )
    with scol2:
        sizechart_cols_map["size_chart_url"] = mapped_select(
            "Size Chart URL column", sizechart_cols_available, ["size chart url", "url"], "sizechart_url_col"
        )


# --- Category Sheet column mapping ---
category_cols_map = dict(CATEGORY_SHEET_COLS)
if category_file is not None:
    _category_preview_df = load_any(category_file)
    category_file.seek(0)
    category_cols_available = list(_category_preview_df.columns)

    st.markdown("#### 📌 Category Sheet — Column Selection")
    ccol1, ccol2 = st.columns(2)
    with ccol1:
        category_cols_map["keyword"] = mapped_select(
            "Title Keyword column", category_cols_available, ["keyword", "title"], "category_keyword_col"
        )
    with ccol2:
        category_cols_map["category_id"] = mapped_select(
            "Category ID column", category_cols_available, ["category id", "category"], "category_id_col"
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
            image_df = _image_preview_df if image_gsheet_url.strip() else load_any(image_file)
            size_chart_df = load_any(size_chart_file)
            category_df = load_any(category_file)
            sample_df = load_any(sample_file)

            output_columns = list(sample_df.columns) if sample_df is not None else None

            try:
                result_df = build_upload_sheet(
                    master_df, tracker_df, image_df, size_chart_df, category_df,
                    tracker_article_col=tracker_article_col,
                    tracker_price_col=tracker_price_col,
                    master_cols=master_cols_map,
                    image_cols=image_cols_map,
                    sizechart_cols=sizechart_cols_map,
                    category_cols=category_cols_map,
                    region=selected_region,
                    marketplace=selected_marketplace,
                )
            except KeyError as e:
                st.error(
                    f"Column mapping mismatch: {e}. "
                    "Double-check the column mapping dropdowns above match your actual sheet headers, then rerun."
                )
                st.stop()

        st.success(f"Generated {len(result_df)} rows ({(result_df['Row Type']=='Parent').sum()} parent, "
                   f"{(result_df['Row Type']=='Child').sum()} child).")
        st.dataframe(result_df, use_container_width=True)

        # Build the exact-format export separately from the full working table above,
        # so a Sample Upload Format without a "Row Type" column (or any other internal
        # column) never breaks the on-screen preview/stats.
        if output_columns:
            export_df = result_df.copy()
            for col in output_columns:
                if col not in export_df.columns:
                    export_df[col] = ""
            export_df = export_df[output_columns]
        else:
            export_df = result_df

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Upload")
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Upload Sheet (.xlsx)",
            data=buffer,
            file_name="marketplace_upload_sheet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Upload your files and click **Generate Upload Sheet** to begin.")
