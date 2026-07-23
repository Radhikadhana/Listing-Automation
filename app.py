import streamlit as st
import pandas as pd
import numpy as np
import io

# ==========================================
# 1. HELPER FUNCTIONS & LOGIC UTILITIES
# ==========================================

def get_selected_region():
    """Requirement 1: Region Selection Sidebar Widget"""
    return st.sidebar.selectbox(
        "Select Marketplace Region",
        options=["SG", "MY", "PH"],
        index=0,
        help="All region-specific price columns will update dynamically based on this selection."
    )

def construct_price_map(df_price: pd.DataFrame) -> dict:
    """Requirement 7: Construct fast lookup dictionary for prices."""
    price_map = {}
    if "SKU" in df_price.columns:
        # Strip whitespace from SKU strings
        df_price["SKU"] = df_price["SKU"].astype(str).str.strip()
        price_map = df_price.set_index("SKU").to_dict(orient="index")
    return price_map

def get_region_price(sku: str, region: str, price_map: dict) -> str:
    """Requirement 3 & 8: Retrieve price for region or return explicit error."""
    if not sku or pd.isna(sku) or str(sku).strip() == "" or str(sku) == "nan":
        return "ERROR - SKU Missing"
    
    sku_str = str(sku).strip()
    col_name = f"{region} Price"  # e.g., 'SG Price', 'MY Price', 'PH Price'
    
    if sku_str in price_map:
        row = price_map[sku_str]
        price_val = row.get(col_name) or row.get(f"{region}_Price") or row.get(f"Cost{region}")
        if pd.notna(price_val) and str(price_val).strip() != "":
            return price_val
            
    return "ERROR - Price Missing"

def get_category_id(row: pd.Series) -> str:
    """
    Requirement 4 & 8: Intelligent Category ID Assignment
    Rules:
    - Sneakers -> Sneakers Category
    - Polo -> Polo Category
    - Tights / Leggings -> Pants Category
    - Unisex -> Men's Category when required
    - Boys/Girls/Youth/Kids -> Kids Category
    - Prefer Sports Category over Fashion
    """
    title = str(row.get("Product Title", "")).lower()
    gender = str(row.get("Gender", "")).lower()
    division = str(row.get("Product Division", "")).lower()
    article = str(row.get("Article Type", "")).lower()
    activity = str(row.get("Activity Group", "")).lower()

    combined_text = f"{title} {division} {article} {activity}"

    # Check for missing critical fields
    if not title and not article:
        return "ERROR - Category Missing"

    # Rule 1: Kids / Boys / Girls / Youth
    if any(k in gender for k in ["boy", "girl", "youth", "kid"]) or any(k in combined_text for k in ["kids", "youth", "junior"]):
        if "sport" in combined_text:
            return "CAT_KIDS_SPORTS"
        return "CAT_KIDS_GENERAL"

    # Rule 2: Sneakers
    if "sneaker" in combined_text or "shoe" in combined_text or "footwear" in combined_text:
        if "sport" in combined_text or "running" in activity:
            return "CAT_SPORTS_SNEAKERS"
        return "CAT_SNEAKERS"

    # Rule 3: Polo
    if "polo" in combined_text:
        if "sport" in combined_text:
            return "CAT_SPORTS_POLO"
        return "CAT_POLO"

    # Rule 4: Tights / Leggings
    if any(p in combined_text for p in ["tight", "legging", "pant"]):
        if "sport" in combined_text or "gym" in activity:
            return "CAT_SPORTS_PANTS"
        return "CAT_PANTS"

    # Rule 5: Gender-based defaults & Unisex handling
    if "unisex" in gender:
        return "CAT_MENS_UNISEX" if "sport" not in combined_text else "CAT_SPORTS_UNISEX"
    elif "women" in gender or "female" in gender:
        return "CAT_WOMENS_GENERAL"
    elif "men" in gender or "male" in gender:
        return "CAT_MENS_GENERAL"

    # Rule 6: Prefer Sports over Fashion fallback
    if "sport" in combined_text or "performance" in combined_text:
        return "CAT_SPORTS_GENERAL"

    return "CAT_GENERAL_FASHION"

def get_quantity() -> int:
    """Requirement 5: Quantity fixed to 0 for all items."""
    return 0

# ==========================================
# 2. OUTPUT TRANSFORM ENGINE
# ==========================================

def fill_parent_row(group_df: pd.DataFrame, region: str, price_map: dict) -> dict:
    """Requirement 6 & 7: Construct Parent Row metadata without changing structure."""
    first_row = group_df.iloc[0]
    parent_sku = first_row.get("Parent SKU") or first_row.get("SKU")
    
    if pd.isna(parent_sku) or str(parent_sku).strip() == "":
        parent_sku = "ERROR - SKU Missing"

    cat_id = get_category_id(first_row)
    price = get_region_price(parent_sku, region, price_map)

    return {
        "SKU": parent_sku,
        "Parent SKU": "",
        "Row Type": "Parent",
        "Product Title": first_row.get("Product Title", ""),
        "Category ID": cat_id,
        "Price": price,
        "Quantity": get_quantity(),
        "Gender": first_row.get("Gender", ""),
        "Product Division": first_row.get("Product Division", ""),
        "Article Type": first_row.get("Article Type", ""),
        "Activity Group": first_row.get("Activity Group", ""),
        "Size": "",
        "Color": first_row.get("Color", ""),
        "Image URL": first_row.get("Image URL", ""),
        "Description": first_row.get("Description", "")
    }

def fill_child_row(child_row: pd.Series, region: str, price_map: dict) -> dict:
    """Requirement 6 & 7: Construct Child Row metadata."""
    sku = child_row.get("SKU")
    parent_sku = child_row.get("Parent SKU")
    
    sku_val = "ERROR - SKU Missing" if (pd.isna(sku) or str(sku).strip() == "") else str(sku).strip()
    cat_id = get_category_id(child_row)
    price = get_region_price(sku_val, region, price_map)

    return {
        "SKU": sku_val,
        "Parent SKU": parent_sku,
        "Row Type": "Child",
        "Product Title": child_row.get("Product Title", ""),
        "Category ID": cat_id,
        "Price": price,
        "Quantity": get_quantity(),
        "Gender": child_row.get("Gender", ""),
        "Product Division": child_row.get("Product Division", ""),
        "Article Type": child_row.get("Article Type", ""),
        "Activity Group": child_row.get("Activity Group", ""),
        "Size": child_row.get("Size", ""),
        "Color": child_row.get("Color", ""),
        "Image URL": child_row.get("Image URL", ""),
        "Description": child_row.get("Description", "")
    }

def generate_output(df_input: pd.DataFrame, df_price: pd.DataFrame, region: str) -> pd.DataFrame:
    """
    Requirement 2, 7 & 9: Generate Output Sheet efficiently with vector/batch loops.
    Optimized for high performance (20,000+ SKUs).
    """
    price_map = construct_price_map(df_price)
    output_rows = []

    # Ensure required parent-child grouping field exists
    group_col = "Parent SKU" if "Parent SKU" in df_input.columns else "SKU"

    # Group by Parent SKU to preserve Parent/Child variant structure
    grouped = df_input.groupby(group_col, sort=False)

    for group_sku, group_df in grouped:
        # Create Parent Row
        parent_data = fill_parent_row(group_df, region, price_map)
        output_rows.append(parent_data)

        # Create Child Rows
        for _, child_row in group_df.iterrows():
            child_data = fill_child_row(child_row, region, price_map)
            output_rows.append(child_data)

    out_df = pd.DataFrame(output_rows)
    
    # Requirement 2: Fixed Column Order
    columns_order = [
        "SKU", "Parent SKU", "Row Type", "Product Title", "Category ID",
        "Price", "Quantity", "Gender", "Product Division", "Article Type",
        "Activity Group", "Size", "Color", "Image URL", "Description"
    ]
    
    # Reindex to ensure strict header alignment
    out_df = out_df.reindex(columns=columns_order)
    return out_df

# ==========================================
# 3. STREAMLIT UI LAYOUT & CONTROLLER
# ==========================================

st.set_page_config(page_title="Marketplace Sheet Converter", page_icon="⚡", layout="wide")

st.title("⚡ Marketplace Sheet Converter")
st.markdown("Convert inventory and catalog sheets with region-specific pricing and category logic.")

selected_region = get_selected_region()

st.sidebar.markdown("---")
st.sidebar.info(f"**Current Region:** `{selected_region}`")

col1, col2 = st.columns(2)

with col1:
    uploaded_input = st.file_uploader("Upload Input Data Sheet (CSV / Excel)", type=["csv", "xlsx"])

with col2:
    uploaded_price = st.file_uploader("Upload Price Sheet (CSV / Excel)", type=["csv", "xlsx"])

if uploaded_input and uploaded_price:
    try:
        # Load sheets into Pandas (Requirement 9: Fast memory reading)
        with st.spinner("Processing files..."):
            if uploaded_input.name.endswith(".csv"):
                df_input = pd.read_csv(uploaded_input)
            else:
                df_input = pd.read_excel(uploaded_input)

            if uploaded_price.name.endswith(".csv"):
                df_price = pd.read_csv(uploaded_price)
            else:
                df_price = pd.read_excel(uploaded_price)

            # Generate converted dataset
            converted_df = generate_output(df_input, df_price, selected_region)

        st.success(f"Processing complete for region **{selected_region}**! ({len(converted_df):,} total rows processed)")

        # Preview section
        st.subheader("📊 Output Preview")
        st.dataframe(converted_df.head(50), use_container_width=True)

        # File Export / Download options
        csv_buffer = io.BytesIO()
        converted_df.to_csv(csv_buffer, index=False)

        st.download_button(
            label="📥 Download Converted CSV Sheet",
            data=csv_buffer.getvalue(),
            file_name=f"Marketplace_Output_{selected_region}.csv",
            mime="text/csv",
            type="primary"
        )

    except Exception as e:
        st.error(f"Error processing files: {str(e)}")
else:
    st.info("Please upload both the **Input Sheet** and **Price Sheet** to begin processing.")
