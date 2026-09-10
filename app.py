"""
Marketplace Bulk Upload Sheet Generator
========================================
"""

import io
import re
from collections import OrderedDict

import pandas as pd
import numpy as np
import streamlit as st

# ======================================================================================
# CONFIG
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
    "price": "Price",
    "description": "Description",
    "care": "Care",
    "care_label": "Care Label",
    "category_hint": "Category",
    "footwear_color": "Footwear Color",
    "product_type": "Product Type",
    "age_group": "Age Group",
    "article_group": "Article Group",
    "article_type": "Article Type",
    "activity_group": "Activity Group",
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

MASTER_COLS_FIELDS = [
    ("style_no", "Style Number", True),
    ("color_no", "Color Number (Footwear)", True),
    ("brand", "Brand", True),
    ("gender", "Gender", True),
    ("title", "Regional Display Name (used in Title)", True),
    ("color_family", "Color Family", True),
    ("color_name", "Color Name (used in Variation 1)", True),
    ("search_color_name", "Search Color Name (used in Title/Short Description, code stripped)", False),
    ("size", "Size", False),
    ("uk_size", "UK Size (used in Variation 2)", True),
    ("sku", "SKU", True),
    ("description", "Description", True),
    ("care", "Care", False),
    ("care_label", "Care Label", False),
    ("footwear_color", "Footwear Color (legacy, no longer used in Title)", False),
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
    "sku": "ColorNumber",
    "url_col": "Product Image URL(s)",
}

# All three mapping sheets (Category, Size Chart, Size Chart Template) now
# share the SAME literal composite key column header:
#   "Age Group+Gender+Article Group+Article Type+Activity Group+Product Division"
# built from the Master Input Sheet's respective columns, joined with "+".
COMPOSITE_KEY_COLUMN_NAME = "Age Group+Gender+Article Group+Article Type+Activity Group+Product Division"

SIZE_CHART_IMAGE_COLS = {
    "composite_key": COMPOSITE_KEY_COLUMN_NAME,  # PRIMARY match: shared composite key
    "gender_article_key": "Gender_ArticleGroup",  # your actual Size Chart Sheet header
    "title_keyword": "Title",                     # fallback only
    "image_url": "Size chart link",  # matches your actual Size Chart Sheet header -> output "Size chart Image URL"
    "style_no": "Style Number",       # fallback only
}

SIZE_CHART_TEMPLATE_COLS = {
    "key": COMPOSITE_KEY_COLUMN_NAME,  # PRIMARY match: shared composite key
    "template_attribute_1": "size chart template",  # matches your actual Size Chart Template Sheet header -> output "Template Attribute 1"
}

CATEGORY_SHEET_COLS = {
    "composite_key": COMPOSITE_KEY_COLUMN_NAME,  # PRIMARY match: shared composite key
    "category_name": "Category Name",  # fallback only (breadcrumb-style name, attribute-substring scoring)
    "keyword": "Title Keyword",        # fallback only (exact keyword sheet, if you have one)
    "category_id": "Category ID",
}


REGION_CURRENCY = {"SG": "SGD", "MY": "MYR", "PH": "PHP"}
MARKETPLACES = ["Lazada", "Shopee", "Zalora", "Tiktok"]
REGIONS = ["SG", "MY", "PH"]
USER_TEMPLATE_NAME = "userTemplate-PumaAccessories"

TITLE_REPLACEMENTS = OrderedDict([
    (r"\bTrainers\b", "Shoes"),
    (r"\bSandals\b", "Sports Sandals"),
    (r"\bSlides\b", "Slides Slippers"),
])

ALPHA_SIZE_ORDER = ["XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "OSFA", "Youth"]


# ======================================================================================
# HELPERS
# ======================================================================================

def clean_color_name(raw):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw).strip()
    if s.lower() in ("", "nan"):
        return ""
    if " - " in s:
        s = s.split(" - ")[-1].strip()
    if re.fullmatch(r"[\d_\-\s]+", s):
        return ""
    s = re.sub(r"^[\d_]+[\s\-_]*", "", s).strip()
    return s


def guess_column_index(options, preferred_name, keywords):
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


def guess_column_or_none(options, preferred_name, keywords):
    """
    Like guess_column_index, but returns None (instead of falling back to
    index 0 / the first column) when nothing actually matches. Use this for
    OPTIONAL fields, where guessing a random unrelated column would be worse
    than correctly leaving the field unmapped.
    """
    norm_options = [str(o).strip().lower() for o in options]
    preferred_norm = str(preferred_name).strip().lower()
    if preferred_norm in norm_options:
        return options[norm_options.index(preferred_norm)]
    for kw in keywords:
        kw_norm = kw.strip().lower()
        for i, opt in enumerate(norm_options):
            if kw_norm in opt:
                return options[i]
    return None


def guess_composite_key_column(options):
    """
    Strict guess for the 6-field composite key column (Age Group+Gender+
    Article Group+Article Type+Activity Group+Product Division). Only
    matches a column whose header ACTUALLY CONTAINS "+" joining at least
    two of the expected field names -- a loose keyword guess (e.g. just
    "group" or "category") was previously grabbing unrelated columns like
    "Category ID". Returns None if no such column exists.
    """
    field_words = ["age group", "gender", "article group", "article type", "activity group", "product division"]
    for opt in options:
        norm = str(opt).strip().lower()
        if "+" not in norm:
            continue
        hit_count = sum(1 for w in field_words if w.replace(" ", "") in norm.replace(" ", ""))
        if hit_count >= 2:
            return opt
    return None


def guess_gender_article_group_column(options):
    """
    Strict guess for a Gender_ArticleGroup-style key column (the format your
    actual Size Chart / Size Chart Template sheets use). Matches a column
    whose header contains both "gender" and "article" (any separator), but
    rejects anything that also contains "+" (that's the 6-field composite
    key, a different column) or looks like an ID/name column.
    """
    for opt in options:
        norm = str(opt).strip().lower().replace(" ", "")
        if "+" in norm:
            continue
        if "gender" in norm and "article" in norm:
            return opt
    return None


def normalize_match_text(s):
    if s is None:
        return ""
    s = str(s).replace("™", "").replace("®", "")
    s = re.sub(r"[^A-Za-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


# Common typos/misspellings seen in real Gender/Article Group data (e.g. a
# Size Chart Sheet row literally spelled "Feamle_Cap" instead of
# "Female_Cap"). Corrected on a per-WORD basis after normalization so a
# single typo'd cell doesn't silently fail to match forever.
GENDER_TYPO_CORRECTIONS = {
    "feamle": "female",
    "femle": "female",
    "femal": "female",
    "mens": "male",
    "womens": "female",
    "boy": "boys",
    "girl": "girls",
}


def correct_gender_typos(normalized_text):
    """Applies known typo corrections to an already-normalized (lowercase,
    whitespace-collapsed) string, word by word."""
    words = normalized_text.split()
    corrected = [GENDER_TYPO_CORRECTIONS.get(w, w) for w in words]
    return " ".join(corrected)


def expand_gender_article_candidates(raw_sheet_value):
    """
    Expands a Gender_ArticleGroup-style sheet value into every individual
    (gender, article group) key it could represent, handling:
      - Simple single values: "Male_Top" -> ["male_top"]
      - Multi-gender cells joined by "/": "Male/Unisex_Footwear" or
        "Male / Female / Unisex_Headwear" -> one candidate key PER gender
        listed, each paired with the same article group.
      - Typos in the gender portion (e.g. "Feamle") corrected via
        GENDER_TYPO_CORRECTIONS.
    Returns a list of normalized "gender_articlegroup" strings (using the
    SAME separator/normalization as build_gender_article_group_key), so a
    Master Sheet row with a single plain gender still matches a sheet row
    that lists several genders together in one cell.
    """
    if raw_sheet_value is None:
        return []
    s = str(raw_sheet_value).strip()
    if not s or s.lower() == "nan":
        return []

    # Split on the LAST underscore to separate the gender portion from the
    # article group portion (article group itself may not contain "_").
    if "_" in s:
        gender_part, article_part = s.rsplit("_", 1)
    else:
        gender_part, article_part = s, ""

    # Multiple genders in one cell are separated by "/" (with or without
    # surrounding spaces): "Male/Unisex" or "Male / Female / Unisex".
    gender_candidates = [g.strip() for g in gender_part.split("/") if g.strip()]
    if not gender_candidates:
        gender_candidates = [gender_part]

    article_norm = correct_gender_typos(normalize_match_text(article_part))

    results = []
    for g in gender_candidates:
        gender_norm = correct_gender_typos(normalize_match_text(g))
        results.append(f"{gender_norm}_{article_norm}")
    return results


def clean_title(brand, gender, title, search_color_name_raw, is_footwear=None):
    """
    Build title per spec:
    [NEW] [Brand] [Gender] [Regional Display Name] ( Color)
    Gender only included when it's "Unisex". Search Color Name is appended
    for EVERY division, wrapped in PARENTHESES with a leading space inside,
    e.g. "( White)" -- matching the required sample format exactly.
    """
    title = title or ""
    for pattern, repl in TITLE_REPLACEMENTS.items():
        title = re.sub(pattern, repl, title, flags=re.IGNORECASE)

    search_color_name = clean_color_name(search_color_name_raw)

    parts = ["[NEW]"]
    if brand:
        parts.append(str(brand).strip())
    if gender and str(gender).strip().lower() == "unisex":
        parts.append(str(gender).strip())
    if title:
        parts.append(title.strip())

    # remove duplicate words anywhere in the title (case-insensitive), preserve first occurrence
    seen = set()
    deduped = []
    for word in " ".join(parts).split():
        key = word.lower()
        if key in seen and key not in ("[new]",):
            continue
        seen.add(key)
        deduped.append(word)
    base_title = " ".join(deduped).strip()

    if search_color_name:
        base_title = f"{base_title} ( {search_color_name})"

    return base_title


def clean_description(raw_desc, style_number, care=None, care_label=None):
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        raw_desc = ""
    desc = str(raw_desc)
    desc = re.sub(r"<h3>\s*product\s*story\s*</h3>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<br\s*/?>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</br>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<h3>\s*details\s*</h3>", "\n\nDETAILS", desc, flags=re.IGNORECASE)
    desc = re.sub(
        r"<h3>\s*features\s*(&|\+)\s*benefits\s*</h3>",
        "\n\nFEATURES & BENEFITS",
        desc,
        flags=re.IGNORECASE,
    )
    desc = re.sub(r"<li[^>]*>", "\r\n- ", desc, flags=re.IGNORECASE)
    for tag in [r"</li>", r"<ul[^>]*>", r"</ul>", r"<p[^>]*>", r"</p>"]:
        desc = re.sub(tag, "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<[^>]+>", "", desc)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in desc.splitlines()]
    lines = [ln for ln in lines if ln != ""]
    desc = "\n".join(lines).strip()
    tail = [f"Style : {style_number}"]
    if care and str(care).strip().lower() not in ("nan", ""):
        tail.append(f'"CARE"\n{str(care).strip()}')
    if care_label and str(care_label).strip().lower() not in ("nan", ""):
        tail.append(f'"CARE LABEL"\n{str(care_label).strip()}')
    desc = desc + "\n\n" + "\n\n".join(tail)
    return desc.strip()


def is_footwear(product_division):
    if not product_division:
        return False
    return str(product_division).strip().lower() in ("footwear", "shoes", "trainers", "sandals", "slides")


def size_sort_key(size_val, is_footwear_row=False):
    s = str(size_val).strip().upper()
    if s in ALPHA_SIZE_ORDER:
        return (0, ALPHA_SIZE_ORDER.index(s), 0, "")
    try:
        num = float(re.sub(r"[^\d.]", "", s))
        return (1, 0, num, "")
    except (ValueError, TypeError):
        return (2, 0, 0, s)


def match_category_id_by_attributes(attribute_values, category_df, name_col, id_col):
    """
    Best-possible-match strategy for a Category Sheet that only has a
    breadcrumb-style Category Name column (e.g. "Kids' Fashion:Baby
    Clothing:Beachwear & Accessories") and NO dedicated composite key
    column -- your actual sheet's structure.

    Scores every Category Name row by how many of the given attribute
    values (Age Group, Gender, Article Group, Article Type, Activity Group,
    Product Division) appear as a normalized substring within that row's
    Category Name, and returns the ID of the row with the highest score.
    This is the "combination of all available attributes" match required
    by spec point 1, adapted to a sheet with no explicit key column.

    Returns "" if nothing scores above zero -- never guesses blindly.
    """
    if category_df is None or category_df.empty:
        return ""
    if name_col not in category_df.columns or id_col not in category_df.columns:
        return ""

    clean_attrs = [normalize_match_text(a) for a in attribute_values if _clean_field_value(a)]
    clean_attrs = [a for a in clean_attrs if a]
    if not clean_attrs:
        return ""

    best_id = ""
    best_score = 0
    best_specificity = 0  # tie-break: prefer the longer/more specific name text matched
    for _, row in category_df.iterrows():
        name_norm = normalize_match_text(row.get(name_col, ""))
        if not name_norm:
            continue
        score = sum(1 for a in clean_attrs if a in name_norm)
        if score > best_score or (score == best_score and score > 0 and len(name_norm) > best_specificity):
            best_score = score
            best_specificity = len(name_norm)
            best_id = row.get(id_col, "")

    return best_id if best_score > 0 else ""


def build_composite_key(age_group, gender, article_group, article_type, activity_group, product_division):
    """
    THE single composite lookup key used across ALL THREE mapping sheets
    (Category, Size Chart, Size Chart Template), built from the Master Input
    Sheet's respective columns, joined with "+" to match the sheets' shared
    literal header:
      "Age Group+Gender+Article Group+Article Type+Activity Group+Product Division"
    Normalized (case-insensitive, whitespace-collapsed) before comparison so
    minor formatting differences don't break the match.
    """
    parts = [age_group, gender, article_group, article_type, activity_group, product_division]
    return "+".join(normalize_match_text(p) for p in parts)


# Kept as an alias for backward compatibility with any earlier call sites.
def build_category_key(age_group, gender, article_group, article_type, activity_group, product_division):
    return build_composite_key(age_group, gender, article_group, article_type, activity_group, product_division)


def match_category_id(title, category_df, keyword_col, id_col,
                       composite_key=None, composite_key_col=None,
                       attribute_values=None, name_col=None):
    """
    Resolves Category ID. Strategies, tried in order:
      1. COMPOSITE KEY exact match (if your Category Sheet has a dedicated
         key column -- AgeGroup-Gender-ArticleGroup-ArticleType-
         ActivityGroup-ProductDivision, normalized before comparing).
      2. ATTRIBUTE-SUBSTRING scoring against a Category Name column (your
         actual sheet's structure -- breadcrumb-style names, no key column).
         Uses the combination of all available attributes to find the best
         match, per spec.
      3. TITLE keyword match (last-resort fallback).
    Returns "" (leaving the cell blank) if nothing matches -- existing
    values are never overwritten with a bad guess.
    """
    if category_df is None or category_df.empty:
        return ""

    if (composite_key_col and composite_key not in (None, "")
            and composite_key_col in category_df.columns
            and id_col in category_df.columns):
        norm_key = str(composite_key).strip().lower()
        sheet_keys_norm = category_df[composite_key_col].astype(str).apply(normalize_match_text)
        key_match = category_df[sheet_keys_norm == norm_key]
        if not key_match.empty:
            val = key_match.iloc[0].get(id_col, "")
            if val and str(val).strip():
                return val

    if attribute_values and name_col:
        attr_result = match_category_id_by_attributes(attribute_values, category_df, name_col, id_col)
        if attr_result:
            return attr_result

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


def build_size_chart_image_key(age_group, gender, article_group, article_type, activity_group):
    """
    Full composite lookup key for the Size Chart Image URL, built from:
      AgeGroup-Gender-ArticleGroup-ArticleType-ActivityGroup
    Normalized (case-insensitive, whitespace-collapsed) before comparison.
    """
    parts = [age_group, gender, article_group, article_type, activity_group]
    return "-".join(normalize_match_text(p) for p in parts)


def build_gender_article_group_key(gender, article_group):
    """
    Gender+ArticleGroup lookup key, per spec point 2: "Use the Gender +
    Article Group mapping to identify the correct size chart." Normalized
    the same way as the other keys, with common typo corrections applied
    (e.g. "Feamle" -> "female") so a misspelling on either side doesn't
    silently break the match.
    """
    gender_norm = correct_gender_typos(normalize_match_text(gender))
    article_norm = correct_gender_typos(normalize_match_text(article_group))
    return f"{gender_norm}_{article_norm}"


def match_size_chart_image(title, size_chart_image_df, title_col, url_col,
                            style_number=None, style_col=None,
                            composite_key=None, composite_key_col=None,
                            gender_article_key=None, gender_article_key_col=None):
    """
    Resolves the Size Chart Image URL. Strategies, tried in order:
      1. GENDER + ARTICLE GROUP exact match (PRIMARY): your actual sheet's
         key column.
      2. FULL COMPOSITE KEY exact match (fallback): Age Group+Gender+Article
         Group+Article Type+Activity Group+Product Division, tried if (1)
         doesn't resolve anything.
      3. STYLE NUMBER exact match (further fallback).
      4. TITLE keyword match (last-resort fallback).
    All comparisons are normalized (case-insensitive, whitespace-collapsed).
    Returns "" (leaving the cell blank) if nothing matches at all --
    existing values are never overwritten with a bad guess.
    """
    if size_chart_image_df is None or size_chart_image_df.empty:
        return ""

    if (gender_article_key_col and gender_article_key not in (None, "")
            and gender_article_key_col in size_chart_image_df.columns
            and url_col in size_chart_image_df.columns):
        # Row-wise match with multi-gender expansion + typo correction, so a
        # sheet cell like "Male/Unisex_Footwear" or "Feamle_Cap" (typo) still
        # matches a plain single-gender Master Sheet row. gender_article_key
        # is already built via build_gender_article_group_key() (normalized +
        # typo-corrected), so no further normalization needed on that side.
        for _, row in size_chart_image_df.iterrows():
            candidates = expand_gender_article_candidates(row.get(gender_article_key_col, ""))
            if gender_article_key in candidates:
                val = row.get(url_col, "")
                if val and str(val).strip():
                    return val

    if (composite_key_col and composite_key not in (None, "")
            and composite_key_col in size_chart_image_df.columns
            and url_col in size_chart_image_df.columns):
        norm_key = normalize_match_text(composite_key)
        sheet_keys_norm = size_chart_image_df[composite_key_col].astype(str).apply(normalize_match_text)
        key_match = size_chart_image_df[sheet_keys_norm == norm_key]
        if not key_match.empty:
            val = key_match.iloc[0].get(url_col, "")
            if val and str(val).strip():
                return val

    if style_col and style_number not in (None, "") and style_col in size_chart_image_df.columns and url_col in size_chart_image_df.columns:
        norm_style = str(style_number).strip().lower()
        style_match = size_chart_image_df[
            size_chart_image_df[style_col].astype(str).str.strip().str.lower() == norm_style
        ]
        if not style_match.empty:
            val = style_match.iloc[0].get(url_col, "")
            if val and str(val).strip():
                return val

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
    if uk_size is None or (isinstance(uk_size, float) and pd.isna(uk_size)) or str(uk_size).strip() == "":
        return ""
    s = str(uk_size).strip()
    if s.upper() == "OSFA":
        s = "One size"
    if is_footwear_row:
        return f"UK:{s}"
    return f"Int:{s}"


def build_size_chart_key(gender, article_group):
    """
    Size Chart TEMPLATE lookup key: Gender_ArticleGroup, per spec (point 3),
    normalized (case-insensitive, whitespace-collapsed) before comparison.
    """
    parts = [gender, article_group]
    return "_".join(normalize_match_text(p) for p in parts)


def match_size_chart_template(size_chart_key, size_chart_template_df, key_col, attr_col):
    """
    Matches the selected key column against the Size Chart Template Sheet.
    Two strategies, tried in order:
      1. Gender_ArticleGroup-style expansion match (handles multi-gender
         cells like "Male/Unisex_Footwear" and typos like "Feamle_Cap").
      2. Plain normalized equality match -- handles a composite key column
         like "Age Group+Gender+Article Group+Article Type+Activity
         Group+Product Division" (no underscore-based gender parsing needed
         here, just an exact normalized string match).
    Returns the Template value formatted as "sizechart=<value>" -- if the
    sheet's value already includes that prefix, it is NOT duplicated.
    Returns "" (leaving the cell blank) if nothing matches -- never
    overwrites with a guess.
    """
    if size_chart_template_df is None or size_chart_template_df.empty:
        return ""
    if key_col not in size_chart_template_df.columns or attr_col not in size_chart_template_df.columns:
        return ""

    matched_row = None

    # Strategy 1: Gender_ArticleGroup-style expansion.
    for _, row in size_chart_template_df.iterrows():
        candidates = expand_gender_article_candidates(row.get(key_col, ""))
        if size_chart_key in candidates:
            matched_row = row
            break

    # Strategy 2: plain normalized equality (composite key format).
    if matched_row is None:
        norm_key = normalize_match_text(size_chart_key)
        sheet_keys_norm = size_chart_template_df[key_col].astype(str).apply(normalize_match_text)
        eq_match = size_chart_template_df[sheet_keys_norm == norm_key]
        if not eq_match.empty:
            matched_row = eq_match.iloc[0]

    if matched_row is None:
        return ""

    raw_val = matched_row.get(attr_col, "")
    val = _clean_field_value(raw_val) if raw_val is not None else ""
    if not val:
        return ""
    if val.strip().lower().startswith("sizechart="):
        return val.strip()
    return f"sizechart={val}"


def match_size_chart_by_title(title, size_chart_image_df, title_col, url_col):
    """
    NEW: Size Chart column now updates strictly per generated Title, using
    normalized longest-keyword-in-title matching (same normalization as
    match_size_chart_image) against the Size Chart Sheet's title column.
    """
    return match_size_chart_image(title, size_chart_image_df, title_col, url_col)


def get_images_for_key(lookup_value, image_df, lookup_col, url_col):
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
    if price_col not in row or pd.isna(row.get(price_col, None)):
        return ""
    return row.get(price_col, "")


def extract_search_color_name(raw_color):
    return clean_color_name(raw_color)


def extract_description_main(raw_desc):
    if raw_desc is None or (isinstance(raw_desc, float) and pd.isna(raw_desc)):
        return ""
    desc = str(raw_desc)
    desc = re.sub(r"<h[1-6]>\s*product\s*story\s*</h[1-6]>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<p>\s*product\s*story\s*</p>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"product\s*story", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<br\s*/?>", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</br>", "", desc, flags=re.IGNORECASE)
    split_pattern = re.compile(
        r"<h[1-6]>\s*(features\s*(&|\+)\s*benefits|details)\s*",
        re.IGNORECASE
    )
    match = split_pattern.search(desc)
    main_part = desc[:match.start()] if match else desc
    main_text = re.sub(r"</?p[^>]*>", "", main_part, flags=re.IGNORECASE).strip()
    main_text = re.sub(r"\s+", " ", main_text).strip()
    if not main_text:
        return ""
    return f"description=<p>{main_text}</p>"


def extract_productstory(raw_desc):
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
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "other"):
        return ""
    return s


def first_nonblank(*values):
    for v in values:
        if _clean_field_value(v):
            return v
    return ""


def build_short_description(brand, color_name, gender, activity_group, collection,
                             material, material_local, upper_material, mid_sole_material,
                             outer_sole_material, shell_material, toe_type, heel_type,
                             fastener, fit, puma_technology, technology_purpose, style_number):
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
                        category_composite_key_col=None,
                        category_name_col=None,
                        size_chart_image_df=None,
                        size_chart_image_title_col=None, size_chart_image_url_col=None,
                        size_chart_image_style_col=None,
                        size_chart_image_composite_key_col=None,
                        size_chart_image_gender_article_key_col=None,
                        region="PH", marketplace="Lazada"):
    mc = dict(MASTER_COLS)
    if master_col_map:
        mc.update({k: v for k, v in master_col_map.items() if v})

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
        "composite_key": category_composite_key_col,
        "category_name": category_name_col if category_name_col else CATEGORY_SHEET_COLS["category_name"],
    }
    sci = {
        "title_keyword": size_chart_image_title_col if size_chart_image_title_col else SIZE_CHART_IMAGE_COLS["title_keyword"],
        "image_url": size_chart_image_url_col if size_chart_image_url_col else SIZE_CHART_IMAGE_COLS["image_url"],
        "style_no": size_chart_image_style_col,
        "composite_key": size_chart_image_composite_key_col,
        "gender_article_key": size_chart_image_gender_article_key_col,
    }

    # Mapping log/report data (per General Requirements): tracks per-row
    # outcomes for Category ID and Size Chart Image URL mapping so a clear
    # report can be shown after generation.
    mapping_log = {"category": [], "size_chart_image": [], "size_chart_template": []}

    currency_code = REGION_CURRENCY.get(region, "PHP")

    rows = []
    master_df = master_df.copy()

    def group_key(r):
        color_no = r.get(mc["color_no"], "")
        if color_no not in (None, "") and str(color_no).strip() not in ("", "nan"):
            return f"color__{color_no}"
        style = r.get(mc["style_no"], "")
        return f"style__{style}"

    master_df["_group_key"] = master_df.apply(group_key, axis=1)

    for group_key_val, group_df in master_df.groupby("_group_key", sort=False):
        first = group_df.iloc[0]
        ptype = first.get(mc["product_type"], "")
        footwear = is_footwear(ptype)

        gender_val = first.get(mc["gender"], "")
        # Search Color Name used in Title for EVERY division, with a blank-safe
        # fallback to Color Name (NOT a plain `or`, since pandas NaN is truthy).
        title_color_raw = first_nonblank(first.get(mc["search_color_name"], ""), first.get(mc["color_name"], ""))
        title = clean_title(
            first.get(mc["brand"], ""),
            gender_val,
            first.get(mc["title"], ""),
            title_color_raw,
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

        color_no_str = str(color_no_val).strip() if color_no_val not in (None, "") and str(color_no_val).strip().lower() != "nan" else ""
        model_value = color_no_str if color_no_str else str(style_number)

        # --- ALL THREE mappings (Category ID / Size Chart Image URL /
        # Template Attribute 1) now share ONE composite key, built from the
        # same 6 Master Sheet attributes, joined with "+" to match your
        # sheets' shared literal header:
        #   "Age Group+Gender+Article Group+Article Type+Activity Group+Product Division"
        # This is tried FIRST for every mapping. Never overwrites with a bad
        # guess -- stays blank if the key isn't found in a given sheet. ---
        shared_key_attrs = [
            first.get(mc["age_group"], ""),
            gender_val,
            first.get(mc["article_group"], ""),
            first.get(mc["article_type"], ""),
            first.get(mc["activity_group"], ""),
            ptype,
        ]
        shared_composite_key = build_composite_key(*shared_key_attrs)

        # --- 1. Category ID mapping ---
        category_id = match_category_id(
            title, category_df, cc["keyword"], cc["category_id"],
            composite_key=shared_composite_key, composite_key_col=cc["composite_key"],
            attribute_values=shared_key_attrs, name_col=cc["category_name"],
        )
        mapping_log["category"].append({
            "SKU/Model": model_value, "Key": shared_composite_key, "Matched": bool(category_id),
        })

        # --- 3. Size Chart Template mapping (Template Attribute 1) ---
        # Your actual sheet only has Gender_ArticleGroup (no 6-field composite
        # key column), so that's tried FIRST here; the shared composite key
        # is tried second in case a sheet with that column is used later.
        gender_article_key = build_gender_article_group_key(gender_val, first.get(mc["article_group"], ""))
        template_attr_1 = match_size_chart_template(
            gender_article_key, size_chart_template_df, sct["key"], sct["template_attribute_1"]
        )
        if not template_attr_1:
            template_attr_1 = match_size_chart_template(
                shared_composite_key, size_chart_template_df, sct["key"], sct["template_attribute_1"]
            )
        mapping_log["size_chart_template"].append({
            "SKU/Model": model_value, "Key": gender_article_key, "Matched": bool(template_attr_1),
        })

        # --- 2. Size Chart Image URL mapping ---
        # Same reasoning: Gender_ArticleGroup is your actual sheet's key
        # column, so it's tried FIRST (primary), with the shared composite
        # key, Style Number, and Title kept as further fallbacks.
        size_chart_image_url = match_size_chart_image(
            title, size_chart_image_df, sci["title_keyword"], sci["image_url"],
            style_number=style_number, style_col=sci["style_no"],
            composite_key=shared_composite_key, composite_key_col=sci["composite_key"],
            gender_article_key=gender_article_key, gender_article_key_col=sci["gender_article_key"],
        )
        mapping_log["size_chart_image"].append({
            "SKU/Model": model_value, "Key": gender_article_key, "Matched": bool(size_chart_image_url),
        })

        template_attr_2 = extract_description_main(raw_desc)
        template_attr_3 = extract_productstory(raw_desc)

        short_description = build_short_description(
            brand=_clean_field_value(first.get(mc["brand"], "")) or "PUMA",
            color_name=extract_search_color_name(title_color_raw),
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

        total_variation_count = len(group_df)

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

        parent_sku_value = model_value

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
        first_child_price = ""
        if child_records:
            first_rec = child_records[0]
            first_child_color_name = clean_color_name(first_rec.get(mc["color_name"], ""))
            first_child_formatted_size = format_size_value(first_rec.get(mc["uk_size"], ""), footwear)
            first_child_price = get_price(first_rec, price_col)

        parent_images = "; ".join(get_images_for_key(model_value, image_df, ic["sku"], ic["url_col"]))
        parent_row = {
            "Row Type": "Parent",
            **base_row,
            "SKU": parent_sku_value,
            "Seller SKU": parent_sku_value,
            "Parent SKU": "",
            "Total variation": total_variation_count,
            "Variation 1": "color_family",
            "Variation 2": "size",
            "Stock": 0,
            "RRP": first_child_price,
            "Images": parent_images,
            "Product Image URL(s)": parent_images,
            "Image URL": parent_images,
            "Product Specification 1": f"sku.color_family={first_child_color_name}",
            "Product Specification 2": f"sku.size={first_child_formatted_size}",
        }
        rows.append(parent_row)

        for rec in child_records:
            sku = rec.get(mc["sku"], "")
            color_name = clean_color_name(rec.get(mc["color_name"], ""))
            uk_size_raw = rec.get(mc["uk_size"], "")
            formatted_size = format_size_value(uk_size_raw, footwear)
            child_images = "; ".join(get_images_for_key(model_value, image_df, ic["sku"], ic["url_col"]))
            child_row = {
                "Row Type": "Child",
                **base_row,
                "Description": "",
                "SKU": sku,
                "Seller SKU": sku,
                "Parent SKU": parent_sku_value,
                "Total variation": "",
                "RRP": get_price(rec, price_col),
                "Variation 1": color_name,
                "Variation 2": formatted_size,
                "Product Specification 1": f"sku.color_family={color_name}",
                "Product Specification 2": f"sku.size={formatted_size}",
                "Stock": 0,
                "Images": child_images,
                "Product Image URL(s)": child_images,
                "Image URL": child_images,
            }
            rows.append(child_row)

    out_df = pd.DataFrame(rows)

    parent_count = int((out_df["Row Type"] == "Parent").sum()) if "Row Type" in out_df.columns else 0
    child_count = int((out_df["Row Type"] == "Child").sum()) if "Row Type" in out_df.columns else 0

    # Match Sample Upload Format columns to computed columns CASE-INSENSITIVELY
    # and with surrounding whitespace ignored. A single-letter case mismatch
    # (e.g. sample says "Size chart Image URL" but the code computed "Size
    # Chart Image URL") would otherwise silently produce a blank column even
    # though the data was computed correctly -- this prevents that class of
    # bug for every column, not just one.
    out_cols_by_norm = {str(c).strip().lower(): c for c in out_df.columns}
    for col in output_columns:
        if col in out_df.columns:
            continue
        norm = str(col).strip().lower()
        if norm in out_cols_by_norm:
            out_df[col] = out_df[out_cols_by_norm[norm]]
        else:
            out_df[col] = ""
    out_df = out_df[output_columns]

    resolved_cols = {"sci": sci, "sct": sct, "cc": cc}
    return out_df, parent_count, child_count, mapping_log, resolved_cols


# ======================================================================================
# STREAMLIT UI
# ======================================================================================

st.set_page_config(page_title="Marketplace Upload Sheet Generator", layout="wide")
st.title("🛒 Marketplace Bulk Upload Sheet Generator")

st.markdown(
    """
Upload your source sheets below. **Master Sheet column mapping is done in the UI**
(see the "Map Master Sheet columns" section once you upload it).

**Updates in this version:**
- Title now shows the Search Color Name in **parentheses**, e.g. `( White)`.
- **Size Chart Image URL** is now matched strictly against the generated **Title**
  (normalized keyword match), instead of loosely matching arbitrary keywords.
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
        "Size Chart Sheet (.xlsx/.csv) — provides the Size Chart Image URL, matched by Title",
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


price_col = MASTER_COLS["price"]
master_col_map = {}

if master_file is not None:
    _master_preview_df = load_any(master_file)
    master_file.seek(0)
    master_cols_available = list(_master_preview_df.columns)

    if not master_cols_available:
        st.error(
            "⚠️ The uploaded Master Input Sheet has NO columns/headers -- it appears "
            "to be empty. The Master Sheet mapping section can't populate any dropdowns "
            "until you upload a file that actually has a header row and data. Please "
            "check the file and re-upload."
        )

    st.markdown("#### 📌 Master Sheet — Column Mapping")
    st.caption(
        "Map every field to the matching column in your uploaded Master Sheet."
    )

    # Split fields into two groups: REQUIRED fields (always shown, need your
    # attention) vs OPTIONAL Short-Description-only fields (auto-detected by
    # keyword matching -- same as the Image Sheet's column guessing -- and
    # tucked into a collapsed section so they don't clutter the main view.
    # The auto-guess still runs and populates master_col_map even if you
    # never open that section, so the result is identical either way.
    required_fields = [(k, label, req) for (k, label, req) in MASTER_COLS_FIELDS if req]
    optional_fields = [(k, label, req) for (k, label, req) in MASTER_COLS_FIELDS if not req]

    with st.expander("Map Master Sheet columns", expanded=True):
        none_option = "— not in my sheet —"
        options_with_none = [none_option] + master_cols_available

        mcol1, mcol2 = st.columns(2)
        for i, (field_key, field_label, required) in enumerate(required_fields):
            default_header = MASTER_COLS[field_key]
            default_idx = (
                options_with_none.index(default_header) if default_header in options_with_none else 0
            )
            target_col = mcol1 if i % 2 == 0 else mcol2
            with target_col:
                chosen = st.selectbox(
                    f"{field_label} *",
                    options=options_with_none,
                    index=default_idx,
                    key=f"master_col_map_{field_key}",
                )
                master_col_map[field_key] = "" if chosen == none_option else chosen

        # Optional Short-Description fields are auto-detected by keyword
        # matching (same approach as the Image Sheet's column guessing) and
        # tucked into a collapsed section below so they don't clutter the
        # main view -- the auto-guess becomes each selectbox's default value,
        # and still applies even if you never open the section.
        with st.expander("Optional: Short Description detail fields (auto-detected — click to override)", expanded=False):
            ocol1, ocol2 = st.columns(2)
            for i, (field_key, field_label, required) in enumerate(optional_fields):
                default_header = MASTER_COLS[field_key]
                base_keyword = field_label.split(" (")[0].strip().lower()
                auto_guess = guess_column_or_none(
                    master_cols_available, default_header, keywords=[base_keyword]
                )
                # No match found -> default to "not in my sheet" instead of
                # silently guessing an unrelated column.
                default_idx = (
                    options_with_none.index(auto_guess) if auto_guess and auto_guess in options_with_none else 0
                )
                target_col = ocol1 if i % 2 == 0 else ocol2
                with target_col:
                    chosen = st.selectbox(
                        field_label,
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
        )

size_chart_key_col = SIZE_CHART_TEMPLATE_COLS["key"]
size_chart_attr_col = SIZE_CHART_TEMPLATE_COLS["template_attribute_1"]

if size_chart_template_file is not None:
    _sct_preview_df = load_any(size_chart_template_file)
    size_chart_template_file.seek(0)
    sct_cols_available = list(_sct_preview_df.columns)

    st.markdown("#### 📌 Size Chart Template Sheet — Column Selection")
    sc1, sc2 = st.columns(2)
    with sc1:
        default_key_guess = (
            guess_composite_key_column(sct_cols_available)
            or guess_gender_article_group_column(sct_cols_available)
        )
        default_key_idx = (
            sct_cols_available.index(default_key_guess) if default_key_guess in sct_cols_available else 0
        )
        size_chart_key_col = st.selectbox(
            "Size chart Name",
            options=sct_cols_available,
            index=default_key_idx,
            key="size_chart_key_col_select_v5",
        )
    with sc2:
        default_attr_guess = guess_column_or_none(
            sct_cols_available, size_chart_attr_col, keywords=["size chart template", "sizechart", "template"]
        ) or size_chart_attr_col
        default_attr_idx = (
            sct_cols_available.index(default_attr_guess) if default_attr_guess in sct_cols_available else 0
        )
        size_chart_attr_col = st.selectbox(
            "Size chart Template",
            options=sct_cols_available,
            index=default_attr_idx,
            key="size_chart_attr_col_select_v3",
        )

size_chart_image_title_col = SIZE_CHART_IMAGE_COLS["title_keyword"]
size_chart_image_url_col = SIZE_CHART_IMAGE_COLS["image_url"]
size_chart_image_style_col = None

if size_chart_image_file is not None:
    _sci_preview_df = load_any(size_chart_image_file)
    size_chart_image_file.seek(0)
    sci_cols_available = list(_sci_preview_df.columns)

    st.markdown("#### 📌 Size Chart Sheet — Column Selection")

    sci1, sci2 = st.columns(2)
    with sci1:
        default_sci_key_guess = (
            guess_column_or_none(sci_cols_available, "Gender_ArticleGroup", keywords=["gender_articlegroup"])
            or guess_composite_key_column(sci_cols_available)
            or guess_gender_article_group_column(sci_cols_available)
        )
        default_sci_key_idx = (
            sci_cols_available.index(default_sci_key_guess) if default_sci_key_guess in sci_cols_available else 0
        )
        _sci_key_value = st.selectbox(
            "Size Chart Template Name",
            options=sci_cols_available,
            index=default_sci_key_idx,
            key="size_chart_image_key_col_select_v5",
        )
    with sci2:
        default_sci_url_guess = (
            guess_column_or_none(sci_cols_available, "Size chart link", keywords=["size chart link"])
            or guess_column_or_none(sci_cols_available, size_chart_image_url_col, keywords=["link", "url", "image"])
            or size_chart_image_url_col
        )
        default_sci_url_idx = (
            sci_cols_available.index(default_sci_url_guess) if default_sci_url_guess in sci_cols_available else 0
        )
        size_chart_image_url_col = st.selectbox(
            "Size chart link",
            options=sci_cols_available,
            index=default_sci_url_idx,
            key="size_chart_image_url_col_select_v3",
        )

    # Feed the single chosen key column into BOTH match strategies -- whichever
    # one it actually is (Gender_ArticleGroup format or composite format),
    # the matcher tries it as both, and only one will ever find a hit.
    size_chart_image_gender_article_key_col = _sci_key_value
    size_chart_image_composite_key_col = _sci_key_value
    size_chart_image_title_col = None
    size_chart_image_style_col = None
else:
    size_chart_image_style_col = None
    size_chart_image_composite_key_col = None
    size_chart_image_gender_article_key_col = None

category_keyword_col = CATEGORY_SHEET_COLS["keyword"]
category_id_col = CATEGORY_SHEET_COLS["category_id"]
category_composite_key_col = None
category_name_col = CATEGORY_SHEET_COLS["category_name"]

if category_file is not None:
    _cat_preview_df = load_any(category_file)
    category_file.seek(0)
    cat_cols_available = list(_cat_preview_df.columns)

    st.markdown("#### 📌 Category Sheet — Column Selection")
    st.caption(
        "PRIMARY match: composite key column, joined from Age Group+Gender+Article "
        "Group+Article Type+Activity Group+Product Division. If your sheet doesn't "
        "have this column, the Category Name column is scored against all available "
        "Master Sheet attributes instead (breadcrumb-style names). Title Keyword is "
        "a last-resort fallback."
    )
    cat_none_option = "— not in my sheet / skip —"
    cat_key_options = [cat_none_option] + cat_cols_available
    default_cat_key_guess = guess_composite_key_column(cat_cols_available)
    default_cat_key_idx = (
        cat_key_options.index(default_cat_key_guess) if default_cat_key_guess in cat_key_options else 0
    )
    cat_key_label = (
        f"Composite key column (detected in this sheet: \"{default_cat_key_guess}\")"
        if default_cat_key_guess else "Composite key column (none detected in this sheet)"
    )
    _cat_key_choice = st.selectbox(
        cat_key_label,
        options=cat_key_options,
        index=default_cat_key_idx,
        key="category_composite_key_col_select_v3",
    )
    category_composite_key_col = None if _cat_key_choice == cat_none_option else _cat_key_choice

    cc1, cc2 = st.columns(2)
    with cc1:
        default_name_guess = guess_column_or_none(
            cat_cols_available, category_name_col, keywords=["category name", "name"]
        ) or category_name_col
        default_name_idx = (
            cat_cols_available.index(default_name_guess) if default_name_guess in cat_cols_available else 0
        )
        category_name_col = st.selectbox(
            "Category Name column (attribute-based best-match)",
            options=cat_cols_available,
            index=default_name_idx,
            key="category_name_col_select",
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

    cc3, cc4 = st.columns(2)
    with cc3:
        cat_kw_none_option = "— not in my sheet / skip —"
        cat_kw_options = [cat_kw_none_option] + cat_cols_available
        default_kw_idx = (
            cat_kw_options.index(category_keyword_col) if category_keyword_col in cat_kw_options else 0
        )
        _cat_kw_choice = st.selectbox(
            "Title Keyword column (optional last-resort fallback)",
            options=cat_kw_options,
            index=default_kw_idx,
            key="category_keyword_col_select",
        )
        category_keyword_col = "" if _cat_kw_choice == cat_kw_none_option else _cat_kw_choice

image_sku_col = IMAGE_SHEET_COLS["sku"]
image_url_col = IMAGE_SHEET_COLS["url_col"]

if image_file is not None:
    _img_preview_df = load_any(image_file)
    image_file.seek(0)
    img_cols_available = list(_img_preview_df.columns)

    st.markdown("#### 📌 Image Sheet — Column Selection")
    st.caption(
        "Your Image Sheet is a long/tall list — one row per image, with the SAME "
        "Color Number repeating across multiple rows."
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
        if image_file is None:
            st.warning(
                "⚠️ No Image Sheet uploaded — every 'Product Image URL(s)' value will be "
                "blank in the output."
            )
        if size_chart_image_file is None:
            st.warning(
                "⚠️ No Size Chart Sheet uploaded — 'Size chart Image URL' will be blank "
                "for every row."
            )
        if size_chart_template_file is None:
            st.warning(
                "⚠️ No Size Chart Template Sheet uploaded — 'Template Attribute 1' will be "
                "blank for every row."
            )
        if category_file is None:
            st.warning(
                "⚠️ No Category Sheet uploaded — 'Category ID' will be blank for every row."
            )

        with st.spinner("Processing..."):
            master_df = load_any(master_file)
            image_df = load_any(image_file)
            size_chart_template_df = load_any(size_chart_template_file)
            size_chart_image_df = load_any(size_chart_image_file)
            category_df = load_any(category_file)
            sample_df = load_any(sample_file)

            output_columns = list(sample_df.columns)

            try:
                result_df, parent_count, child_count, mapping_log, resolved_cols = build_upload_sheet(
                    master_df, image_df, size_chart_template_df, category_df, output_columns,
                    price_col=price_col,
                    master_col_map=master_col_map,
                    image_sku_col=image_sku_col,
                    image_url_col=image_url_col,
                    size_chart_key_col=size_chart_key_col,
                    size_chart_attr_col=size_chart_attr_col,
                    category_keyword_col=category_keyword_col,
                    category_id_col=category_id_col,
                    category_composite_key_col=category_composite_key_col,
                    category_name_col=category_name_col,
                    size_chart_image_df=size_chart_image_df,
                    size_chart_image_title_col=size_chart_image_title_col,
                    size_chart_image_url_col=size_chart_image_url_col,
                    size_chart_image_style_col=size_chart_image_style_col,
                    size_chart_image_composite_key_col=size_chart_image_composite_key_col,
                    size_chart_image_gender_article_key_col=size_chart_image_gender_article_key_col,
                    region=selected_region,
                    marketplace=selected_marketplace,
                )
            except KeyError as e:
                st.error(
                    f"Column mapping mismatch: {e}. "
                    "Please adjust the column mappings above to match your actual sheet's headers, then rerun."
                )
                st.stop()

        st.success(f"Generated {len(result_df)} rows ({parent_count} parent, {child_count} child).")

        # --- Mapping log/report (per General Requirements): shows successfully
        # mapped rows, unmatched rows, and missing mapping combinations for
        # each of the three mappings, without needing to inspect the full sheet.
        # Auto-expands and shows real diagnostics (sheet uploaded? actual key
        # values found in the sheet vs what was attempted) whenever a mapping
        # has ZERO matches, so a "why is this blank" question is answerable
        # directly from this report instead of guessing. ---
        mapping_defs = [
            ("Category ID", "category", category_df, resolved_cols["cc"]["composite_key"] or resolved_cols["cc"]["category_name"]),
            ("Size Chart Image URL", "size_chart_image", size_chart_image_df, resolved_cols["sci"]["gender_article_key"] or resolved_cols["sci"]["composite_key"]),
            ("Template Attribute 1 (Size Chart Template)", "size_chart_template", size_chart_template_df, resolved_cols["sct"]["key"]),
        ]
        any_zero_match = any(
            pd.DataFrame(mapping_log[key])["Matched"].sum() == 0
            for _, key, _, _ in mapping_defs
            if not pd.DataFrame(mapping_log[key]).empty
        )
        with st.expander(
            "📋 Mapping Report (Category ID / Size Chart Image URL / Template Attribute 1)",
            expanded=any_zero_match,
        ):
            for label, key, sheet_df, sheet_key_col in mapping_defs:
                log_df = pd.DataFrame(mapping_log[key])
                if log_df.empty:
                    continue
                matched_count = int(log_df["Matched"].sum())
                total_count = len(log_df)
                unmatched_df = log_df[~log_df["Matched"]]
                st.markdown(f"**{label}:** {matched_count} / {total_count} groups matched")

                if sheet_df is None:
                    st.error(f"⚠️ No sheet was uploaded for {label} -- this is why it's entirely blank. Upload the sheet above.")
                    continue

                if not unmatched_df.empty:
                    missing_keys = sorted(unmatched_df["Key"].unique().tolist())
                    st.caption(f"{len(unmatched_df)} unmatched row(s). Keys attempted from your Master Sheet:")
                    st.dataframe(pd.DataFrame({"Key attempted (from Master Sheet)": missing_keys}), use_container_width=True)

                    if matched_count == 0 and sheet_key_col and sheet_key_col in sheet_df.columns:
                        sheet_sample_keys = sorted(
                            sheet_df[sheet_key_col].astype(str).dropna().unique().tolist()
                        )[:15]
                        st.caption(f"Actual values found in your sheet's \"{sheet_key_col}\" column (compare against the attempted keys above):")
                        st.dataframe(pd.DataFrame({f'Values in "{sheet_key_col}"': sheet_sample_keys}), use_container_width=True)
                        st.info(
                            "If NONE of the attempted keys appear (even loosely) in the actual sheet values above, "
                            "the Master Sheet's Gender/Article Group/etc. column mapping is likely pointing at the "
                            "wrong column, or producing blank values -- double-check the 'Map Master Sheet columns' "
                            "section further up."
                        )
                    elif matched_count == 0 and (not sheet_key_col or sheet_key_col not in sheet_df.columns):
                        st.error(
                            f"⚠️ The key column selected for this sheet (\"{sheet_key_col}\") doesn't actually exist "
                            "in the uploaded file -- please re-check the column dropdown above."
                        )

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
