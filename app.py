import io
import re
import json
import pandas as pd
import numpy as np
import streamlit as st

# ======================================================================================
# EXACT OUTPUT SHEET HEADERS (68 COLUMNS)
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

# Region -> Currency Code mapping
REGION_CURRENCY = {
    "SG": "SGD",
    "MY": "MYR",
    "PH": "PHP",
}

MARKETPLACES = ["Lazada", "Shopee", "Zalora", "Tiktok"]
REGIONS = ["SG", "MY", "PH"]

ALPHA_SIZE_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "OSFA", "Youth"]

# ======================================================================================
# HELPERS
# ======================================================================================

def clean_title(brand, gender, regional_name):
    """Build standardized title."""
    parts = []
    if brand and pd.notna(brand):
        parts.append(str(brand).strip())
    if gender and pd.notna(gender):
        parts.append(str(gender).strip())
    if regional_name and pd.notna(regional_name):
        parts.append(str(regional_name).strip())

    seen = set()
    deduped = []
    for word in " ".join(parts).split():
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(word)
    return " ".join(deduped).strip()


def clean_description(raw_desc, style_number, care=None, care_label=None):
    """Clean description HTML and format properly."""
    if raw_desc is None or pd.isna(raw_desc):
        return ""
    desc = str(raw_desc)

    # Convert/Clean HTML structures
    desc = re.sub(r"<h3[^>]*>\s*product\s*story\s*</h3>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<h3[^>]*>\s*DETAILS\s*</h3>", "\n\nDETAILS", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<h3[^>]*>\s*FEATURES\s*(&|\+)\s*BENEFITS\s*</h3>", "\n\nFEATURES & BENEFITS", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<li[^>]*>", "\n- ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</li>", "", desc, flags=re.IGNORECASE)

    for tag in [r"<br\s*/?>", r"</br>", r"<ul[^>]*>", r"</ul>", r"<p[^>]*>", r"</p>"]:
        desc = re.sub(tag, "\n", desc, flags=re.IGNORECASE)

    desc = re.sub(r"<[^>]+>", "", desc)

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

    desc = "\n".join(lines).strip()

    tail = [f"Style : {style_number}"]
    if care and pd.notna(care) and str(care).strip().lower() != "nan":
        tail.append(f"CARE\n{str(care).strip()}")
    if care_label and pd.notna(care_label) and str(care_label).strip().lower() != "nan":
        tail.append(f"CARE LABEL\n{str(care_label).strip()}")

    return desc + "\n\n" + "\n\n".join(tail)


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
    return best_match if best_match else category_df.iloc[0].get('Category ID', '')


def get_price(ean, price_df):
    if price_df is None or price_df.empty or pd.isna(ean):
        return "", ""
    match = price_df[price_df['EAN'].astype(str).str.strip() == str(ean).strip()]
    if not match.empty:
        list_p = match.iloc[0].get('sg-list-prices', '')
        sale_p = match.iloc[0].get('sg-sale-prices', '')
        return list_p if pd.notna(list_p) else "", sale_p if pd.notna(sale_p) else ""
    return "", ""

# ======================================================================================
# CORE BUILD FUNCTION
# ======================================================================================

def build_upload_sheet(master_df, price_df, size_chart_df, category_df, size_template_df, region="SG"):
    currency_code = REGION_CURRENCY.get(region, "SGD")
    rows = []

    # Group by StyleNo and ColorNumber
    for (style_no, color_no), group in master_df.groupby(['StyleNo', 'ColorNumber'], sort=False):
        first = group.iloc[0]
        
        brand = first.get('Brand', 'PUMA')
        gender = first.get('Gender', '')
        regional_name = first.get('RegionalDisplayName', '')
        product_name = clean_title(brand, gender, regional_name)
        
        style_num = first.get('StyleNo', '')
        desc = clean_description(first.get('LongDescription', ''), style_num)
        
        category_id = match_category_id(product_name, category_df)
        
        size_chart_url = ""
        if size_chart_df is not None and not size_chart_df.empty:
            size_chart_url = size_chart_df.iloc[0].get('Size chart', '')
            
        template_attr_1 = ""
        if size_template_df is not None and not size_template_df.empty:
            template_attr_1 = size_template_df.iloc[0].get('Template', '')

        for _, rec in group.iterrows():
            ean = rec.get('EAN', '')
            color_name = rec.get('ColorName', '')
            size_uk = rec.get('SizeUK', '')
            
            list_price, sale_price = get_price(ean, price_df)
            if not list_price:
                list_price = rec.get('Price', '')

            # Create row initialized to 68 standard columns
            row_dict = {col: "" for col in OUTPUT_COLUMNS}
            
            row_dict['Graas SKU'] = str(ean)
            row_dict['Seller SKU'] = str(ean)
            row_dict['Product Name'] = product_name
            row_dict['Product Name (English)'] = product_name
            row_dict['Product Description 1'] = desc
            row_dict['Product Description(English) 1'] = desc
            row_dict['Total variation'] = len(group)
            row_dict['Variation 1'] = str(color_name)
            row_dict['Variation 2'] = str(size_uk)
            row_dict['SRP'] = list_price
            row_dict['RRP'] = sale_price if sale_price else list_price
            row_dict['Currency Code'] = currency_code
            row_dict['Quantity'] = 0
            row_dict['Product Image URL(s)'] = str(rec.get('Images', '')) if pd.notna(rec.get('Images')) else ""
            row_dict['Category ID'] = category_id
            row_dict['Tax Class'] = "Default"
            row_dict['Brand'] = brand
            row_dict['Model'] = str(style_num)
            row_dict['Warranty Type'] = "No Warranty"
            row_dict['Package Weight (kg)'] = 0.5
            row_dict['Package Height(cm)'] = 15
            row_dict['Package Length(cm)'] = 12
            row_dict['Package Width(cm)'] = 12
            row_dict["What's in the Box"] = f"1 x {product_name}"
            row_dict["What's in the Box(English)"] = f"1 x {product_name}"
            row_dict['Size chart Image URL'] = size_chart_url
            row_dict['Product Specification 1'] = f"Brand: {brand}"
            row_dict['Product Specification 2'] = f"Color: {color_name}"
            row_dict['Product Specification 3'] = f"Size: {size_uk}"
            row_dict['Template Attribute 1'] = template_attr_1
            row_dict['Post As Non Variant'] = "No"

            rows.append(row_dict)

    out_df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return out_df

# ======================================================================================
# STREAMLIT UI
# ======================================================================================

st.set_page_config(page_title="Marketplace Bulk Upload Sheet Generator", layout="wide")
st.title("🛒 Marketplace Bulk Upload Sheet Generator")

st.markdown("### 🌏 Region & Marketplace")
rcol1, rcol2 = st.columns(2)
with rcol1:
    selected_region = st.selectbox("Region", options=REGIONS, index=0)
with rcol2:
    selected_marketplace = st.selectbox("Marketplace", options=MARKETPLACES, index=0)

st.markdown("### 📁 Upload Input Sheets")
col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("Master Input Sheet (.xlsx)", type=["xlsx"], key="master")
    category_file = st.file_uploader("Category Sheet (.xlsx)", type=["xlsx"], key="category")
    price_file = st.file_uploader("Price Sheet (.xlsx)", type=["xlsx"], key="price")
with col2:
    size_chart_file = st.file_uploader("Size Chart Sheet (.xlsx)", type=["xlsx"], key="sizechart")
    size_template_file = st.file_uploader("Size Chart Template (.xlsx)", type=["xlsx"], key="sizetemplate")

def load_any(f):
    if f is None:
        return None
    return pd.read_excel(f)

if st.button("🚀 Generate Upload Sheet", type="primary"):
    if master_file is None:
        st.error("Master Input Sheet is required.")
    else:
        with st.spinner("Processing..."):
            master_df = load_any(master_file)
            price_df = load_any(price_file)
            size_chart_df = load_any(size_chart_file)
            category_df = load_any(category_file)
            size_template_df = load_any(size_template_file)

            result_df = build_upload_sheet(
                master_df, price_df, size_chart_df, category_df, size_template_df,
                region=selected_region
            )

        st.success(f"Successfully generated {len(result_df)} rows across {len(result_df.columns)} target headers!")
        st.dataframe(result_df, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Sheet1")
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Marketplace Bulk Upload Sheet (.xlsx)",
            data=buffer,
            file_name="Output_Sheet_Formatted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
