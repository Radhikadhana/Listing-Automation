import streamlit as st
from logic import build_output_workbook, ConversionError

st.set_page_config(page_title="Product Feed Generator", layout="wide")

st.title("📦 Product Feed & Variant Generator")
st.markdown("Upload your main tracker workbook (or upload standalone reference sheets) to process parent/child variants and generate feed output.")

# Sidebar Settings
st.sidebar.header("Configuration Settings")
currency_code = st.sidebar.selectbox("Currency Code", ["PHP", "SGD", "MYR", "THB", "IDR"], index=0)
price_col_setting = st.sidebar.text_input("Price Column Letter/Header in Input Sheet", value="D")

st.subheader("1. File Uploads")

col1, col2 = st.columns(2)

with col1:
    input_file = st.file_uploader("Upload Main Workbook (.xlsx)", type=["xlsx"], help="Workbook containing 'Input', 'Price Sheet', 'Category sheet', 'Size chart', etc.")

with col2:
    st.markdown("**Optional Standalone Overrides:**")
    price_file = st.file_uploader("Price Sheet (.xlsx)", type=["xlsx"], key="price")
    category_file = st.file_uploader("Category Sheet (.xlsx)", type=["xlsx"], key="cat")
    size_chart_file = st.file_uploader("Size Chart Sheet (.xlsx)", type=["xlsx"], key="size")
    sample_output_file = st.file_uploader("Sample Output Sheet (For Custom Column Headers)", type=["xlsx"], key="sample")

st.markdown("---")

if st.button("🚀 Process & Generate Feed", type="primary"):
    if not input_file:
        st.error("Please upload the main input Excel file before proceeding.")
    else:
        try:
            with st.spinner("Processing rows, colors, size UK, and template attributes..."):
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
                    currency_code=currency_code,
                    price_col_setting=price_col_setting
                )

            st.success("Conversion completed successfully!")
            
            st.download_button(
                label="📥 Download Output Feed (.xlsx)",
                data=output_bytes,
                file_name="Product_Feed_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except ConversionError as ce:
            st.error(f"Conversion Error: {ce}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
