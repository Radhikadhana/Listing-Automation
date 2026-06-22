import io
import streamlit as st
import pandas as pd

from mapper import convert, HEADER_COLUMNS

st.set_page_config(page_title="Lazada SG Listing Converter", layout="wide")
st.title("Lazada SG Listing Converter")
st.caption(
    "Upload the product Input file and the Lazada SG category sheet to generate "
    "a marketplace-ready upload file with the official Header columns."
)

col1, col2 = st.columns(2)
with col1:
    input_file = st.file_uploader("Input.xlsx (product data)", type=["xlsx"])
with col2:
    category_file = st.file_uploader("Lazada_SG_Category_Sheet.xlsx", type=["xlsx"])

with st.expander("How Category ID is assigned"):
    st.markdown(
        "- Each product's **Age Group, Gender, Article Group, Article Type, "
        "Activity Group, Product Division** are matched against every category "
        "path in the Lazada sheet.\n"
        "- Matches under a **Sports** category branch are preferred; if no "
        "good sports match exists, the best **Fashion/Bags/Shoes** match is used "
        "instead.\n"
        "- Matching is heuristic (keyword + gender/age alignment) — always spot-check "
        "the **Category Match Log** sheet in the output before bulk-uploading to Lazada."
    )

if st.button("Generate Output", type="primary", disabled=not (input_file and category_file)):
    with st.spinner("Reading files..."):
        input_df = pd.read_excel(input_file, sheet_name="Input")
        category_df = pd.read_excel(category_file, sheet_name=0)

    with st.spinner("Matching categories and building output..."):
        output_df, log_df = convert(input_df, category_df)

    st.success(f"Converted {len(output_df)} rows.")

    st.subheader("Preview — Output")
    st.dataframe(output_df.head(50), use_container_width=True)

    st.subheader("Preview — Category Match Log")
    st.dataframe(log_df.head(50), use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        output_df.to_excel(writer, sheet_name="Output", index=False)
        log_df.to_excel(writer, sheet_name="Category Match Log", index=False)
    buffer.seek(0)

    st.download_button(
        "Download Output.xlsx",
        data=buffer,
        file_name="Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    if not (input_file and category_file):
        st.info("Upload both files to continue.")
