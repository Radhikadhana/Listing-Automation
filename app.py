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

SIZE_CHART_IMAGE_COLS = {
    "title_keyword": "Title",
    "image_url": "Size Chart Image URL",
    "style_no": "Style Number",
}

SIZE_CHART_TEMPLATE_COLS = {
    "key": "Size Chart Key",
    "template_attribute_1": "Template Attribute 1",
}

CATEGORY_SHEET_COLS = {
    "keyword": "Title Keyword",
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


def normalize_match_text(s):
    if s is None:
        return ""
    s = str(s).replace("™", "").replace("®", "")
    s = re.sub(r"[^A-Za-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


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
    if size_chart_image_df is None or size_chart_image_df.empty:
        return ""
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
    if is_footwear_row:
        return f"UK:{s}"
    return f"Int:{s}"


def build_size_chart_key(gender, article_group):
    parts = [gender, article_group]
    return "-".join(str(p).strip() if p is not None else "" for p in parts)


def match_size_chart_template(size_chart_key, size_chart_template_df, key_col, attr_col):
    if size_chart_template_df is None or size_chart_template_df.empty:
        return ""
    if key_col not in size_chart_template_df.columns or attr_col not in size_chart_template_df.columns:
        return ""
    match = size_chart_template_df[
        size_chart_template_df[key_col].astype(str).str.strip() == str(size_chart_key).strip()
    ]
    if match.empty:
        return ""
    raw_val = match.iloc[0].get(attr_col, "")
    val = _clean_field_value(raw_val) if raw_val is not None else ""
    return f"sizechart={val}" if val else ""


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
                        size_chart_image_df=None,
                        size_chart_image_title_col=None, size_chart_image_url_col=None,
                        size_chart_image_style_col=None,
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
    }
    sci = {
        "title_keyword": size_chart_image_title_col if size_chart_image_title_col else SIZE_CHART_IMAGE_COLS["title_keyword"],
        "image_url": size_chart_image_url_col if size_chart_image_url_col else SIZE_CHART_IMAGE_COLS["image_url"],
        "style_no": size_chart_image_style_col,
    }

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

        category_id = match_category_id(title, category_df, cc["keyword"], cc["category_id"])

        size_chart_key = build_size_chart_key(gender_val, first.get(mc["article_group"], ""))
        template_attr_1 = match_size_chart_template(
            size_chart_key, size_chart_template_df, sct["key"], sct["template_attribute_1"]
        )

        # --- Size Chart Image URL: now matched strictly by the generated TITLE
        # (normalized keyword-in-title match), per updated spec. Style Number
        # exact match is still tried first when available, as a more reliable
        # anchor before falling back to the title-based match. ---
        size_chart_image_url = match_size_chart_image(
            title, size_chart_image_df, sci["title_keyword"], sci["image_url"],
            style_number=style_number, style_col=sci["style_no"],
        )

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
            "Parent SKU": "",
            "Total variation": total_variation_count,
            "Variation 1": "color_family",
            "Variation 2": "size",
            "Stock": 0,
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

    st.markdown("#### 📌 Master Sheet — Column Mapping")
    st.caption(
        "Map every field to the matching column in your uploaded Master Sheet."
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
        default_key_idx = (
            sct_cols_available.index(size_chart_key_col) if size_chart_key_col in sct_cols_available else 0
        )
        size_chart_key_col = st.selectbox(
            "Lookup key column (Gender-Article Group)",
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

size_chart_image_title_col = SIZE_CHART_IMAGE_COLS["title_keyword"]
size_chart_image_url_col = SIZE_CHART_IMAGE_COLS["image_url"]

if size_chart_image_file is not None:
    _sci_preview_df = load_any(size_chart_image_file)
    size_chart_image_file.seek(0)
    sci_cols_available = list(_sci_preview_df.columns)

    st.markdown("#### 📌 Size Chart Sheet — Column Selection")
    st.caption(
        "The Title column here is matched (normalized keyword match) against each "
        "product's generated Title — the longest matching row wins. Its Image URL "
        "fills the 'Size Chart Image URL' output column."
    )
    sci1, sci2 = st.columns(2)
    with sci1:
        default_sci_title_idx = (
            sci_cols_available.index(size_chart_image_title_col) if size_chart_image_title_col in sci_cols_available else 0
        )
        size_chart_image_title_col = st.selectbox(
            "Title column (matched against generated product Title)",
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
        "Optional: if your Size Chart Sheet also has a Style Number column, mapping "
        "it here gives an exact match tried BEFORE the Title match above."
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
                    "Please adjust the column mappings above to match your actual sheet's headers, then rerun."
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
