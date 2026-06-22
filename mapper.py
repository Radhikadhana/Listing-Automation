"""
Core logic that converts a Puma-style "Input" product sheet into a
Lazada SG marketplace upload file, using the official Header column order
and matching each product to a Category ID from the Lazada category list.
"""

import re
import pandas as pd

HEADER_COLUMNS = [
    "Graas SKU", "Status", "Remarks", "Seller SKU", "Product Name",
    "Product Description 1", "Product Description 2", "Product Description 3",
    "Total variation", "Variation 1", "Variation 2", "Variation 3",
    "Short Description", "SRP", "Sale Start Date", "Sale End Date", "RRP",
    "Currency Code", "Quantity", "Product Image URL(s)", "Category ID",
    "Tax Class", "Brand", "Model", "Warranty Type", "Package Weight (kg)",
    "Package Height(cm)", "Package Length(cm)", "Package Width(cm)",
    "What's in the Box", "Size chart Image URL",
] + [f"Product Specification {i}" for i in range(1, 26)] + [
    f"Template Attribute {i}" for i in range(1, 6)
] + ["Post As Non Variant"]

# Input columns (in order) feeding Product Specification 1-25.
SPEC_SOURCE_COLUMNS = [
    "Material (English)", "Type of Material ", "Main Material of Shell (English)",
    "Heel Type", "Puma Technology", "Technology Purpose", "Fastener", "Fit",
    "Notes (SEA)", "Body Style 1", "Body Style 2", "Volume", "Franchise",
    "Pattern", "Mid Sole (English)", "Upper (English)", "Outer Sole (English)",
    "Profile", "Collection", "Dimensions Accessories", "Country of Origin",
    "Search Color Name (English)", "RBU", "Business Segment", "Style Name",
]

TEMPLATE_ATTR_SOURCE_COLUMNS = [
    "Age Group", "Gender", "Article Group", "Article Type", "Activity Group",
]

DEFAULT_CURRENCY = "SGD"

_PLACEHOLDER_VALUES = {"none", "0", "nan", ""}


def _clean(value):
    """Blank out Puma's placeholder values ('None', '0', NaN) used for unset fields."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in _PLACEHOLDER_VALUES:
        return ""
    return text


_WORD_RE = re.compile(r"[A-Za-z]+")


def _tokenize(text):
    return set(w.lower() for w in _WORD_RE.findall(str(text)) if len(w) > 2)


import re as _re

_FEMALE_RE = _re.compile(r"\b(women|girl)\b")
_MALE_RE = _re.compile(r"\b(men|boy)\b")
_KIDS_TERMS = ("kid", "girl", "boy", "baby", "infant", "toddler")

# Sportswear/apparel brand products should only ever land in these top-level
# branches. Without this guard, generic word overlap (e.g. "boot", "training",
# "auto") can pull a shoe or cap into Automotive or Pet Supplies categories.
_RELEVANT_ROOTS = {
    "sports shoes and clothing", "sports & outdoors activities equipment",
    "women's shoes", "men's shoes", "women's clothing", "men's clothing",
    "kids' fashion", "fashion accessories", "bags and travel",
    "lingerie, sleep, lounge & thermal wear",
}


def build_category_index(category_df):
    """Pre-tokenize every category path once for fast scoring."""
    records = []
    for _, row in category_df.iterrows():
        cat_id = row["Category ID"]
        cat_name = row["Category Name"]
        lower_name = cat_name.lower()
        root = lower_name.split(":")[0].strip()
        if root not in _RELEVANT_ROOTS:
            continue
        tokens = _tokenize(cat_name.replace(":", " "))
        is_sports = "sport" in lower_name
        is_fashion = "fashion" in lower_name
        records.append((cat_id, cat_name, lower_name, tokens, is_sports, is_fashion))
    return records


def _score(cat_tokens, lower_name, article_type, article_group, activity_group,
           product_division, gender, age_group):
    article_type_tok = _tokenize(article_type)
    article_group_tok = _tokenize(article_group)
    activity_tok = _tokenize(activity_group)
    division_tok = _tokenize(product_division)

    score = 0.0
    score += 5 * len(article_type_tok & cat_tokens)
    score += 3 * len(article_group_tok & cat_tokens)
    score += 2 * len(division_tok & cat_tokens)
    score += 1 * len(activity_tok & cat_tokens)

    if article_type and " " in article_type and article_type in lower_name:
        score += 4
    if article_group and " " in article_group and article_group in lower_name:
        score += 2

    if gender == "female":
        if _FEMALE_RE.search(lower_name):
            score += 4
        elif _MALE_RE.search(lower_name):
            score -= 4
    elif gender == "male":
        if _MALE_RE.search(lower_name):
            score += 4
        elif _FEMALE_RE.search(lower_name):
            score -= 4

    is_kids_age = age_group in ("kids", "youth", "infants", "infant", "toddler", "baby")
    has_kids_term = any(t in lower_name for t in _KIDS_TERMS)
    if is_kids_age and has_kids_term:
        score += 6
    elif (not is_kids_age) and has_kids_term:
        score -= 10

    return score


def match_category(row, category_index):
    """Pick the best Category ID for a product row.

    Strategy: build a search string from the row's classification fields,
    score it against every category path (token overlap plus boosts for
    verbatim phrase matches and gender alignment), strongly preferring
    paths that contain 'Sports'; fall back to 'Fashion' paths, then to
    the best match overall.
    """
    article_type = _clean(row.get("Article Type", "")).lower()
    article_group = _clean(row.get("Article Group", "")).lower()
    activity_group = _clean(row.get("Activity Group", "")).lower()
    gender = _clean(row.get("Gender", "")).lower()
    age_group = _clean(row.get("Age Group", "")).lower()
    product_division = _clean(row.get("Product Division", "")).lower()

    best_sports, best_fashion, best_any = None, None, None

    for cat_id, cat_name, lower_name, cat_tokens, is_sports, is_fashion in category_index:
        s = _score(cat_tokens, lower_name, article_type, article_group,
                   activity_group, product_division, gender, age_group)
        if s <= 0:
            continue
        if best_any is None or s > best_any[0]:
            best_any = (s, cat_id, cat_name)
        if is_sports and (best_sports is None or s > best_sports[0]):
            best_sports = (s, cat_id, cat_name)
        if is_fashion and (best_fashion is None or s > best_fashion[0]):
            best_fashion = (s, cat_id, cat_name)

    chosen = best_any
    if best_sports is not None and best_any is not None and best_sports[0] >= best_any[0] * 0.75:
        chosen = best_sports
    elif chosen is None:
        chosen = best_fashion
    if chosen is None:
        return "", ""
    _, cat_id, cat_name = chosen
    return cat_id, cat_name


def convert(input_df, category_df):
    """Convert the raw Input sheet into a DataFrame matching HEADER_COLUMNS.

    Returns (output_df, category_match_log_df).
    """
    category_index = build_category_index(category_df)

    variant_counts = input_df.groupby("Style No")["Style No"].transform("count")

    rows = []
    log_rows = []

    for idx, in_row in input_df.iterrows():
        cat_id, cat_name = match_category(in_row, category_index)

        price = _clean(in_row.get("Price", ""))
        total_variation = int(variant_counts.loc[idx])

        out = {
            "Graas SKU": "",
            "Status": "",
            "Remarks": "",
            "Seller SKU": _clean(in_row.get("EAN", "")),
            "Product Name": _clean(in_row.get("Regional Display Name (English)", ""))
                             or _clean(in_row.get("Style Name", "")),
            "Product Description 1": _clean(in_row.get("Short Description (English)", "")),
            "Product Description 2": _clean(in_row.get("Long Description (English)", "")),
            "Product Description 3": "",
            "Total variation": total_variation,
            "Variation 1": _clean(in_row.get("Color Name", "")),
            "Variation 2": _clean(in_row.get("Size No.", "")),
            "Variation 3": "",
            "Short Description": _clean(in_row.get("Short Description (English)", "")),
            "SRP": price,
            "Sale Start Date": "",
            "Sale End Date": "",
            "RRP": price,
            "Currency Code": DEFAULT_CURRENCY,
            "Quantity": "",
            "Product Image URL(s)": "",
            "Category ID": cat_id,
            "Tax Class": "",
            "Brand": _clean(in_row.get("Brand", "")),
            "Model": _clean(in_row.get("Style No", "")),
            "Warranty Type": "",
            "Package Weight (kg)": _clean(in_row.get("Product Wt (SEA,Metric)", "")),
            "Package Height(cm)": _clean(in_row.get("Product Ht (SEA,Metric)", "")),
            "Package Length(cm)": _clean(in_row.get("Product Len (SEA,Metric)", "")),
            "Package Width(cm)": _clean(in_row.get("Product Wd (SEA,Metric)", "")),
            "What's in the Box": "",
            "Size chart Image URL": "",
            "Post As Non Variant": "No" if total_variation > 1 else "Yes",
        }

        for i, src_col in enumerate(SPEC_SOURCE_COLUMNS, start=1):
            out[f"Product Specification {i}"] = _clean(in_row.get(src_col, ""))

        for i, src_col in enumerate(TEMPLATE_ATTR_SOURCE_COLUMNS, start=1):
            out[f"Template Attribute {i}"] = _clean(in_row.get(src_col, ""))

        rows.append(out)
        log_rows.append({
            "Style No": in_row.get("Style No", ""),
            "Color No": in_row.get("Color No", ""),
            "Matched Category ID": cat_id,
            "Matched Category Name": cat_name,
        })

    output_df = pd.DataFrame(rows, columns=HEADER_COLUMNS)
    log_df = pd.DataFrame(log_rows)
    return output_df, log_df
