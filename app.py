"""
Marketplace Bulk Upload Sheet Generator
========================================
Streamlit app that takes:
  - Master Input Sheet (product data, including price)
  - Image Sheet (SKU -> image URLs)
  - Size Chart Template Sheet (category/title -> size chart template attribute)
  - Category Sheet (title keyword -> category ID)
  - Sample Upload Format (defines exact output columns/order — REQUIRED)

...and produces a marketplace-ready bulk upload file (Parent/Child rows,
cleaned titles & descriptions, variations, images, category IDs, size chart
template values, prices, defaults, stock=0, shipping, product specification).

CHANGES IN THIS VERSION:
  - Tracker Sheet (separate pricing file) REMOVED. Price is now read straight
    from a price column on the Master Input Sheet.
  - Size Chart Sheet REPLACED with a Size Chart Template Sheet: instead of
    matching free-text title keywords to a URL, this matches a Size Chart Key
    (built from Age Group / Gender / Article Group / Article Type, same as
    before) to a Template Attribute 1 string you define directly in that sheet.
  - Output columns now STRICTLY follow the Sample Upload Format headers.
    The Sample Upload Format file is now REQUIRED (not optional) — the app
    will not guess an output layout on its own.

IMPORTANT: Column name constants below are BEST-GUESS based on the spec you
provided. Once you share your actual sheets, update the CONFIG section
(search for "ADJUST ME") to match your real column headers exactly.
"""

import io
import re
from collections import OrderedDict

import pandas as pd
import numpy as np
import streamlit as st

# ======================================================================================
# CONFIG — ADJUST ME to match your real column headers once real files are shared
# ======================================================================================

MASTER_COLS = {
    "style_no": "Style Number",
    "color_no": "Color Number",
    "brand": "Brand",
    "gender": "Gender",
    "title": "Regional Display Name",
    "color_family": "Color Family",
    "color_name": "Color Name",
    "search_color_name": "Search Color Name",
    "size": "Size",
    "uk_size": "UK Size",
    "sku": "SKU",
    "price": "Price",              # NEW: price now lives on the Master Sheet directly
    "description": "Description",
    "care": "Care",
    "care_label": "Care Label",
    "category_hint": "Category",   # optional, else derived from title
    "footwear_color": "Footwear Color",
    "product_type": "Product Type",  # e.g. Trainers / Sandals / Slides / Apparel / Accessories
    "age_group": "Age Group",
    "article_group": "Article Group",
    "article_type": "Article Type",
    "activity_group": "Activity Group",
    # --- Fields used to build the Short Description bullet list ---
    "collection": "Collection",
    "material": "Material",
    "material_local": "Material (English)",
    "upper_material": "Upper Material",
    "mid_sole_material": "Mid Sole Material",
    "outer_sole_material": "Outer Sole Material",
    "shell_material": "Shell Material",
    "toe_type": "Toe Type",
    "heel_type": "Heel Type",
    "fastener": "Fastener",
    "fit": "Fit",
    "puma_technology": "Puma Technology",
    "technology_purpose": "Technology Purpose",
}

# Human-readable label + whether the field is required for a usable output,
# used to build the runtime Master Sheet column-mapping UI below. This is
# what actually fixes "field X is blank in the output" bugs — instead of
# silently defaulting to "" when a hard-coded header name doesn't match your
# real sheet, the app now makes you explicitly map every field once per file.
MASTER_COLS_FIELDS = [
    ("style_no", "Style Number", True),
    ("color_no", "Color Number (Footwear)", True),
    ("brand", "Brand", True),
    ("gender", "Gender", True),
    ("title", "Regional Display Name (used in Title)", True),
    ("color_family", "Color Family", True),
    ("color_name", "Color Name (used in Variation 1)", True),
    ("search_color_name", "Search Color Name (used in Short Description, code stripped)", False),
    ("size", "Size", False),
    ("uk_size", "UK Size (used in Variation 2)", True),
    ("sku", "SKU", True),
    ("description", "Description", True),
    ("care", "Care", False),
    ("care_label", "Care Label", False),
    ("footwear_color", "Footwear Color (used in Title for Footwear)", False),
    ("product_type", "Product Division (Footwear/Apparel/Accessories)", True),
    ("age_group", "Age Group", False),
    ("article_group", "Article Group", False),
    ("article_type", "Article Type", False),
    ("activity_group", "Activity Group (used in Short Description)", False),
    ("collection", "Collection (used in Short Description)", False),
    ("material", "Material (used in Short Description)", False),
    ("material_local", "Material Local / English (used in Short Description)", False),
    ("upper_material", "Upper Material (used in Short Description)", False),
    ("mid_sole_material", "Mid Sole Material (used in Short Description)", False),
    ("outer_sole_material", "Outer Sole Material (used in Short Description)", False),
    ("shell_material", "Shell Material (used in Short Description)", False),
    ("toe_type", "Toe Type (used in Short Description)", False),
    ("heel_type", "Heel Type (used in Short Description)", False),
    ("fastener", "Fastener (used in Short Description)", False),
    ("fit", "Fit (used in Short Description)", False),
    ("puma_technology", "PUMA Technology (used in Short Description)", False),
    ("technology_purpose", "Technology Purpose (used in Short Description)", False),
]

IMAGE_SHEET_COLS = {
    "sku": "ColorNumber",  # long/tall format: one row per (ColorNumber, image URL) pair
    "url_col": "Product Image URL(s)",  # every row matching a given ColorNumber contributes one URL
}

# Size Chart Sheet (NEW): a separate upload that provides the actual size
# chart IMAGE URL, matched by a title/keyword reference — this feeds the
# "Size Chart Image URL" output column. This is distinct from the Size Chart
# TEMPLATE Sheet below, which feeds "Template Attribute 1" via a direct
# composite-key lookup (Age Group-Gender-Article Group-Article Type).
SIZE_CHART_IMAGE_COLS = {
    "title_keyword": "Title",       # keyword/phrase matched against the generated product Title
    "image_url": "Size Chart Image URL",  # the literal image URL to output
    "style_no": "Style Number",     # OPTIONAL: exact-match column, tried before title-keyword matching
}

# Size Chart TEMPLATE sheet (replaces old free-text Size Chart Sheet).
# Expected columns: a lookup key (Age Group-Gender-Article Group-Article Type,
# same composite key used elsewhere) and the literal Template Attribute 1 value
# to place on the row — no keyword matching, no URL, just a direct key lookup.
SIZE_CHART_TEMPLATE_COLS = {
    "key": "Size Chart Key",                 # e.g. "Adult-Men-Tops-Tee"
    "template_attribute_1": "Template Attribute 1",  # literal string to output, e.g. "sizechart=Men Tops"
}

CATEGORY_SHEET_COLS = {
    "keyword": "Title Keyword",
    "category_id": "Category ID",
}

# Region -> Currency Code mapping
REGION_CURRENCY = {
    "SG": "SGD",
    "MY": "MYR",
    "PH": "PHP",
}

MARKETPLACES = ["Lazada", "Shopee", "Zalora", "Tiktok"]
REGIONS = ["SG", "MY", "PH"]

USER_TEMPLATE_NAME = "userTemplate-PumaAccessories"

# Default values (spec section 7)
DEFAULTS = {
    "Currency": "PHP",
    "Condition": "Default",
    "Warranty": "No Warranty",
    "Package Weight": 0.5,
    "Package Height": 15,
    "Package Length": 12,
    "Package Width": 12,
    "Shipping Service": "Standard Local",
    "Shipping Fee": 40.00,
    "Product Specification": "Brand: PUMA",
}

# Title word replacements (spec section 1)
TITLE_REPLACEMENTS = OrderedDict([
    (r"\bTrainers\b", "Shoes"),
    (r"\bSandals\b", "Sports Sandals"),
    (r"\bSlides\b", "Slides Slippers"),
])

# Size sort order (spec section 3)
ALPHA_SIZE_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "OSFA", "Youth"]


# ======================================================================================
# HELPERS
# ======================================================================================

def extract_pure_color_number(raw):
    """
    Your Master Sheet's "Color Number" field stores a COMBINED
    StyleNumber_ColorSuffix code (e.g. "695872_01"), matching PUMA's own
    convention -- not a bare color code on its own. For the Model field (and
    the Image Sheet lookup key), only the trailing color suffix is wanted
    (e.g. "01"), with the Style Number prefix stripped off.

    "695872_01"  -> "01"
    "054950_08"  -> "08"
    "01"         -> "01"   (already bare -- left as-is)
    ""  / None   -> ""
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw).strip()
    if s.lower() in ("", "nan"):
        return ""
    if "_" in s:
        return s.rsplit("_", 1)[-1].strip()
    return s


def clean_color_name(raw):
    """
    Cleans a color field down to a plain color name, stripping any leading
    color NUMBER and separator. Handles both:
      - "10 - Black"       -> "Black"   (Search Color Name style)
      - "309707_03"        -> ""        (a raw Style_Color code, not a color
                                          name at all -- returns "" so it
                                          never leaks into the title/variation)
      - "Black"            -> "Black"   (already clean)
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw).strip()
    if s.lower() in ("", "nan"):
        return ""

    # "<number> - <color name>" (Search Color Name convention) -> take the
    # part after the LAST " - " separator.
    if " - " in s:
        s = s.split(" - ")[-1].strip()

    # A bare numeric/underscore code with no letters at all (e.g. a raw
    # Style_Color number like "309707_03") is not a color name -- discard it
    # entirely rather than let a number leak into the title.
    if re.fullmatch(r"[\d_\-\s]+", s):
        return ""

    # Strip any leftover leading numeric/underscore prefix (e.g. "01_Black").
    s = re.sub(r"^[\d_]+[\s\-_]*", "", s).strip()
    return s


def guess_column_index(options, preferred_name, keywords):
    """
    Picks a sensible default index into `options` for a Streamlit selectbox:
      1. Exact match on `preferred_name` (case-insensitive) if present.
      2. Otherwise, the first column whose name contains any of `keywords`
         (case-insensitive substring match) -- e.g. "url", "link", "image".
      3. Otherwise, falls back to 0 -- but this should be rare once (2) is in
         place, and the person can always override the dropdown manually.
    This avoids silently defaulting to the wrong column (like matching a
    "Color Number" column as if it were an "Image URL" column) just because
    the exact configured header name isn't present in the person's sheet.
    """
    norm_options = [str(o).strip().lower() for o in options]
    preferred_norm = str(preferred_name).strip().lower()
    if preferred_norm in norm_options:
        return norm_options.index(preferred_norm)
    for kw in keywords:
        kw_norm = kw.strip().lower()
        for i, opt in enumerate(norm_options):
            if kw_norm in opt:
                return i
    return 0


def normalize_match_text(s):
    """Lowercase, strip trademark/registered symbols and punctuation, and
    collapse whitespace -- used so keyword-in-title matching survives minor
    formatting differences (curly quotes, ™/® symbols, extra spaces, etc.)."""
    if s is None:
        return ""
    s = str(s).replace("™", "").replace("®", "")
    s = re.sub(r"[^A-Za-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def clean_title(brand, gender, title, footwear_color_raw, is_footwear):
    """
    Build title per spec:
    [NEW] [Brand] [Gender] [Regional Display Name] [Color (if Footwear)]
    Gender is now ALWAYS included when present (not just when it's "Unisex").
    The footwear color is cleaned via clean_color_name() first, so a raw
    Color Number / Style_Color code never ends up in the title -- only an
    actual color name (e.g. "Black", not "309707_03" or "10 - Black").
    """
    title = title or ""
    for pattern, repl in TITLE_REPLACEMENTS.items():
        title = re.sub(pattern, repl, title, flags=re.IGNORECASE)

    footwear_color = clean_color_name(footwear_color_raw)

    parts = ["[NEW]"]
    if brand:
        parts.append(str(brand).strip())
    if gender and str(gender).strip().lower() == "unisex":
        parts.append(str(gender).strip())
    if title:
        parts.append(title.strip())
    if is_footwear and footwear_color:
        parts.append(footwear_color)

    # remove duplicate words anywhere in the title (case-insensitive), preserve first occurrence
    seen = set()
    deduped = []
    for word in " ".join(parts).split():
        key = word.lower()
        if key in seen and key not in ("[new]",):
            continue
        seen.add(key)
        deduped.append(word)
    return " ".join(deduped).strip()


def clean_description(raw_desc, style_number, care=None, care_label=None):
    """
    Clean description per Lazada Short Description spec:
      - Remove <h3>PRODUCT STORY</h3> variants (case/whitespace-insensitive).
      - Remove <br/>, </br>, <br /> line breaks.
      - Trim leading/trailing whitespace.
      - Replace <h3>DETAILS</h3> variants with two newlines + "DETAILS".
      - Replace <h3>FEATURES & BENEFITS</h3> / <h3>FEATURES + BENEFITS</h3>
        variants with two newlines + "FEATURES & BENEFITS".
      - Replace <li> with newline + "- " bullet; strip </li>, <ul>, </ul>,
        <p>, </p> entirely.
    """
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        raw_desc = ""
    desc = str(raw_desc)

    # Remove <h3>PRODUCT STORY</h3> (and lowercase/whitespace variants) entirely.
    desc = re.sub(r"<h3>\s*product\s*story\s*</h3>", "", desc, flags=re.IGNORECASE)
    # Safety net: bare "product story" text without the heading tags.
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)

    # Remove line breaks: <br/>, </br>, <br />
    desc = re.sub(r"<br\s*/?>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</br>", "", desc, flags=re.IGNORECASE)

    # Replace <h3>DETAILS</h3> variants with two newlines + "DETAILS"
    desc = re.sub(r"<h3>\s*details\s*</h3>", "\n\nDETAILS", desc, flags=re.IGNORECASE)

    # Replace <h3>FEATURES & BENEFITS</h3> / <h3>FEATURES + BENEFITS</h3> variants
    desc = re.sub(
        r"<h3>\s*features\s*(&|\+)\s*benefits\s*</h3>",
        "\n\nFEATURES & BENEFITS",
        desc,
        flags=re.IGNORECASE,
    )

    # Convert <li> to newline + bullet
    desc = re.sub(r"<li[^>]*>", "\r\n- ", desc, flags=re.IGNORECASE)

    # Strip </li>, <ul>, </ul>, <p>, </p> entirely (no replacement)
    for tag in [r"</li>", r"<ul[^>]*>", r"</ul>", r"<p[^>]*>", r"</p>"]:
        desc = re.sub(tag, "", desc, flags=re.IGNORECASE)

    # Strip any remaining stray HTML tags (safety net)
    desc = re.sub(r"<[^>]+>", "", desc)

    # Trim leading/trailing whitespace (per row and overall)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in desc.splitlines()]
    lines = [ln for ln in lines if ln != ""]
    desc = "\n".join(lines).strip()

    # Append Style, CARE, CARE LABEL
    tail = [f"Style : {style_number}"]
    if care and str(care).strip().lower() not in ("nan", ""):
        tail.append(f'"CARE"\n{str(care).strip()}')
    if care_label and str(care_label).strip().lower() not in ("nan", ""):
        tail.append(f'"CARE LABEL"\n{str(care_label).strip()}')

    desc = desc + "\n\n" + "\n\n".join(tail)
    return desc.strip()


def is_footwear(product_division):
    """Product Division check (Footwear / Apparel / Accessories)."""
    if not product_division:
        return False
    return str(product_division).strip().lower() in ("footwear", "shoes", "trainers", "sandals", "slides")


def size_sort_key(size_val, is_footwear_row=False):
    """
    Variant 2 size sorting:
      - Alphanumeric/sizing (XS, S, M, L, XL, XXL, OSFA, age ranges like 1-2Y):
        sort by the predefined ALPHA_SIZE_ORDER sequence.
      - Purely numeric (footwear UK shoe sizes): sort numerically ascending.
    """
    s = str(size_val).strip().upper()
    if s in ALPHA_SIZE_ORDER:
        return (0, ALPHA_SIZE_ORDER.index(s), 0, "")
    try:
        num = float(re.sub(r"[^\d.]", "", s))
        return (1, 0, num, "")
    except (ValueError, TypeError):
        return (2, 0, 0, s)


def match_category_id(title, category_df, keyword_col, id_col):
    if category_df is None or category_df.empty:
        return ""
    if keyword_col not in category_df.columns or id_col not in category_df.columns:
        return ""
    title_lower = str(title).lower()
    best_match = ""
    best_len = 0
    for _, row in category_df.iterrows():
        kw = str(row.get(keyword_col, "")).strip().lower()
        if kw and kw in title_lower and len(kw) > best_len:
            best_match = row.get(id_col, "")
            best_len = len(kw)
    return best_match


def match_size_chart_image(title, size_chart_image_df, title_col, url_col,
                            style_number=None, style_col=None):
    """
    Resolves the Size Chart Image URL for a product.

    Two strategies, tried in order:
      1. STYLE NUMBER exact match (reliable): if the Size Chart Sheet has a
         style-number column mapped, match it exactly against this group's
         Style Number first.
      2. TITLE keyword match (fallback): the Size Chart Sheet's title/keyword
         column is checked for the longest substring match against the
         product Title. Both sides are normalized first (symbols like ™/®
         stripped, punctuation removed, whitespace collapsed, case-folded)
         so minor formatting differences (curly quotes, trademark marks,
         double spaces) don't silently break the match.

    Returns "" if no sheet is uploaded, expected columns aren't found, or
    nothing matches either way.
    """
    if size_chart_image_df is None or size_chart_image_df.empty:
        return ""

    # --- Strategy 1: exact Style Number match ---
    if style_col and style_number not in (None, "") and style_col in size_chart_image_df.columns and url_col in size_chart_image_df.columns:
        norm_style = str(style_number).strip().lower()
        style_match = size_chart_image_df[
            size_chart_image_df[style_col].astype(str).str.strip().str.lower() == norm_style
        ]
        if not style_match.empty:
            val = style_match.iloc[0].get(url_col, "")
            if val and str(val).strip():
                return val

    # --- Strategy 2: normalized keyword-in-title match ---
    if title_col not in size_chart_image_df.columns or url_col not in size_chart_image_df.columns:
        return ""
    title_norm = normalize_match_text(title)
    best_match = ""
    best_len = 0
    for _, row in size_chart_image_df.iterrows():
        kw_raw = row.get(title_col, "")
        kw_norm = normalize_match_text(kw_raw)
        if kw_norm and kw_norm in title_norm and len(kw_norm) > best_len:
            url_val = row.get(url_col, "")
            if url_val and str(url_val).strip():
                best_match = url_val
                best_len = len(kw_norm)
    return best_match


def format_size_value(uk_size, is_footwear_row):
    """
    Use UK size for ALL divisions (Footwear, Apparel, Accessories).
    Prefix convention: 'UK:' for footwear numeric sizes, 'Int:' for
    Apparel/Accessories alpha sizes (XS, S, M, L, XL, XXL, OSFA, etc.).
    """
    if uk_size is None or (isinstance(uk_size, float) and pd.isna(uk_size)) or str(uk_size).strip() == "":
        return ""
    s = str(uk_size).strip()
    if is_footwear_row:
        return f"UK:{s}"
    return f"Int:{s}"


def count_groups_by_division(master_df, mc):
    """
    For each distinct Style Number (non-footwear rows, per Product Division),
    and for each distinct Color Number (footwear rows, per Product Division),
    count how many rows belong to that group. Used to decide whether a group
    needs a Parent row (count > 1) or is a single standalone row (count == 1).
    """
    counts = {}
    for _, r in master_df.iterrows():
        ptype = r.get(mc["product_type"], "")
        if is_footwear(ptype):
            key = ("footwear", r.get(mc["color_no"], ""))
        else:
            key = ("other", r.get(mc["style_no"], ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_size_chart_key(age_group, gender, article_group, article_type):
    """Composite lookup key used against the Size Chart Template Sheet."""
    parts = [age_group, gender, article_group, article_type]
    return "-".join(str(p).strip() if p is not None else "" for p in parts)


def match_size_chart_template(size_chart_key, size_chart_template_df, key_col, attr_col):
    """
    Direct key lookup (NOT keyword/title matching) against the Size Chart
    Template Sheet. Returns the literal Template Attribute 1 string, or ""
    if the key isn't found or either expected column is missing from the
    uploaded sheet (missing columns are treated as "no data available" —
    not a crash — since the sheet is optional).
    """
    if size_chart_template_df is None or size_chart_template_df.empty:
        return ""
    if key_col not in size_chart_template_df.columns or attr_col not in size_chart_template_df.columns:
        return ""
    match = size_chart_template_df[
        size_chart_template_df[key_col].astype(str).str.strip() == str(size_chart_key).strip()
    ]
    if match.empty:
        return ""
    return match.iloc[0].get(attr_col, "")


def get_images_for_key(lookup_value, image_df, lookup_col, url_col):
    """
    Looks up image URLs in the Image Sheet by Color Number (the Model value).

    The Image Sheet is a LONG/TALL format: one row per (ColorNumber, Link)
    pair, with the SAME ColorNumber repeating across multiple rows -- one row
    per image, not multiple image columns side-by-side on a single row. So
    this collects EVERY row whose lookup column matches the given Color
    Number and returns all of their URL values (in sheet order, duplicates
    removed), rather than reading fixed "Image 1".."Image N" columns off a
    single row.
    """
    if image_df is None or image_df.empty:
        return []
    if lookup_col not in image_df.columns or url_col not in image_df.columns:
        return []

    lookup_norm = str(lookup_value).strip()
    matches = image_df[image_df[lookup_col].astype(str).str.strip() == lookup_norm]
    if matches.empty:
        return []

    imgs = []
    seen = set()
    for val in matches[url_col]:
        if pd.notna(val) and str(val).strip():
            url = str(val).strip()
            if url not in seen:
                seen.add(url)
                imgs.append(url)
    return imgs


def get_price(row, price_col):
    """Price now comes straight from the Master Sheet row (no Tracker Sheet lookup)."""
    if price_col not in row or pd.isna(row.get(price_col, None)):
        return ""
    return row.get(price_col, "")


def extract_search_color_name(raw_color):
    """
    Extracts the plain color NAME from a "Search Color Name" field, stripping
    any leading code/number, per: "10 - Orange" -> "Orange". Also handles a
    bare code with no separator by discarding it entirely (no letters = not
    a color name). Used specifically for the Short Description's
    "Color Name" line (per spec: search color name WITHOUT the code number).
    """
    return clean_color_name(raw_color)


def extract_description_main(raw_desc):
    """
    Extract the plain main description content (before DETAILS/FEATURES
    sections) for the "description=" Template Attribute output. Matches:
      description=<p>Any closer and you'd be in the cockpit. ...</p>
    -- i.e. the intro paragraph(s) only, wrapped in a single <p> tag, with
    PRODUCT STORY headings and stray tags removed.
    """
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        return ""
    desc = str(raw_desc)

    # Remove PRODUCT STORY heading variants entirely (tag + text).
    desc = re.sub(r"<h[1-6]>\s*product\s*story\s*</h[1-6]>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<p>\s*product\s*story\s*</p>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)

    # Remove line breaks.
    desc = re.sub(r"<br\s*/?>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</br>", "", desc, flags=re.IGNORECASE)

    # Cut at the START of the first FEATURES/DETAILS heading only (no dot-all
    # greedy tail matching -- that previously let the pattern match too early
    # and chop the last word off the intro paragraph).
    split_pattern = re.compile(
        r"<h[1-6]>\s*(features\s*(&|\+)\s*benefits|details)\s*",
        re.IGNORECASE
    )
    match = split_pattern.search(desc)
    main_part = desc[:match.start()] if match else desc

    # Strip surrounding <p>/</p> tags off the intro text (any that remain,
    # including nested ones), then re-wrap the plain text in a single <p>.
    main_text = re.sub(r"</?p[^>]*>", "", main_part, flags=re.IGNORECASE).strip()
    main_text = re.sub(r"\s+", " ", main_text).strip()

    if not main_text:
        return ""
    return f"description=<p>{main_text}</p>"


def extract_productstory(raw_desc):
    """
    Extract FEATURES & BENEFITS + DETAILS sections (raw HTML) for the
    "productstory=" Template Attribute output. Matches from the OPENING
    <h3> tag itself (not from the word "FEATURES" inside it), so the tag
    is preserved:
      productstory=<h3>FEATURES & BENEFITS </h3><ul>...</ul><h3> DETAILS </h3><ul>...</ul>
    """
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        return ""
    desc = str(raw_desc)
    match = re.search(
        r"(<h[1-6]>\s*features\s*(&|\+)\s*benefits.*)",
        desc,
        flags=re.IGNORECASE | re.DOTALL,
    )
    story_part = match.group(1).strip() if match else ""
    return f"productstory={story_part}" if story_part else ""


def _clean_field_value(val):
    """Returns a trimmed string, or "" for blank/NaN/"Other" placeholder values."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "other"):
        return ""
    return s


def build_short_description(brand, color_name, gender, activity_group, collection,
                             material, material_local, upper_material, mid_sole_material,
                             outer_sole_material, shell_material, toe_type, heel_type,
                             fastener, fit, puma_technology, technology_purpose, style_number):
    """
    Builds the Short Description as an HTML bullet list, exactly matching:
      <ul><li>Brand : PUMA</li><li>Color Name : Orange</li><li>Gender : Unisex</li>
      <li>Activity Group : Auto</li><li>Material : ...</li><li>Style Number : 27472</li></ul>

    Each field is only included if it has a real (non-blank, non-"Other") value,
    in a fixed field order. Style Number is always appended last if present.
    """
    fields = [
        ("Brand", brand),
        ("Color Name", color_name),
        ("Gender", gender),
        ("Activity Group", activity_group),
        ("Collection", collection),
        ("Material", material),
        ("Material Local", material_local),
        ("Upper Material", upper_material),
        ("Mid Sole Material", mid_sole_material),
        ("Outer Sole Material", outer_sole_material),
        ("Shell Material", shell_material),
        ("Toe Type", toe_type),
        ("Heel Type", heel_type),
        ("Fastener", fastener),
        ("Fit", fit),
        ("PUMA Technology", puma_technology),
        ("Technology Purpose", technology_purpose),
        ("Style Number", style_number),
    ]

    items = []
    for label, raw_val in fields:
        val = _clean_field_value(raw_val)
        if val:
            items.append(f"<li>{label} : {val}</li>")

    return "<ul>" + "".join(items) + "</ul>"


# ======================================================================================
# CORE TRANSFORMATION
# ======================================================================================

def build_upload_sheet(master_df, image_df, size_chart_template_df, category_df,
                        output_columns, price_col,
                        master_col_map=None,
                        image_sku_col=None, image_url_col=None,
                        size_chart_key_col=None, size_chart_attr_col=None,
                        category_keyword_col=None, category_id_col=None,
                        size_chart_image_df=None,
                        size_chart_image_title_col=None, size_chart_image_url_col=None,
                        size_chart_image_style_col=None,
                        region="PH", marketplace="Lazada"):
    # Master Sheet field->column mapping is picked at runtime in the UI (this
    # is what fixes "Title/SKU/Variation blank in output" bugs — those fields
    # were silently defaulting to "" whenever CONFIG's hard-coded header names
    # didn't match your real sheet). Any field not explicitly mapped falls
    # back to the CONFIG default as a last resort.
    mc = dict(MASTER_COLS)
    if master_col_map:
        mc.update({k: v for k, v in master_col_map.items() if v})

    # Column names for the supporting sheets are picked at runtime in the UI
    # (since sheets rarely match the CONFIG placeholders exactly); fall back
    # to CONFIG defaults only if the caller didn't supply a runtime choice.
    ic = {
        "sku": image_sku_col if image_sku_col else IMAGE_SHEET_COLS["sku"],
        "url_col": image_url_col if image_url_col else IMAGE_SHEET_COLS["url_col"],
    }
    sct = {
        "key": size_chart_key_col if size_chart_key_col else SIZE_CHART_TEMPLATE_COLS["key"],
        "template_attribute_1": size_chart_attr_col if size_chart_attr_col else SIZE_CHART_TEMPLATE_COLS["template_attribute_1"],
    }
    cc = {
        "keyword": category_keyword_col if category_keyword_col else CATEGORY_SHEET_COLS["keyword"],
        "category_id": category_id_col if category_id_col else CATEGORY_SHEET_COLS["category_id"],
    }
    sci = {
        "title_keyword": size_chart_image_title_col if size_chart_image_title_col else SIZE_CHART_IMAGE_COLS["title_keyword"],
        "image_url": size_chart_image_url_col if size_chart_image_url_col else SIZE_CHART_IMAGE_COLS["image_url"],
        "style_no": size_chart_image_style_col,  # optional; None means "not mapped, skip style match"
    }

    currency_code = REGION_CURRENCY.get(region, "PHP")

    rows = []
    master_df = master_df.copy()

    # --- Grouping key: distinct COLOR (Color Number), for ALL divisions.
    # A group must always be a single style + single color combination, so
    # every color of a style gets its own separate Parent row and its own
    # set of Child rows -- sizes are the only thing that varies within a
    # group. (Color Number already encodes "StyleNumber_ColorSuffix" per
    # your Master Sheet convention, e.g. "695872_01", so grouping by it
    # alone is sufficient to separate different styles too.)
    def group_key(r):
        color_no = r.get(mc["color_no"], "")
        if color_no not in (None, "") and str(color_no).strip() not in ("", "nan"):
            return f"color__{color_no}"
        # Fallback when Color Number is missing for a row: group by Style
        # Number alone so it doesn't silently vanish or merge incorrectly.
        style = r.get(mc["style_no"], "")
        return f"style__{style}"

    master_df["_group_key"] = master_df.apply(group_key, axis=1)

    for group_key_val, group_df in master_df.groupby("_group_key", sort=False):
        first = group_df.iloc[0]
        ptype = first.get(mc["product_type"], "")
        footwear = is_footwear(ptype)

        gender_val = first.get(mc["gender"], "")
        title = clean_title(
            first.get(mc["brand"], ""),
            gender_val,
            first.get(mc["title"], ""),
            first.get(mc["footwear_color"], "") if footwear else "",
            footwear,
        )

        style_number = first.get(mc["style_no"], "")
        color_no_val = first.get(mc["color_no"], "")
        raw_desc = first.get(mc["description"], "")
        desc = clean_description(
            raw_desc,
            style_number,
            first.get(mc["care"], None),
            first.get(mc["care_label"], None),
        )

        # Model = the FULL Color Number code as it appears in the Master Sheet
        # (e.g. "695872_01") -- since each group is now a single style+color
        # combination, this correctly repeats across every size of that one
        # color, and differs across different colors/styles. Falls back to
        # Style Number only if Color Number is blank for a given row.
        color_no_str = str(color_no_val).strip() if color_no_val not in (None, "") and str(color_no_val).strip().lower() != "nan" else ""
        model_value = color_no_str if color_no_str else str(style_number)

        category_id = match_category_id(title, category_df, cc["keyword"], cc["category_id"])

        # --- Size Chart Template lookup (direct key match) -> "Template Attribute 1" ---
        size_chart_key = build_size_chart_key(
            first.get(mc["age_group"], ""),
            gender_val,
            first.get(mc["article_group"], ""),
            first.get(mc["article_type"], ""),
        )
        template_attr_1 = match_size_chart_template(
            size_chart_key, size_chart_template_df, sct["key"], sct["template_attribute_1"]
        )

        # --- Size Chart Sheet lookup (Style Number exact match first, then
        # normalized title-keyword match) -> "Size Chart Image URL" ---
        size_chart_image_url = match_size_chart_image(
            title, size_chart_image_df, sci["title_keyword"], sci["image_url"],
            style_number=style_number, style_col=sci["style_no"],
        )

        template_attr_2 = extract_description_main(raw_desc)
        template_attr_3 = extract_productstory(raw_desc)

        # --- Short Description: HTML bullet list built from group-level fields
        # (every row in the group shares the same style+color, so these are
        # read once from the group's first row, same as Title/Description). ---
        short_description = build_short_description(
            brand=_clean_field_value(first.get(mc["brand"], "")) or "PUMA",
            color_name=extract_search_color_name(first.get(mc["search_color_name"], "") or first.get(mc["color_name"], "")),
            gender=gender_val,
            activity_group=first.get(mc["activity_group"], ""),
            collection=first.get(mc["collection"], ""),
            material=first.get(mc["material"], ""),
            material_local=first.get(mc["material_local"], ""),
            upper_material=first.get(mc["upper_material"], ""),
            mid_sole_material=first.get(mc["mid_sole_material"], ""),
            outer_sole_material=first.get(mc["outer_sole_material"], ""),
            shell_material=first.get(mc["shell_material"], ""),
            toe_type=first.get(mc["toe_type"], ""),
            heel_type=first.get(mc["heel_type"], ""),
            fastener=first.get(mc["fastener"], ""),
            fit=first.get(mc["fit"], ""),
            puma_technology=first.get(mc["puma_technology"], ""),
            technology_purpose=first.get(mc["technology_purpose"], ""),
            style_number=style_number,
        )

        # Group has multiple rows (variants) -> insert a Parent row first.
        total_variation_count = len(group_df)
        has_variants = total_variation_count > 1

        base_row = {
            "Product Description 1": USER_TEMPLATE_NAME,
            "Product Name": title,
            "Title": title,
            "Description": desc,
            "Short Description": short_description,
            "Currency Code": currency_code,
            "Quantity": 0,
            "Category ID": category_id,
            "Size Chart Image URL": size_chart_image_url,
            "Tax Class": "Default",
            "Brand": "PUMA",
            "Model": model_value,
            "Warranty Type": "No Warranty",
            "Package Weight (kg)": 0.5,
            "Package Height(cm)": 15,
            "Package Length(cm)": 12,
            "Package Width(cm)": 12,
            "What's in the Box": f"1 X {title}",
            "Template Attribute 1": template_attr_1,
            "Template Attribute 2": template_attr_2,
            "Template Attribute 3": template_attr_3,
            "Region": region,
            "Marketplace": marketplace,
        }

        # Parent SKU: the group's own identifying SKU. Since every group is
        # now a single style+color combination, this is the FULL Color
        # Number code (e.g. "695872_01", matching the Model field).
        parent_sku_value = model_value

        # --- Parent row: write group-level details (title, brand, price type). ---
        # Variation 1 HEADER for the Parent row = "color_family"; Variation 2
        # HEADER for the Parent row = "size" (these are literal header labels,
        # not actual values). Total variation count appears ONLY on the Parent row.
        # Images are looked up once per group (by Model = Style+Color) and
        # shown on the Parent row too, since every child shares the same color.
        #
        # NOTE: a Parent row is ALWAYS created, even for a group with only a
        # single SKU / no size or color variants -- every SKU gets a Parent
        # above it, matching the marketplace bulk-upload structure exactly.
        # --- Sort child records FIRST so the Parent row can inherit the
        # first child's Product Specification 1/2 values (per spec: the
        # Parent row should show the first variant's spec values instead of
        # being left blank/"None"). ---
        child_records = group_df.to_dict("records")
        child_records.sort(
            key=lambda r: (
                str(r.get(mc["color_family"], "")),
                str(r.get(mc["color_name"], "")),
                size_sort_key(r.get(mc["uk_size"], r.get(mc["size"], "")), footwear),
            )
        )

        first_child_color_name = ""
        first_child_formatted_size = ""
        if child_records:
            first_rec = child_records[0]
            first_child_color_name = clean_color_name(first_rec.get(mc["color_name"], ""))
            first_child_formatted_size = format_size_value(first_rec.get(mc["uk_size"], ""), footwear)

        parent_images = "; ".join(get_images_for_key(model_value, image_df, ic["sku"], ic["url_col"]))
        parent_row = {
            "Row Type": "Parent",
            **base_row,
            "SKU": parent_sku_value,
            "Seller SKU": parent_sku_value,
            "Parent SKU": "",  # a Parent row has no parent of its own
            "Total variation": total_variation_count,
            "Variation 1": "color_family",
            "Variation 2": "size",
            "Stock": 0,
            "Images": parent_images,
            "Product Image URL(s)": parent_images,
            "Image URL": parent_images,
            # Parent inherits the first child's spec values instead of being blank.
            "Product Specification 1": f"sku.color_family={first_child_color_name}",
            "Product Specification 2": f"sku.size={first_child_formatted_size}",
        }
        rows.append(parent_row)

        # --- Child rows: variation1 = color no/style option, variation2 = size option. ---
        for rec in child_records:
            sku = rec.get(mc["sku"], "")
            color_name = clean_color_name(rec.get(mc["color_name"], ""))
            uk_size_raw = rec.get(mc["uk_size"], "")
            formatted_size = format_size_value(uk_size_raw, footwear)
            child_row = {
                "Row Type": "Child",
                **base_row,
                "Description": "",  # child rows: SKU-specific only
                "SKU": sku,
                "Seller SKU": sku,
                "Parent SKU": parent_sku_value,
                "Total variation": "",  # Total variation appears ONLY on the Parent row
                "RRP": get_price(rec, price_col),
                # Variation 1 fetches Color Name directly from the Master Input Sheet.
                "Variation 1": color_name,
                "Variation 2": formatted_size,
                "Product Specification 1": f"sku.color_family={color_name}",
                "Product Specification 2": f"sku.size={formatted_size}",
                "Stock": 0,
                "Images": "; ".join(get_images_for_key(model_value, image_df, ic["sku"], ic["url_col"])),
                "Product Image URL(s)": "; ".join(get_images_for_key(model_value, image_df, ic["sku"], ic["url_col"])),
                "Image URL": "; ".join(get_images_for_key(model_value, image_df, ic["sku"], ic["url_col"])),
            }
            rows.append(child_row)

    out_df = pd.DataFrame(rows)

    # Capture parent/child counts BEFORE trimming to the Sample Upload Format's
    # columns — "Row Type" is an internal tracking column and may not exist in
    # the sample header, so it can be dropped in the next step.
    parent_count = int((out_df["Row Type"] == "Parent").sum()) if "Row Type" in out_df.columns else 0
    child_count = int((out_df["Row Type"] == "Child").sum()) if "Row Type" in out_df.columns else 0

    # Output STRICTLY follows the Sample Upload Format headers — no extra columns,
    # no reordering, missing ones filled blank. If "Row Type" isn't one of the
    # sample's headers, it is correctly dropped here.
    for col in output_columns:
        if col not in out_df.columns:
            out_df[col] = ""
    out_df = out_df[output_columns]

    return out_df, parent_count, child_count


# ======================================================================================
# STREAMLIT UI
# ======================================================================================

st.set_page_config(page_title="Marketplace Upload Sheet Generator", layout="wide")
st.title("🛒 Marketplace Bulk Upload Sheet Generator")

st.markdown(
    """
Upload your source sheets below. **Master Sheet column mapping is now done in the UI**
(see the "Map Master Sheet columns" section once you upload it) — you no longer need to
edit `app.py` to match your real headers for those fields.

**Note:** the Tracker Sheet has been removed — price is now read directly from a
column on the Master Input Sheet. There are now TWO separate size-chart-related
uploads: the **Size Chart Sheet** (matched by title reference) fills the
**"Size Chart Image URL"** output column, and the **Size Chart Template Sheet**
(direct key lookup) fills the **"Template Attribute 1"** output column. The
**Sample Upload Format is now required** — output columns/order will always
match it exactly.
"""
)

st.markdown("### 🌏 Region & Marketplace")
rcol1, rcol2 = st.columns(2)
with rcol1:
    selected_region = st.selectbox("Region", options=REGIONS, index=REGIONS.index("PH"))
with rcol2:
    selected_marketplace = st.selectbox("Marketplace", options=MARKETPLACES, index=MARKETPLACES.index("Lazada"))

st.markdown("### 📁 Source Files")
col1, col2 = st.columns(2)
with col1:
    master_file = st.file_uploader("Master Input Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="master")
    image_file = st.file_uploader("Image Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="images")
    category_file = st.file_uploader("Category Sheet (.xlsx/.csv)", type=["xlsx", "csv"], key="category")
    size_chart_image_file = st.file_uploader(
        "Size Chart Sheet (.xlsx/.csv) — provides the Size Chart Image URL, matched by title",
        type=["xlsx", "csv"], key="sizechartimage",
    )
with col2:
    size_chart_template_file = st.file_uploader(
        "Size Chart Template Sheet (.xlsx/.csv) — provides Template Attribute 1, direct key lookup",
        type=["xlsx", "csv"], key="sizecharttemplate"
    )
    sample_file = st.file_uploader(
        "Sample Upload Format (.xlsx/.csv) — REQUIRED, defines exact output columns",
        type=["xlsx", "csv"], key="sample",
    )


def load_any(f):
    if f is None:
        return None
    if f.name.lower().endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)


# --- Master Sheet full field mapping (fixes Title/SKU/Variation/price blanks) ---
# Every field the app needs from the Master Sheet is now explicitly mapped by
# you, at runtime, from your file's real headers — instead of silently
# defaulting to "" when a hard-coded CONFIG name doesn't match.
price_col = MASTER_COLS["price"]
master_col_map = {}

if master_file is not None:
    _master_preview_df = load_any(master_file)
    master_file.seek(0)  # reset pointer so it can be read again later
    master_cols_available = list(_master_preview_df.columns)

    st.markdown("#### 📌 Master Sheet — Column Mapping")
    st.caption(
        "Map every field to the matching column in your uploaded Master Sheet. "
        "This is what fills in Title, SKU, Parent SKU, and Variation 1/2 correctly — "
        "if a field is left unmapped, that part of the output stays blank."
    )

    with st.expander("Map Master Sheet columns", expanded=True):
        none_option = "— not in my sheet —"
        options_with_none = [none_option] + master_cols_available

        mcol1, mcol2 = st.columns(2)
        for i, (field_key, field_label, required) in enumerate(MASTER_COLS_FIELDS):
            default_header = MASTER_COLS[field_key]
            default_idx = (
                options_with_none.index(default_header) if default_header in options_with_none else 0
            )
            target_col = mcol1 if i % 2 == 0 else mcol2
            with target_col:
                label = f"{field_label}" + (" *" if required else "")
                chosen = st.selectbox(
                    label,
                    options=options_with_none,
                    index=default_idx,
                    key=f"master_col_map_{field_key}",
                )
                master_col_map[field_key] = "" if chosen == none_option else chosen

        st.markdown("#### 📌 Price Column")
        default_price_idx = (
            master_cols_available.index(price_col) if price_col in master_cols_available else 0
        )
        price_col = st.selectbox(
            "Price column in Master Input Sheet",
            options=master_cols_available,
            index=default_price_idx,
            key="master_price_col_select",
            help="Choose which column in the Master Input Sheet holds the price to pull into the upload sheet.",
        )

# --- Size Chart Template Sheet column pickers ---
# Instead of requiring your sheet's headers to literally match the CONFIG
# constants (which is what caused the "Size Chart Key" crash), let you pick
# the real column names from a dropdown once the file is uploaded.
size_chart_key_col = SIZE_CHART_TEMPLATE_COLS["key"]
size_chart_attr_col = SIZE_CHART_TEMPLATE_COLS["template_attribute_1"]

if size_chart_template_file is not None:
    _sct_preview_df = load_any(size_chart_template_file)
    size_chart_template_file.seek(0)
    sct_cols_available = list(_sct_preview_df.columns)

    st.markdown("#### 📌 Size Chart Template Sheet — Column Selection")
    sc1, sc2 = st.columns(2)
    with sc1:
        default_key_idx = (
            sct_cols_available.index(size_chart_key_col) if size_chart_key_col in sct_cols_available else 0
        )
        size_chart_key_col = st.selectbox(
            "Lookup key column (Age Group-Gender-Article Group-Article Type)",
            options=sct_cols_available,
            index=default_key_idx,
            key="size_chart_key_col_select",
        )
    with sc2:
        default_attr_idx = (
            sct_cols_available.index(size_chart_attr_col) if size_chart_attr_col in sct_cols_available else 0
        )
        size_chart_attr_col = st.selectbox(
            "Template Attribute 1 value column",
            options=sct_cols_available,
            index=default_attr_idx,
            key="size_chart_attr_col_select",
        )

# --- Size Chart Sheet column pickers (NEW: title-referenced Size Chart Image URL) ---
size_chart_image_title_col = SIZE_CHART_IMAGE_COLS["title_keyword"]
size_chart_image_url_col = SIZE_CHART_IMAGE_COLS["image_url"]

if size_chart_image_file is not None:
    _sci_preview_df = load_any(size_chart_image_file)
    size_chart_image_file.seek(0)
    sci_cols_available = list(_sci_preview_df.columns)

    st.markdown("#### 📌 Size Chart Sheet — Column Selection")
    st.caption(
        "The Title column here is matched (as a keyword) against each product's generated "
        "Title — the longest matching row wins. Its Image URL then fills the 'Size Chart "
        "Image URL' output column."
    )
    sci1, sci2 = st.columns(2)
    with sci1:
        default_sci_title_idx = (
            sci_cols_available.index(size_chart_image_title_col) if size_chart_image_title_col in sci_cols_available else 0
        )
        size_chart_image_title_col = st.selectbox(
            "Title / keyword column (matched against product Title)",
            options=sci_cols_available,
            index=default_sci_title_idx,
            key="size_chart_image_title_col_select",
        )
    with sci2:
        default_sci_url_idx = (
            sci_cols_available.index(size_chart_image_url_col) if size_chart_image_url_col in sci_cols_available else 0
        )
        size_chart_image_url_col = st.selectbox(
            "Size Chart Image URL column",
            options=sci_cols_available,
            index=default_sci_url_idx,
            key="size_chart_image_url_col_select",
        )

    st.caption(
        "Optional but recommended: if your Size Chart Sheet also has a Style Number "
        "column, mapping it here gives an exact match tried BEFORE the title/keyword "
        "match above — more reliable than free-text title matching."
    )
    sci_none_option = "— not in my sheet / skip —"
    sci_style_options = [sci_none_option] + sci_cols_available
    default_sci_style_idx = (
        sci_style_options.index(SIZE_CHART_IMAGE_COLS["style_no"])
        if SIZE_CHART_IMAGE_COLS["style_no"] in sci_style_options else 0
    )
    _sci_style_choice = st.selectbox(
        "Style Number column (optional)",
        options=sci_style_options,
        index=default_sci_style_idx,
        key="size_chart_image_style_col_select",
    )
    size_chart_image_style_col = None if _sci_style_choice == sci_none_option else _sci_style_choice
else:
    size_chart_image_style_col = None

# --- Category Sheet column pickers ---
category_keyword_col = CATEGORY_SHEET_COLS["keyword"]
category_id_col = CATEGORY_SHEET_COLS["category_id"]

if category_file is not None:
    _cat_preview_df = load_any(category_file)
    category_file.seek(0)
    cat_cols_available = list(_cat_preview_df.columns)

    st.markdown("#### 📌 Category Sheet — Column Selection")
    cc1, cc2 = st.columns(2)
    with cc1:
        default_kw_idx = (
            cat_cols_available.index(category_keyword_col) if category_keyword_col in cat_cols_available else 0
        )
        category_keyword_col = st.selectbox(
            "Title keyword column",
            options=cat_cols_available,
            index=default_kw_idx,
            key="category_keyword_col_select",
        )
    with cc2:
        default_id_idx = (
            cat_cols_available.index(category_id_col) if category_id_col in cat_cols_available else 0
        )
        category_id_col = st.selectbox(
            "Category ID column",
            options=cat_cols_available,
            index=default_id_idx,
            key="category_id_col_select",
        )

# --- Image Sheet column picker ---
image_sku_col = IMAGE_SHEET_COLS["sku"]
image_url_col = IMAGE_SHEET_COLS["url_col"]

if image_file is not None:
    _img_preview_df = load_any(image_file)
    image_file.seek(0)
    img_cols_available = list(_img_preview_df.columns)

    st.markdown("#### 📌 Image Sheet — Column Selection")
    st.caption(
        "Your Image Sheet is a long/tall list — one row per image, with the SAME "
        "Color Number repeating across multiple rows. Every row matching a given "
        "Color Number contributes one image link, so pick BOTH the Color Number "
        "column and the URL/Link column below (not a set of 'Image 1'..'Image N' "
        "columns)."
    )
    ic1, ic2 = st.columns(2)
    with ic1:
        default_img_sku_idx = guess_column_index(
            img_cols_available, image_sku_col, keywords=["color number", "colornumber", "color no", "color"]
        )
        image_sku_col = st.selectbox(
            "Color Number column in Image Sheet",
            options=img_cols_available,
            index=default_img_sku_idx,
            key="image_sku_col_select",
        )
    with ic2:
        default_img_url_idx = guess_column_index(
            img_cols_available, image_url_col, keywords=["url", "link", "image"]
        )
        image_url_col = st.selectbox(
            "Image URL / Link column in Image Sheet",
            options=img_cols_available,
            index=default_img_url_idx,
            key="image_url_col_select",
        )

    if image_sku_col == image_url_col:
        st.warning(
            "⚠️ Color Number column and Image URL column are set to the SAME column "
            "— images will not resolve correctly. Please pick two different columns above."
        )


if st.button("🚀 Generate Upload Sheet", type="primary"):
    if master_file is None:
        st.error("Master Input Sheet is required.")
    elif sample_file is None:
        st.error("Sample Upload Format is required — it defines the exact output columns/order.")
    else:
        with st.spinner("Processing..."):
            master_df = load_any(master_file)
            image_df = load_any(image_file)
            size_chart_template_df = load_any(size_chart_template_file)
            size_chart_image_df = load_any(size_chart_image_file)
            category_df = load_any(category_file)
            sample_df = load_any(sample_file)

            output_columns = list(sample_df.columns)

            try:
                result_df, parent_count, child_count = build_upload_sheet(
                    master_df, image_df, size_chart_template_df, category_df, output_columns,
                    price_col=price_col,
                    master_col_map=master_col_map,
                    image_sku_col=image_sku_col,
                    image_url_col=image_url_col,
                    size_chart_key_col=size_chart_key_col,
                    size_chart_attr_col=size_chart_attr_col,
                    category_keyword_col=category_keyword_col,
                    category_id_col=category_id_col,
                    size_chart_image_df=size_chart_image_df,
                    size_chart_image_title_col=size_chart_image_title_col,
                    size_chart_image_url_col=size_chart_image_url_col,
                    size_chart_image_style_col=size_chart_image_style_col,
                    region=selected_region,
                    marketplace=selected_marketplace,
                )
            except KeyError as e:
                st.error(
                    f"Column mapping mismatch: {e}. "
                    "Please edit the CONFIG constants (MASTER_COLS, IMAGE_SHEET_COLS, "
                    "SIZE_CHART_TEMPLATE_COLS, SIZE_CHART_IMAGE_COLS, CATEGORY_SHEET_COLS) "
                    "at the top of app.py to match your actual sheet's column headers, then rerun."
                )
                st.stop()

        st.success(f"Generated {len(result_df)} rows ({parent_count} parent, {child_count} child).")
        st.dataframe(result_df, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Upload")
        buffer.seek(0)

        st.download_button(
            "⬇️ Download Upload Sheet (.xlsx)",
            data=buffer,
            file_name="marketplace_upload_sheet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
else:
    st.info("Upload your files and click **Generate Upload Sheet** to begin.")
