import streamlit as st
from logic import (
    build_output_workbook,
    ConversionError,
    get_sheet_headers,
    REGION_CURRENCY,
)

st.set_page_config(page_title="Product Feed Generator", layout="wide")

st.title("📦 Product Feed & Variant Generator")
st.markdown(
    "Upload your main tracker workbook (or upload standalone reference sheets) "
    "to process parent/child variants and generate feed output."
)

# ---------------------------------------------------------------------------
# Sidebar Settings
# ---------------------------------------------------------------------------
st.sidebar.header("Configuration Settings")

region = st.sidebar.selectbox(
    "Region",
    ["SG", "MY", "PH"],
    index=2,
    format_func=lambda r: {"SG": "SG (Singapore)", "MY": "MY (Malaysia)", "PH": "PH (Philippines)"}[r],
    help="All output data (currency, and region-specific Price/Category/Size sheets if present) is generated for this region.",
)
currency_code = REGION_CURRENCY[region]
st.sidebar.caption(f"Currency for this region: **{currency_code}**")

price_col_setting = st.sidebar.text_input(
    "Fallback Price Column (Letter/Header) in Input Sheet",
    value="D",
    help="Used only if a SKU's price isn't found in the Price Tracker below.",
)

st.subheader("1. File Uploads")

col1, col2 = st.columns(2)

with col1:
    input_file = st.file_uploader(
        "Upload Main Workbook (.xlsx)",
        type=["xlsx"],
        help="Workbook containing 'Input', 'Price Sheet', 'Category sheet', 'Size chart', etc.",
    )

with col2:
    st.markdown("**Optional Standalone Overrides:**")
    price_file = st.file_uploader("Price Tracker / Price Sheet (.xlsx)", type=["xlsx"], key="price")
    category_file = st.file_uploader("Category Sheet (.xlsx)", type=["xlsx"], key="cat")
    size_chart_file = st.file_uploader("Size Chart Sheet (.xlsx)", type=["xlsx"], key="size")
    sample_output_file = st.file_uploader("Sample Output Sheet (For Custom Column Headers)", type=["xlsx"], key="sample")

st.markdown("---")

# ---------------------------------------------------------------------------
# 2. Price column picker — populated dynamically from whatever Price Tracker
#    was actually supplied (standalone file takes priority over the tab
#    inside the main workbook).
# ---------------------------------------------------------------------------
st.subheader("2. Price Column Selection")

price_headers = []
price_source_bytes = None
price_sheet_hint = None

if price_file is not None:
    price_source_bytes = price_file.getvalue()
elif input_file is not None:
    price_source_bytes = input_file.getvalue()
    price_sheet_hint = "Price Sheet"

if price_source_bytes:
    try:
        price_headers = get_sheet_headers(price_source_bytes, sheet_name=price_sheet_hint)
    except Exception:
        price_headers = []

if price_headers:
    price_column_name = st.selectbox(
        "Price column to use from the Price Tracker (e.g. Selling Price, Promo Price, Marketplace Price)",
        price_headers,
    )
else:
    price_column_name = None
    st.info("Upload your main workbook or a standalone Price Tracker above to choose which price column to use.")

st.markdown("---")

# ---------------------------------------------------------------------------
# 3. Generate
# ---------------------------------------------------------------------------
st.subheader("3. Generate Feed")

if st.button("🚀 Process & Generate Feed", type="primary"):
    if not input_file:
        st.error("Please upload the main input Excel file before proceeding.")
    elif not price_column_name:
        st.error("Please select a Price Column from the Price Tracker before proceeding.")
    else:
        try:
            with st.spinner("Processing rows, colors, size UK, category mapping, and template attributes..."):
                input_bytes = input_file.getvalue()
                price_bytes = price_file.getvalue() if price_file else None
                category_bytes = category_file.getvalue() if category_file else None
                size_chart_bytes = size_chart_file.getvalue() if size_chart_file else None
                sample_output_bytes = sample_output_file.getvalue() if sample_output_file else None

                output_bytes = build_output_workbook(
                    input_bytes=input_bytes,
                    price_bytes=price_bytes,
                    category_bytes=category_bytes,
                    size_chart_bytes=size_chart_bytes,
                    sample_output_bytes=sample_output_bytes,
                    region=region,
                    price_col_setting=price_col_setting,
                    price_column_name=price_column_name,
                )

            st.success(f"Conversion completed successfully for region {region} ({currency_code})!")

            st.download_button(
                label="📥 Download Output Feed (.xlsx)",
                data=output_bytes,
                file_name=f"Product_Feed_Output_{region}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except ConversionError as ce:
            st.error(f"Conversion Error: {ce}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
