import io
import traceback
from datetime import datetime

import streamlit as st
from openpyxl import load_workbook

from logic import build_output_workbook, ConversionError
from github_utils import get_file, put_file, GitHubError

st.set_page_config(page_title="Product Feed Generator - Zecom Tracker", layout="wide")
st.title("Product Feed Generator")
st.caption("Generate ZECOM feed outputs with customized column selections, currency codes, and parent SKU rules.")

# ---------------------------------------------------------------------------
# Sidebar: GitHub Connection Settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("GitHub Connection")
    token = st.text_input("GitHub Token (PAT)", type="password", help="Needs 'repo' scope on target repo.")
    owner = st.text_input("Repo Owner", placeholder="my-org")
    repo = st.text_input("Repo Name", placeholder="product-feed")
    branch = st.text_input("Branch", value="main")
    st.markdown("---")
    keep_debug_writes = st.checkbox(
        "Reproduce debug writes (columns A-C)",
        value=False,
        help="Writes debug information into output columns A-C.",
    )

st.subheader("1. Input Data Source")
source = st.radio("Main Input Source", ["Upload File", "Pull from GitHub"], horizontal=True)

input_bytes = None
input_label = None

if source == "Upload File":
    uploaded = st.file_uploader("Upload Main Input Workbook (.xlsx)", type=["xlsx"], key="main_input")
    if uploaded is not None:
        input_bytes = uploaded.read()
        input_label = uploaded.name
else:
    input_path = st.text_input("Path in repo", placeholder="data/input.xlsx")
    if st.button("Fetch from GitHub"):
        if not (token and owner and repo and input_path):
            st.error("Fill in GitHub credentials and file path first.")
        else:
            try:
                with st.spinner(f"Fetching {input_path}..."):
                    content, sha = get_file(owner, repo, input_path, token, branch)
                st.session_state["gh_input_bytes"] = content
                st.session_state["gh_input_path"] = input_path
                st.success(f"Fetched {input_path} ({len(content):,} bytes)")
            except GitHubError as e:
                st.error(str(e))

    if "gh_input_bytes" in st.session_state:
        input_bytes = st.session_state["gh_input_bytes"]
        input_label = st.session_state["gh_input_path"]

st.markdown("---")
st.subheader("2. Configurable Tracker Options")

col_cfg1, col_cfg2, col_cfg3 = st.columns(3)

with col_cfg1:
    currency_code = st.selectbox(
        "Select Currency Code",
        options=["PHP", "SGD", "MYR"],
        index=0,
        help="This value will fill the currencyCode column in the output sheet."
    )

with col_cfg2:
    price_col_input = st.text_input(
        "Tracker Price Column (for RRP)",
        value="D",
        help="Enter column letter (e.g., D, E, Q) or header name from the tracker that contains the price/RRP."
    )

with col_cfg3:
    st.info("Parent SKU Rules:\n- **Apparel & Accessories**: Uses **Style**\n- **Footwear**: Uses **Color No.**")

st.markdown("---")
st.subheader("3. Upload Mapping Sheets (Optional / Override)")

col1, col2 = st.columns(2)

with col1:
    price_file = st.file_uploader("Price Sheet (.xlsx)", type=["xlsx"])
    category_file = st.file_uploader("Category Sheet (.xlsx)", type=["xlsx"])

with col2:
    size_chart_file = st.file_uploader("Size Chart Sheet (.xlsx)", type=["xlsx"])
    sample_output_file = st.file_uploader("Sample Output Template Sheet (.xlsx)", type=["xlsx"])

price_bytes = price_file.read() if price_file else None
category_bytes = category_file.read() if category_file else None
size_chart_bytes = size_chart_file.read() if size_chart_file else None
sample_output_bytes = sample_output_file.read() if sample_output_file else None

st.markdown("---")
st.subheader("4. Run Conversion")

run_clicked = st.button("Run Conversion", type="primary", disabled=not input_bytes)
if not input_bytes:
    st.caption("Please upload or fetch an input workbook first.")

if run_clicked and input_bytes:
    progress_bar = st.progress(0.0, text="Starting conversion...")

    def progress_callback(done, total):
        frac = min(done / max(total, 1), 1.0)
        progress_bar.progress(frac, text=f"Processing row {done} of {total}")

    try:
        output_bytes = build_output_workbook(
            input_bytes,
            price_bytes=price_bytes,
            category_bytes=category_bytes,
            size_chart_bytes=size_chart_bytes,
            sample_output_bytes=sample_output_bytes,
            currency_code=currency_code,
            price_col_setting=price_col_input,
            keep_debug_writes=keep_debug_writes,
            progress_callback=progress_callback,
        )
        progress_bar.progress(1.0, text="Done")
        st.session_state["output_bytes"] = output_bytes
        st.success("Conversion complete! RRP and Parent SKUs mapped successfully.")
    except ConversionError as e:
        progress_bar.empty()
        st.error(str(e))
    except Exception as e:
        progress_bar.empty()
        st.error(f"Conversion failed: {e}")
        st.code(traceback.format_exc())

# Download / Push section
if "output_bytes" in st.session_state:
    st.subheader("5. Download / Export Result")
    out_bytes = st.session_state["output_bytes"]

    default_name = f"zecom_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    st.download_button(
        "Download Output Sheet (.xlsx)",
        data=out_bytes,
        file_name=default_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("**Push to GitHub**")
    output_path = st.text_input("Path in repo for output file", placeholder="data/output.xlsx")
    commit_msg = st.text_input("Commit message", value="Update generated ZECOM product feed output")

    if st.button("Commit to GitHub"):
        if not (token and owner and repo and output_path):
            st.error("Fill in GitHub credentials and output path first.")
        else:
            try:
                with st.spinner(f"Committing {output_path}..."):
                    result = put_file(owner, repo, output_path, out_bytes, commit_msg, token, branch)
                commit_url = result.get("commit", {}).get("html_url")
                st.success("Successfully pushed to GitHub!")
                if commit_url:
                    st.markdown(f"[View Commit on GitHub]({commit_url})")
            except GitHubError as e:
                st.error(str(e))
