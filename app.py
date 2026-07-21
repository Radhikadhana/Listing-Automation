import io
import traceback
from datetime import datetime

import streamlit as st

from logic import build_output_workbook
from github_utils import get_file, put_file, GitHubError

st.set_page_config(page_title="Product Feed Generator", layout="centered")
st.title("Product Feed Generator")
st.caption(
    "Port of the original Apps Script: reads Input / Price Sheet / "
    "Category sheet / Size chart (and optional Stock sheet) and produces "
    "an Output sheet."
)

# ---------------------------------------------------------------------------
# Sidebar: GitHub connection settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("GitHub connection")
    token = st.text_input("GitHub token (Personal Access Token)", type="password",
                           help="Needs 'repo' scope (or fine-grained contents:read/write) on the target repo.")
    owner = st.text_input("Repo owner", placeholder="my-org")
    repo = st.text_input("Repo name", placeholder="product-feed")
    branch = st.text_input("Branch", value="main")
    st.markdown("---")
    keep_debug_writes = st.checkbox(
        "Reproduce original debug writes (rows 1-3, columns A-C)",
        value=False,
        help="The original Apps Script had leftover debug lines writing "
             "mappingKey/childIndex/full map into output columns A-C at the "
             "input row number. Off by default since it looks unintentional.",
    )

st.subheader("1. Get the input workbook")
source = st.radio("Input source", ["Upload a file", "Pull from GitHub"], horizontal=True)

input_bytes = None
input_label = None

if source == "Upload a file":
    uploaded = st.file_uploader("Input workbook (.xlsx)", type=["xlsx"])
    if uploaded is not None:
        input_bytes = uploaded.read()
        input_label = uploaded.name
else:
    input_path = st.text_input("Path in repo", placeholder="data/input.xlsx")
    if st.button("Fetch from GitHub"):
        if not (token and owner and repo and input_path):
            st.error("Fill in the GitHub token, owner, repo and file path first.")
        else:
            try:
                with st.spinner(f"Fetching {input_path} from {owner}/{repo}@{branch}..."):
                    content, sha = get_file(owner, repo, input_path, token, branch)
                st.session_state["gh_input_bytes"] = content
                st.session_state["gh_input_path"] = input_path
                st.success(f"Fetched {input_path} ({len(content):,} bytes)")
            except GitHubError as e:
                st.error(str(e))

    if "gh_input_bytes" in st.session_state:
        input_bytes = st.session_state["gh_input_bytes"]
        input_label = st.session_state["gh_input_path"]

if input_bytes:
    st.info(f"Using input: **{input_label}** ({len(input_bytes):,} bytes)")

st.subheader("2. Generate the Output sheet")

if input_bytes and st.button("Run conversion", type="primary"):
    progress_bar = st.progress(0.0, text="Starting...")

    def progress_callback(done, total):
        frac = min(done / max(total, 1), 1.0)
        progress_bar.progress(frac, text=f"Processing row {done} of {total}")

    try:
        output_bytes = build_output_workbook(
            input_bytes,
            keep_debug_writes=keep_debug_writes,
            progress_callback=progress_callback,
        )
        progress_bar.progress(1.0, text="Done")
        st.session_state["output_bytes"] = output_bytes
        st.success("Conversion complete.")
    except Exception as e:
        st.error(f"Conversion failed: {e}")
        st.code(traceback.format_exc())

if "output_bytes" in st.session_state:
    st.subheader("3. Get the result")
    out_bytes = st.session_state["output_bytes"]

    default_name = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    st.download_button(
        "Download Output.xlsx",
        data=out_bytes,
        file_name=default_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("**Push result to GitHub**")
    output_path = st.text_input("Path in repo to write output to", placeholder="data/output.xlsx")
    commit_msg = st.text_input("Commit message", value="Update generated product feed output")

    if st.button("Commit to GitHub"):
        if not (token and owner and repo and output_path):
            st.error("Fill in the GitHub token, owner, repo and output path first.")
        else:
            try:
                with st.spinner(f"Committing {output_path} to {owner}/{repo}@{branch}..."):
                    result = put_file(owner, repo, output_path, out_bytes, commit_msg, token, branch)
                commit_url = result.get("commit", {}).get("html_url")
                st.success("Pushed to GitHub.")
                if commit_url:
                    st.markdown(f"[View commit]({commit_url})")
            except GitHubError as e:
                st.error(str(e))

st.markdown("---")
with st.expander("Expected input workbook format"):
    st.markdown(
        """
The uploaded/fetched `.xlsx` must contain these sheets (names must match exactly):

- **Input** — the raw product rows (same column layout as the original: e.g.
  column N = product division `Footwear`/`Apparel`/`Accessories`/`Socks`,
  column A or I = style depending on division, column P = customSKU, etc.)
- **Price Sheet** — columns A:E, customSKU in column C, item amount in D, sale
  price in E.
- **Category sheet** — columns A:C, lookup key in column A, category ID in
  column B.
- **Size chart** — columns A:B, lookup key in column A.
- **Stock sheet** *(optional, currently unused in output — kept for parity
  with the original script)*.

The generated **Output** sheet mirrors the original 60-column layout (SKU,
status, errorDetails, customSKU, itemTitle, ... postAsNonVariant).
        """
    )
