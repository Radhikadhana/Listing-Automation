import io
import re
import pandas as pd
import numpy as np
import streamlit as st

# ======================================================================================
# EXACT 68 HEADERS FROM OUTPUT SHEET
# ======================================================================================

OUTPUT_COLUMNS = [
    'Graas SKU', 'Status', 'Remarks', 'Seller SKU', 'Product Name', 'Product Name (English)',
    'Product Description 1', 'Product Description 2', 'Product Description 3',
    'Product Description(English) 1', 'Product Description(English) 2', 'Product Description(English) 3',
    'Total variation', 'Variation 1', 'Variation 2', 'Variation 3', 'Short Description',
    'Product Highlights \n(English)', 'SRP', 'Sale Start Date', 'Sale End Date', 'RRP',
    'Currency Code', 'Quantity', 'Product Image URL(s)', 'Category ID', 'Tax Class', 'Brand',
    'Model', 'Warranty Type', 'Package Weight (kg)', 'Package Height(cm)', 'Package Length(cm)',
    'Package Width(cm)', "What's in the Box", "What's in the Box(English)", 'Size chart Image URL',
    'Product Specification 1', 'Product Specification 2', 'Product Specification 3',
    'Product Specification 4', 'Product Specification 5', 'Product Specification 6',
    'Product Specification 7', 'Product Specification 8', 'Product Specification 9',
    'Product Specification 10', 'Product Specification 11', 'Product Specification 12',
    'Product Specification 13', 'Product Specification 14', 'Product Specification 15',
    'Product Specification 16', 'Product Specification 17', 'Product Specification 18',
    'Product Specification 19', 'Product Specification 20', 'Product Specification 21',
    'Product Specification 22', 'Product Specification 23', 'Product Specification 24',
    'Product Specification 25', 'Template Attribute 1', 'Template Attribute 2',
    'Template Attribute 3', 'Template Attribute 4', 'Template Attribute 5', 'Post As Non Variant'
]

# Replacement map for titles
TITLE_REPLACEMENTS = [
    (r"\bTrainers\b", "Shoes"),
    (r"\bSandals\b", "Sports Sandals"),
    (r"\bSlides\b", "Slides Slippers"),
]

# Alpha size sorting sequence
ALPHA_SIZE_ORDER = [
    "3XS", "XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "XXXL", "4XL", "XXXXL", "OSFA", "Youth"
]

# Default Sizechart Template Mapping fallback
DEFAULT_SIZECHART_TEMPLATE_MAP = {
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

# ======================================================================================
# HELPER FUNCTIONS
# ======================================================================================

def is_footwear(division, product_type):
    div = str(division).strip().lower() if pd.notna(division) else ""
    ptype = str(product_type).strip().lower() if pd.notna(product_type) else ""
    return div == "footwear" or ptype in ["footwear", "shoes", "trainers", "sandals", "slides"]

def clean_title(brand, gender, regional_display_name, color_name, footwear):
    title = str(regional_display_name) if pd.notna(regional_display_name) else ""
    for pattern, repl in TITLE_REPLACEMENTS:
        title = re.sub(pattern, repl, title, flags=re.IGNORECASE)

    parts = ["[NEW]"]
    if pd.notna(brand) and str(brand).strip():
        parts.append(str(brand).strip())
    if pd.notna(gender) and str(gender).strip().lower() == "unisex":
        parts.append("Unisex")
    if title:
        parts.append(title.strip())
    if footwear and pd.notna(color_name) and str(color_name).strip():
        parts.append(str(color_name).strip())

    # Remove duplicate words while keeping first occurrence
    seen = set()
    deduped = []
    for word in " ".join(parts).split():
        key = word.lower()
        if key in seen and key != "[new]":
            continue
        seen.add(key)
        deduped.append(word)
    return " ".join(deduped).strip()

def clean_description(raw_desc, style_number, care=None, care_label=None):
    if raw_desc is None or pd.isna(raw_desc):
        desc = ""
    else:
        desc = str(raw_desc)

    # 1. Clean HTML tags per specification
    desc = re.sub(r"<h3[^>]*>\s*product\s*story\s*</h3>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<h3[^>]*>\s*DETAILS\s*</h3>", "\n\nDETAILS", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<h3[^>]*>\s*FEATURES\s*(&|\+)\s*BENEFITS\s*</h3>", "\n\nFEATURES & BENEFITS", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<li[^>]*>", "\r\n- ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</li>", "", desc, flags=re.IGNORECASE)

    for tag in [r"<br\s*/?>", r"</br>", r"<ul[^>]*>", r"</ul>", r"<p[^>]*>", r"</p>"]:
        desc = re.sub(tag, "", desc, flags=re.IGNORECASE)

    desc = re.sub(r"<[^>]+>", "", desc)

    raw_lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in desc.splitlines()]
    lines = [ln for ln in raw_lines if ln]
    desc = "\n".join(lines).strip()

    # Appending Metadata
    tail = [f"- Style : {style_number}"]
    if care and pd.notna(care) and str(care).strip().lower() not in ("nan", ""):
        tail.append(f"CARE\n{str(care).strip()}")
    if care_label and pd.notna(care_label) and str(care_label).strip().lower() not in ("nan", ""):
        tail.append(f"CARE LABEL\n{str(care_label).strip()}")

    return desc + "\n\n" + "\n\n".join(tail)

def extract_description_content(raw_desc):
    if raw_desc is None or pd.isna(raw_desc):
        return ""
    desc = str(raw_desc)
    desc = re.sub(r"<h3[^>]*>\s*product\s*story\s*</h3>", "", desc, flags=re.IGNORECASE)
    split_match = re.search(r"(FEATURES\s*(&|\+)\s*BENEFITS|DETAILS)", desc, flags=re.IGNORECASE)
    main_part = desc[:split_match.start()] if split_match else desc
    main_part = main_part.strip()
    if main_part and not main_part.lower().startswith("<p>"):
        main_part = f"<p>{main_part}</p>"
    return f"description={main_part}" if main_part else ""

def extract_features_and_details(raw_desc):
    if raw_desc is None or pd.isna(raw_desc):
        return ""
    desc = str(raw_desc)
    match = re.search(r"(FEATURES\s*(&|\+)\s*BENEFITS.*)", desc, flags=re.IGNORECASE | re.DOTALL)
    story_part = match.group(1).strip() if match else ""
    return f"productstory={story_part}" if story_part else ""

def size_sort_key(size_val):
    s = str(size_val).strip().upper() if pd.notna(size_val) else ""
    if s in ALPHA_SIZE_ORDER:
        return (0, ALPHA_SIZE_ORDER.index(s), 0)
    try:
        num = float(re.sub(r"[^\d.]", "", s))
        return (1, 0, num)
    except (ValueError, TypeError):
        return (2, 0, s)

def format_variation_2(size_val, division):
    val = str(size_val).strip() if pd.notna(size_val) else ""
    div = str(division).strip().lower() if pd.notna(division) else ""
    if div == "footwear":
        return f"UK: {val}"
    return f"Int: {val}"

def match_category_id(title, category_df):
    if category_df is None or category_df.empty:
        return ""
    title_lower = str(title).lower()
    best_match, best_len = "", 0
    for _, row in category_df.iterrows():
        cat_name = str(row.get('Category', '')).strip().lower()
        if cat_name and cat_name in title_lower and len(cat_name) > best_len:
            best_match = row.get('Category ID', '')
            best_len = len(cat_name)
    return best_match if best_match else (category_df.iloc[0].get('Category ID', '') if 'Category ID' in category_df.columns else "")

def get_price(ean, price_df, price_col_letter=None):
    if price_df is None or price_df.empty or pd.isna(ean):
        return ""
    
    # If user selected a specific column letter for price in Price Sheet
    if price_col_letter:
        col_idx = ord(price_col_letter.upper()) - ord('A')
        if 0 <= col_idx < len(price_df.columns):
            price_col_name = price_df.columns[col_idx]
            match = price_df[price_df['EAN'].astype(str).str.strip() == str(ean).strip()]
            if not match.empty:
                val = match.iloc[0].get(price_col_name, "")
                if pd.notna(val):
                    return val

    # Default lookup logic
    match = price_df[price_df['EAN'].astype(str).str.strip() == str(ean).strip()]
    if not match.empty:
        for p_col in ['sg-list-prices', 'sg-sale-prices', 'Price']:
            if p_col in match.columns and pd.notna(match.iloc[0].get(p_col)):
                return match.iloc[0].get(p_col)
    return ""

def get_image_url(ean, image_df):
    if image_df is None or image_df.empty or pd.isna(ean):
        return ""
    for col in image_df.columns:
        if "ean" in col.lower() or "article" in col.lower() or "sku" in col.lower():
            match = image_df[image_df[col].astype(str).str.strip() == str(ean).strip()]
            if not match.empty:
                img_cols = [c for c in image_df.columns if "image" in c.lower() or "url" in c.lower()]
                imgs = [str(match.iloc[0][c]).strip() for c in img_cols if pd.notna(match.iloc[0][c])]
                return "; ".join(imgs)
    return ""

# ======================================================================================
# CORE GENERATION PROCESS
# ======================================================================================

def build_upload_sheet(master_df, price_df, category_df, size_chart_df, size_template_df, image_df, price_col_letter=None):
    rows = []

    def get_group_key(r):
        div = r.get('ProductDivision', '')
        ptype = r.get('ArticleType', '')
        style = str(r.get('StyleNo', '')).strip()
        if is_footwear(div, ptype):
            color = str(r.get('ColorNumber', '')).strip()
            return f"{style}__{color}"
        return style

    master_df['_group_key'] = master_df.apply(get_group_key, axis=1)

    for group_key, group in master_df.groupby('_group_key', sort=False):
        first = group.iloc[0]
        division = first.get('ProductDivision', '')
        ptype = first.get('ArticleType', '')
        footwear = is_footwear(division, ptype)

        brand = first.get('Brand', 'PUMA')
        gender = first.get('Gender', '')
        display_name = first.get('RegionalDisplayName', '')
        color_name = first.get('ColorName', '')
        title = clean_title(brand, gender, display_name, color_name, footwear)

        style_no = first.get('StyleNo', '')
        raw_desc = first.get('LongDescription', '')
        cleaned_desc = clean_description(raw_desc, style_no, first.get('Care'), first.get('CareLabel'))

        category_id = match_category_id(title, category_df)

        size_chart_url = ""
        if size_chart_df is not None and not size_chart_df.empty:
            size_chart_url = size_chart_df.iloc[0].get('Size chart', '')

        size_chart_template = ""
        if size_template_df is not None and not size_template_df.empty:
            size_chart_template = size_template_df.iloc[0].get('Template', '')
        else:
            size_chart_template = DEFAULT_SIZECHART_TEMPLATE_MAP.get(first.get('ArticleGroup', ''), "")

        desc_content = extract_description_content(raw_desc)
        features_details = extract_features_and_details(raw_desc)

        total_variants = len(group)
        has_variants = total_variants > 1

        # Common Base Map for 68 Output Columns
        base_map = {col: "" for col in OUTPUT_COLUMNS}
        base_map['Product Name'] = title
        base_map['Product Name (English)'] = title
        base_map['Currency Code'] = "PHP"
        base_map['Quantity'] = 0
        base_map['Category ID'] = category_id
        base_map['Tax Class'] = "default"
        base_map['Brand'] = brand
        base_map['Model'] = str(style_no)
        base_map['Warranty Type'] = "No Warranty"
        base_map['Package Weight (kg)'] = 0.5
        base_map['Package Height(cm)'] = 15
        base_map['Package Length(cm)'] = 12
        base_map['Package Width(cm)'] = 12
        base_map["What's in the Box"] = f"1 X {title}"
        base_map["What's in the Box(English)"] = f"1 X {title}"
        base_map['Size chart Image URL'] = size_chart_url
        base_map['Product Specification 1'] = "Brand: PUMA"
        base_map['Template Attribute 1'] = size_chart_template
        base_map['Template Attribute 2'] = desc_content
        base_map['Template Attribute 3'] = features_details
        base_map['Post As Non Variant'] = "No"

        # -------------------------------------------------------------------------
        # PARENT ROW INSERTION (If variants exist)
        # -------------------------------------------------------------------------
        if has_variants:
            parent_row = base_map.copy()
            parent_sku = str(first.get('EAN', ''))
            parent_row['Graas SKU'] = parent_sku
            parent_row['Seller SKU'] = parent_sku
            parent_row['Product Description 1'] = cleaned_desc
            parent_row['Product Description(English) 1'] = cleaned_desc
            parent_row['Total variation'] = total_variants
            parent_row['Variation 1'] = str(first.get('SearchColorName', 'color_family'))
            parent_row['Variation 2'] = "size"
            
            # Parent RRP price fallback
            p_price = get_price(parent_sku, price_df, price_col_letter)
            parent_row['RRP'] = p_price if p_price else first.get('Price', '')
            parent_row['SRP'] = parent_row['RRP']
            
            rows.append(parent_row)

        # -------------------------------------------------------------------------
        # CHILD ROWS / SINGLE ROW
        # -------------------------------------------------------------------------
        child_records = group.to_dict('records')
        child_records.sort(key=lambda x: size_sort_key(x.get('SizeUK', '')))

        for rec in child_records:
            child_row = base_map.copy()
            ean = str(rec.get('EAN', ''))
            v1_color = str(rec.get('ColorName', ''))
            v2_size = format_variation_2(rec.get('SizeUK', ''), division)

            price_val = get_price(ean, price_df, price_col_letter)
            if not price_val:
                price_val = rec.get('Price', '')

            img_urls = get_image_url(ean, image_df)

            child_row['Graas SKU'] = ean
            child_row['Seller SKU'] = ean
            child_row['Product Description 1'] = cleaned_desc
            child_row['Product Description(English) 1'] = cleaned_desc
            child_row['Total variation'] = total_variants if has_variants else 1
            child_row['Variation 1'] = v1_color
            child_row['Variation 2'] = v2_size
            child_row['RRP'] = price_val
            child_row['SRP'] = price_val
            child_row['Product Image URL(s)'] = img_urls
            child_row['Product Specification 2'] = f"sku.color_family={v1_color}"
            child_row['Product Specification 3'] = f"sku.size={v2_size}"

            rows.append(child_row)

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)

# ======================================================================================
# STREAMLIT USER INTERFACE
# ======================================================================================

st.set_page_config(page_title="Marketplace Bulk Upload Sheet Generator", layout="wide")
st.title("🛒 Marketplace Bulk Upload Sheet Generator")

st.markdown("### 📁 Upload Required Input Sheets")

col1, col2 = st.columns(2)

with col1:
    master_file = st.file_uploader("1. Master Input Sheet (.xlsx)", type=["xlsx"], key="master")
    category_file = st.file_uploader("2. Category Sheet (.xlsx)", type=["xlsx"], key="category")
    image_file = st.file_uploader("3. Image Sheet (.xlsx)", type=["xlsx"], key="image")

with col2:
    price_file = st.file_uploader("4. Price Sheet (.xlsx)", type=["xlsx"], key="price")
    price_col_letter = st.text_input("Price Column Letter in Price Sheet (Optional, e.g. D or E)", value="")
    size_chart_file = st.file_uploader("5. Size Chart Sheet (.xlsx)", type=["xlsx"], key="sizechart")
    size_template_file = st.file_uploader("6. Size Chart Template (.xlsx)", type=["xlsx"], key="sizetemplate")

def load_excel(f):
    return pd.read_excel(f) if f is not None else None

if st.button("🚀 Generate Output Sheet", type="primary"):
    if master_file is None:
        st.error("Master Input Sheet is required.")
    else:
        with st.spinner("Processing files and applying transformation rules..."):
            master_df = load_excel(master_file)
            price_df = load_excel(price_file)
            category_df = load_excel(category_file)
            size_chart_df = load_excel(size_chart_file)
            size_template_df = load_excel(size_template_file)
            image_df = load_excel(image_file)

            out_df = build_upload_sheet(
                master_df, price_df, category_df, size_chart_df,
                size_template_df, image_df, price_col_letter
            )

        st.success(f"Successfully generated {len(out_df)} rows with exactly 68 standard output columns!")
        st.dataframe(out_df, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            out_df.to_excel(writer, index=False, sheet_name="Sheet1")
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Updated Bulk Output Sheet (.xlsx)",
            data=buffer,
            file_name="Output_Sheet_Updated.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
