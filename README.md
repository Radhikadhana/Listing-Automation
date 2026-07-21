# Product Feed Generator (Streamlit + GitHub)

A Python/Streamlit port of the original Google Apps Script that turns a raw
"Input" product sheet into a formatted "Output" feed sheet (titles, SKUs,
category mapping, parent/variant rows, item specifics, etc.).

## Files

- `logic.py` — faithful, function-by-function port of the Apps Script
  (`myFunction`, `fillParentRow`, `variation2`, `sortChildIndexBasedOnSize`,
  string helpers, map builders, ...). Pure Python + `openpyxl`, no Google
  dependency.
- `github_utils.py` — minimal GitHub Contents API wrapper (read a file from a
  repo, create/update a file in a repo).
- `app.py` — the Streamlit UI: upload or pull the input workbook from GitHub,
  run the conversion, download the result and/or push it back to GitHub.
- `requirements.txt`

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub token

Create a GitHub **Personal Access Token** (classic `repo` scope, or a
fine-grained token with **Contents: Read and write** on the target repo) and
paste it into the sidebar. The token is only kept in the Streamlit session —
it isn't written to disk. For a deployed app, put it in
`.streamlit/secrets.toml` instead and read it with `st.secrets["GITHUB_TOKEN"]`
rather than typing it in each time.

## Expected input workbook

One `.xlsx` file with these sheet names (must match exactly):

| Sheet | Columns used |
|---|---|
| `Input` | Raw product rows — same column layout as the original script (e.g. col 14 = product division `Footwear`/`Apparel`/`Accessories`/`Socks`; col 1 or 9 = style depending on division; col 16 = customSKU; cols 20-23 = US/FR/UK/Asia sizes; etc.) |
| `Price Sheet` | A:E — customSKU in C, item amount in D, sale price in E |
| `Category sheet` | A:C — lookup key in A, category ID in B |
| `Size chart` | A:B — lookup key in A |
| `Stock sheet` *(optional)* | kept for parity with the original script; not currently used to populate any output column (it wasn't in the original either — that code path is commented out there too) |

Output is a single `Output` sheet with the same 60-column layout as the
original (`SKU, status, errorDetails, customSKU, itemTitle, ...,
postAsNonVariant`).

## Known quirks carried over from the original script

These aren't bugs introduced in the port — they're faithfully reproduced
because a byte-for-byte behavioural match was the goal. Worth knowing about:

1. **Debug writes into columns A-C.** The original script has three lines
   that write `"mappingKey : ..."`, `"childIndex : ..."`, and the entire
   lookup map into output columns A/B/C at the *input* row number `i` (not
   the output row). This looks like leftover debugging rather than
   intentional output. It's **off by default** in this port
   (`keep_debug_writes=False` / the sidebar checkbox); turn it on if you need
   an exact match to the original's output file.
2. **`index` increments twice for parent rows that have children** (once
   right after the parent is filled, once more at the bottom of the loop),
   while non-variant rows only increment once. This is preserved as-is.
3. **`Stock sheet` / quantity map** is constructed but never actually used to
   populate a column — same as the original (the relevant lines are commented
   out there too).
4. `sortChildIndexBasedOnSize`'s `value1[5]` (assumed "quantity") column is
   read from the Input sheet but its actual meaning depends on your specific
   column layout — verify column **Q** (17) really holds a quantity in your
   workbook.

## Validating the port

Before pointing this at a production workbook, run it against a small sample
(a handful of styles, both variant and non-variant, footwear and apparel) and
diff the `Output` sheet against what the Apps Script produces for the same
input. The most format-sensitive parts are `variation2()` (size string
formatting) and `sortChildIndexBasedOnSize()` (parent/child row alignment) —
if child rows land on the wrong row, that's the first place to check.
