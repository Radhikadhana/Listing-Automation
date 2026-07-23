import streamlit as st
import pandas as pd
import numpy as np
import re
import io

# ==========================================
# 1. HELPERS & UTILITY FUNCTIONS
# ==========================================

# Standard size order map for logical size sorting
SIZE_ORDER = [
    "3XS", "XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL", "4XL", "5XL",
    "OSFA", "1-2Y", "3-4Y", "5-6Y", "7-8Y", "9-10Y", "11-12Y", "13-14Y", "Youth"
]
SIZE_RANK = {size.upper(): idx for idx, size in enumerate(SIZE_ORDER)}

def parse_size_sort_key(size_str: str):
    """
    Sorts size variants logically:
    - Standard letter sizes / age ranges follow SIZE_ORDER sequence.
    - Purely numerical sizes (e.g. shoe sizes) are sorted numerically in ascending order.
    """
    if pd.isna(size_str) or str(size_str).strip() == "":
        return (2, 0)
    
    clean_size = str(size_str).strip().upper()
    
    # Try parsing numeric size
    try:
        num_val = float(clean_size)
        return (1, num_val)
    except ValueError:
        pass
    
    # Text-based sequence mapping
    if clean_size in SIZE_RANK:
        return (0, SIZE_RANK[clean_size])
    
    # Fallback default alphanumeric
    return (2, clean_size)

def clean_title(title: str, brand: str, gender: str, regional_name: str, color: str, division: str) -> str:
    """
    Rule 1: Title construction & term cleanup.
    Format: [NEW] [Brand] [Gender (if Unisex)] [Regional Display Name] [Color (if Footwear)]
    """
    title_parts = ["[NEW]", str(brand).strip()]
    
    # Add gender if Unisex
    g_str = str(gender).strip()
    if "UNISEX" in g_str.upper():
        title_parts.append(g_str)
        
    # Regional Display Name or fallback title
    disp_name = str(regional_name).strip() if pd.notna(regional_name) else str(title).strip()
    
    # Clean up specific terms
    disp_name = re.sub(r'\bTrainers\b', 'Shoes', disp_name, flags=re.IGNORECASE)
    disp_name = re.sub(r'\bSandals\b', 'Sports Sandals', disp_name, flags=re.IGNORECASE)
    disp_name = re.sub(r'\bSlides\b', 'Slides Slippers', disp_name, flags=re.IGNORECASE)
    title_parts.append(disp_name)
    
    # Add color if Footwear
    div_str = str(division).strip().lower()
    if "footwear" in div_str and pd.notna(color) and str(color).strip() != "":
        title_parts.append(str(color).strip())
        
    # Remove duplicate words while preserving exact word order
    full_title = " ".join(title_parts)
    words = full_title.split()
    seen = set()
    deduped_words = []
    for w in words:
        w_lower = w.lower()
        if w_lower not in seen:
            seen.add(w_lower)
            deduped_words.append(w)
            
    return " ".join(deduped_words)

def clean_description(raw_desc: str, style_val: str, care_val: str, care_label_val: str) -> str:
    """
    Rule 3 & 4: Description cleanup, regex replacements, and metadata appending.
    """
    if pd.isna(raw_desc):
        desc = ""
    else:
        desc = str(raw_desc)
        
    # Remove variations of PRODUCT STORY header
    desc = re.sub(r'<h3>\s*PRODUCT STORY\s*</h3>', '', desc, flags=re.IGNORECASE)
    
    # Remove line breaks
    desc = re.sub(r'</?br\s*/?>', '', desc, flags=re.IGNORECASE)
    
    # Replace DETAILS tags
    desc = re.sub(r'<h3>\s*DETAILS\s*</h3>', '\n\nDETAILS', desc, flags=re.IGNORECASE)
    
    # Replace FEATURES & BENEFITS / FEATURES + BENEFITS tags
    desc = re.sub(r'<h3>\s*FEATURES\s*(&|\+)\s*BENEFITS\s*</h3>', '\n\nFEATURES & BENEFITS', desc, flags=re.IGNORECASE)
    
    # Replace <li> tags with newline and bullet point
    desc = re.sub(r'<li>', '\r\n- ', desc, flags=re.IGNORECASE)
    
    # Strip out </li>, <ul>, </ul>, <p>, and </p> tags
    desc = re.sub(r'</?(li|ul|p)>', '', desc, flags=re.IGNORECASE)
    
    desc = desc.strip()
    
    # Append Metadata
    if pd.notna(style_val) and str(style_val).strip() != "":
        desc += f"\n- Style : {str(style_val).strip()}"
        
    if pd.notna(care_val) and str(care_val).strip() != "":
        desc += f"\n\nCARE\n{str(care_val).strip()}"
        
    if pd.notna(care_label_val) and str(care_label_val).strip() != "":
        desc += f"\n\nCARE LABEL\n{str(care_label_val).strip()}"
        
    return desc

# ==========================================
# 2. OUTPUT GENERATION ENGINE
# ==========================================

def process_marketplace_transformation(df_input, df_tracker, price_col, df_category, df_sizechart, df_images):
    """
    Groups, converts, sorts sizes, inserts Parent rows, maps prices/images, and formats output.
    """
    # Create Price Map from Tracker sheet using dynamic price column selection
    price_map = {}
    if "SKU" in df_tracker.columns and price_col in df_tracker.columns:
        df_tracker["SKU_Clean"] = df_tracker["SKU"].astype(str).str.strip()
        price_map = df_tracker.set_index("SKU_Clean")[price_col].to_dict()

    # Image Mapping Lookup
    image_map = {}
    if "Style Number" in df_images.columns and "Image URL" in df_images.columns:
        df_images["Style_Clean"] = df_images["Style Number"].astype(str).str.strip()
        image_map = df_images.set_index("Style_Clean")["Image URL"].to_dict()

    # Sizechart Image Mapping Lookup
    sizechart_map = {}
    if "Title" in df_sizechart.columns and "Sizechart URL" in df_sizechart.columns:
        df_sizechart["Title_Clean"] = df_sizechart["Title"].astype(str).str.strip()
        sizechart_map = df_sizechart.set_index("Title_Clean")["Sizechart URL"].to_dict()

    output_rows = []

    # Grouping key determination based on Style Number
    group_col = "Style Number" if "Style Number" in df_input.columns else "SKU"
    grouped = df_input.groupby(group_col, sort=False)

    for style_id, group_df in grouped:
        # Logical Size Sorting for variants
        group_df = group_df.copy()
        size_field = "UK Size" if "UK Size" in group_df.columns else "Size"
        if size_field in group_df.columns:
            group_df["sort_key"] = group_df[size_field].apply(parse_size_sort_key)
            group_df = group_df.sort_values(by="sort_key").drop(columns=["sort_key"])

        first_row = group_df.iloc[0]
        brand_val = first_row.get("Brand", "PUMA")
        gender_val = first_row.get("Gender", "")
        regional_name = first_row.get("Regional Display Name", "")
        color_val = first_row.get("Color", "")
        division_val = first_row.get("Product Division", "")
        color_family_val = first_row.get("Color Family", color_val)

        # Form formatted Parent Title
        parent_title = clean_title(
            title=first_row.get("Product Title", ""),
            brand=brand_val,
            gender=gender_val,
            regional_name=regional_name,
            color=color_val,
            division=division_val
        )

        cleaned_desc = clean_description(
            raw_desc=first_row.get("Description", ""),
            style_val=style_id,
            care_val=first_row.get("Care", ""),
            care_label_val=first_row.get("Care Label", "")
        )

        sizechart_url = sizechart_map.get(str(parent_title).strip(), "")
        img_url = image_map.get(str(style_id).strip(), first_row.get("Image URL", ""))

        # Create PARENT Row if group has multiple rows
        if len(group_df) > 1:
            parent_row_data = {
                "SKU": f"PARENT_{style_id}",
                "Parent SKU": "",
                "Row Type": "Parent",
                "Product Title": parent_title,
                "Brand": "PUMA",
                "Price": "",
                "Stock": 0,
                "Currency": "PHP",
                "Warranty": "No Warranty",
                "Package Weight (kg)": "0.5",
                "Package Height (cm)": "15",
                "Package Length (cm)": "12",
                "Package Width (cm)": "12",
                "Shipping Service": "Standard Local:40.00",
                "Size Chart Image URL": sizechart_url,
                "Image URL": img_url,
                "Description": cleaned_desc,
                "Variation 1 Name": "color_family",
                "Variation 1 Value": color_family_val,
                "Variation 2 Name": "size",
                "Variation 2 Value": ""
            }
            output_rows.append(parent_row_data)

        # Process CHILD Rows
        for _, child_row in group_df.iterrows():
            child_sku = str(child_row.get("SKU", "")).strip()
            
            # Retrieve price from Tracker Sheet using dynamic price column
            price_val = price_map.get(child_sku)
            if pd.isna(price_val) or price_val is None:
                price_val = "ERROR - Price Missing"

            size_val = child_row.get(size_field, "")

            child_row_data = {
                "SKU": child_sku if child_sku else "ERROR - SKU Missing",
                "Parent SKU": f"PARENT_{style_id}" if len(group_df) > 1 else "",
                "Row Type": "Child",
                "Product Title": parent_title,
                "Brand": "PUMA",
                "Price": price_val,
                "Stock": 0,
                "Currency": "PHP",
                "Warranty": "No Warranty",
                "Package Weight (kg)": "0.5",
                "Package Height (cm)": "15",
                "Package Length (cm)": "12",
                "Package Width (cm)": "12",
                "Shipping Service": "Standard Local:40.00",
                "Size Chart Image URL": sizechart_url,
                "Image URL": img_url,
                "Description": cleaned_desc,
                "Variation 1 Name": "color_family",
                "Variation 1 Value": child_row.get("Color Name", color_val),
                "Variation 2 Name": "size",
                "Variation 2 Value": size_val
            }
            output_rows.append(child_row_data)

    return pd.DataFrame(output_rows)

# ==========================================
# 3. STREAMLIT UI CONTROLLER
# ==========================================

st.set_page_config(page_title="Marketplace Converter Engine", page_icon="🛍️", layout="wide")

st.title("🛍️ Marketplace Output Generator Engine")
st.markdown("Upload required input files to build formatted parent-child marketplace outputs.")

st.sidebar.header("📋 Required Inputs")

uploaded_master = st.sidebar.file_uploader("1. Master Input Sheet", type=["csv", "xlsx"])
uploaded_tracker = st.sidebar.file_uploader("2. Tracker Sheet", type=["csv", "xlsx"])
uploaded_category = st.sidebar.file_uploader("3. Category Sheet", type=["csv", "xlsx"])
uploaded_sizechart = st.sidebar.file_uploader("4. Size Chart Sheet", type=["csv", "xlsx"])
uploaded_images = st.sidebar.file_uploader("5. Images Sheet", type=["csv", "xlsx"])

# Target Price Column Alphabet Selection
price_column_alphabet = st.sidebar.text_input(
    "6. Tracker Price Column Name / Alphabet",
    value="PHP Price",
    help="Enter exact column name (e.g., 'PHP Price') or column header in Tracker Sheet."
)

if uploaded_master and uploaded_tracker and uploaded_category and uploaded_sizechart and uploaded_images:
    if st.button("🚀 Process & Generate Marketplace Output Sheet", type="primary"):
        with st.spinner("Processing sheets, sorting sizes, and formatting metadata..."):
            try:
                # Helper reader
                def read_file(file):
                    if file.name.endswith(".csv"):
                        return pd.read_csv(file)
                    return pd.read_excel(file)

                df_master = read_file(uploaded_master)
                df_tracker = read_file(uploaded_tracker)
                df_category = read_file(uploaded_category)
                df_sizechart = read_file(uploaded_sizechart)
                df_images = read_file(uploaded_images)

                df_output = process_marketplace_transformation(
                    df_master, df_tracker, price_column_alphabet, df_category, df_sizechart, df_images
                )

                st.success(f"Successfully processed {len(df_output):,} rows!")
                
                st.subheader("📊 Output Preview")
                st.dataframe(df_output.head(100), use_container_width=True)

                # Export Download Option
                csv_buffer = io.BytesIO()
                df_output.to_csv(csv_buffer, index=False)

                st.download_button(
                    label="📥 Download Converted Marketplace CSV",
                    data=csv_buffer.getvalue(),
                    file_name="Marketplace_Output_Converted.csv",
                    mime="text/csv",
                    type="primary"
                )

            except Exception as e:
                st.error(f"Error processing files: {str(e)}")
else:
    st.info("Please upload all 5 required sheets in the sidebar to begin processing.")
