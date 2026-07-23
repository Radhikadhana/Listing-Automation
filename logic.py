"""
Logic module for Product Feed Generator / Zecom Tracker processing.
- Preserves original structure while fixing column mapping bugs.
- Handles empty/missing Graas SKU gracefully.
- Parent Row: variation1 = "color_family", variation2 = "size", noOfVariants = count.
- Variant Row: variation1 = Color Name (Col 9), variation2 = Size UK (Col 22).
- Sorts child variants sequentially by size order (Alpha/Numeric).
"""

from openpyxl import Workbook, load_workbook
from openpyxl.utils import column_index_from_string
import io

# Standard clothing size order for sorting
SIZE_ORDER = [
    "3XS", "XXXS", "XXS", "XS", "S", "S/M", "M", "M/L", "L", "L/XL",
    "XL", "XXL", "XXXL", "3XL", "4XL", "5XL", "6XL", "1-2Y", "2-3Y",
    "3-4Y", "4-5Y", "5-6Y", "6-7Y", "7-8Y", "8-9Y", "9-10Y", "10-11Y",
    "11-12Y", "12-13Y", "13-14Y", "14-15Y", "15-16Y", "6Y", "8Y", "10Y",
    "12Y", "14Y", "16Y", "18Y", "20Y", "OSFA", "ONE SIZE", "UA", "MINI",
    "KIDS", "ADULT", "YOUTH"
]


class ConversionError(Exception):
    """Raised for issues that prevent proper generation of the Output sheet."""
    pass


HEADINGS = [
    "SKU", "status", "errorDetails", "customSKU", "itemTitle", "itemDescription1",
    "itemDescription2", "itemDescription3", "noOfVariants", "variation1",
    "variation2", "variation3", "shortDescription", "salePrice", "saleStartDate",
    "saleEndDate", "itemAmount", "currencyCode", "noOfItem", "imageURI",
    "categoryID", "taxClass", "brand", "model", "warrantyType",
    "packageWeight(kg)", "packageHeight(cm)", "packageLength(cm)",
    "packageWidth(cm)", "packageContent", "itemSpecifics1", "itemSpecifics2",
    "itemSpecifics3", "itemSpecifics4", "itemSpecifics5", "itemSpecifics6",
    "itemSpecifics7", "itemSpecifics8", "itemSpecifics9", "itemSpecifics10",
    "itemSpecifics11", "itemSpecifics12", "itemSpecifics13", "itemSpecifics14",
    "itemSpecifics15", "itemSpecifics16", "itemSpecifics17", "itemSpecifics18",
    "itemSpecifics19", "itemSpecifics20", "itemSpecifics21", "itemSpecifics22",
    "itemSpecifics23", "itemSpecifics24", "itemSpecifics25", "templateAttribute1",
    "templateAttribute2", "templateAttribute3", "templateAttribute4",
    "templateAttribute5", "postAsNonVariant",
]


def val(ws, row, col):
    v = ws.cell(row=row, column=col).value
    return "" if v is None else v


def s(v):
    return "" if v is None else str(v)


def replace_first(text, old, new):
    return s(text).replace(old, new, 1)


def is_not_number(v):
    try:
        float(s(v).strip())
        return False
    except (ValueError, TypeError):
        return True


def parse_column_setting(ws, col_setting):
    if not col_setting:
        return 4

    col_str = str(col_setting).strip()

    if col_str.isalpha():
        try:
            return column_index_from_string(col_str.upper())
        except ValueError:
            pass

    if col_str.isdigit():
        return int(col_str)

    for c in range(1, ws.max_column + 1):
        if str(val(ws, 1, c)).strip().lower() == col_str.lower():
            return c

    return 4


class OutputSheet:
    def __init__(self):
        self.rows = {}
        self.max_col = 0
        self.max_row = 0

    def set_value(self, row, col, value):
        if col is None or col < 1:
            return
        self.rows.setdefault(row, {})[col] = value
        self.max_row = max(self.max_row, row)
        self.max_col = max(self.max_col, col)

    def to_workbook(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Output"
        for r in range(1, self.max_row + 1):
            for c in range(1, self.max_col + 1):
                v = self.rows.get(r, {}).get(c)
                if v is not None and v != "":
                    ws.cell(row=r, column=c, value=v)
        return wb


def create_heading_for_target_sheet(main: OutputSheet, custom_headings=None):
    headings = custom_headings if custom_headings else HEADINGS
    for i, h in enumerate(headings):
        main.set_value(1, i + 1, h)


def replace_spl_character(value):
    value = s(value)
    pairs = [
        ("â€œ", "\u201c"), ("â€", "\u201d"), ("â€˜", "\u2018"), ("â€™", "\u2019"),
        ("â€”", "\u2013"), ("â€“", "\u2014"), ("â€•", "-"), ("â€¦", "\u2026"),
        ("Ã˜", "\u00d8"), ("Ã‚Â®", "\u00ae"), ("Â³", "\u00b3"), ("Â®", "\u00ae"),
    ]
    for old, new in pairs:
        value = replace_first(value, old, new)
    return value


def remove_duplicates(title):
    parts = s(title).split(" ")
    result = []
    for p in parts:
        if p not in result:
            result.append(p)
    return " ".join(result)


def form_title(brand, new_regional_display_name, activity_group, article_type, gender, search_color_name, products_division):
    brand, new_regional_display_name, search_color_name = s(brand), s(new_regional_display_name), s(search_color_name)
    title = "[NEW] " + (replace_first(brand, "Licence", "PUMA") if "Licence" in brand else brand)

    if gender not in (None, "") and gender not in title and gender == "Unisex":
        title += " " + gender

    if new_regional_display_name not in title:
        if "Trainers" in new_regional_display_name or "Trainer" in new_regional_display_name:
            title += " " + replace_first(replace_first(new_regional_display_name, "Trainers", "Shoes"), "Trainer", "Shoes")
        elif "Sandals" in new_regional_display_name:
            title += " " + replace_first(new_regional_display_name, "Sandals", "Sports Sandals")
        elif "Slides" in new_regional_display_name:
            title += " " + replace_first(new_regional_display_name, "Slides", "Slides Slippers")
        else:
            title += " " + new_regional_display_name

    if products_division == "Footwear" and search_color_name not in title:
        title += " (" + search_color_name + ") "

    return title


def get_item_title(regional_display_name, brand, gender, activity_group, article_type, search_color_name, products_division):
    regional_display_name, search_color_name = s(regional_display_name), s(search_color_name)
    new_regional_display_name = replace_first(regional_display_name, "\u2019s", "'s\u2122") if "\u2019s" in regional_display_name else regional_display_name
    get_search_color_name = search_color_name.split(" - ")[1] if " - " in search_color_name else search_color_name

    if "Men" in regional_display_name or "Women" in regional_display_name:
        title = form_title(brand, new_regional_display_name, activity_group, article_type, "", get_search_color_name, products_division)
    else:
        title = form_title(brand, new_regional_display_name, activity_group, article_type, gender, get_search_color_name, products_division)
    return remove_duplicates(title)


def get_variation2_size(input_ws, i):
    """Extracts Size UK (Col 22) or calculates formatted size variation string."""
    product_division = val(input_ws, i, 14)
    size_uk = val(input_ws, i, 22)
    size_fr = val(input_ws, i, 21)
    size_asia = val(input_ws, i, 23)
    size_us = val(input_ws, i, 20)

    if size_uk != "":
        return s(size_uk)

    variation = None
    if product_division in ("Footwear", "Accessories", "Socks"):
        if size_uk != "":
            variation = ("Int:" + s(size_uk)) if is_not_number(size_uk) else ("UK:" + s(size_uk))
        else:
            variation = ("Int:" + s(size_fr)) if is_not_number(size_fr) else ("US:" + s(size_fr))
    elif product_division == "Apparel":
        if size_uk != "":
            variation = ("Int:" + s(size_uk)) if is_not_number(size_uk) else ("UK:" + s(size_uk))
        elif size_us != "":
            variation = ("Int:" + s(size_us)) if is_not_number(size_us) else ("US:" + s(size_us))
        else:
            variation = ("Int:" + s(size_asia)) if is_not_number(size_asia) else ("ASIA:" + s(size_asia))

    return s(variation) if variation else ""


def size_sort_key(size_str):
    """Helper key generator for sorting variants by size."""
    clean_size = s(size_str).upper().replace("UK:", "").replace("US:", "").replace("INT:", "").replace("ASIA:", "").strip()
    if clean_size in SIZE_ORDER:
        return (0, SIZE_ORDER.index(clean_size))
    try:
        return (1, float(clean_size))
    except ValueError:
        return (2, clean_size)


def build_short_description(input_ws, idx):
    """Builds short description HTML bullet list from tracker metadata."""
    color_name = val(input_ws, idx, 9) or val(input_ws, idx, 13)
    fields = [
        ("Brand", val(input_ws, idx, 3)),
        ("Color Name", color_name),
        ("Gender", val(input_ws, idx, 5)),
        ("Activity Group", val(input_ws, idx, 8)),
        ("Collection", val(input_ws, idx, 26)),
        ("Material", val(input_ws, idx, 27)),
        ("Upper Material", val(input_ws, idx, 29)),
        ("Mid Sole Material", val(input_ws, idx, 30)),
        ("Outer Sole Material", val(input_ws, idx, 31)),
        ("Style Number", val(input_ws, idx, 1)),
    ]
    items = [f"<li>{k} : {v}</li>" for k, v in fields if v not in ("", None, "Other")]
    return f"<ul>{''.join(items)}</ul>" if items else ""


def construct_amount_map(price_ws):
    amount_map = {}
    for r in range(2, price_ws.max_row + 1):
        custom_sku = val(price_ws, r, 3)
        if custom_sku:
            amount_map[s(custom_sku).strip()] = [val(price_ws, r, c) for c in range(1, 6)]
    return amount_map


def construct_category_map(category_ws):
    category_map = {}
    for r in range(2, category_ws.max_row + 1):
        key = val(category_ws, r, 1)
        if key:
            category_map[s(key).strip()] = [val(category_ws, r, c) for c in range(1, 4)]
    return category_map


def get_template_attribute1(size_chart_ws):
    size_chart_map = {}
    for r in range(2, size_chart_ws.max_row + 1):
        key = val(size_chart_ws, r, 1)
        if key:
            size_chart_map[s(key).strip()] = [val(size_chart_ws, r, c) for c in range(1, 3)]
    return size_chart_map


def get_parent_key(input_ws, row_idx, products_division):
    if products_division in ["Apparel", "Accessories"]:
        return val(input_ws, row_idx, 1)
    elif products_division == "Footwear":
        return val(input_ws, row_idx, 9)
    return val(input_ws, row_idx, 1)


def _normalize_sheet_name(name):
    return "".join(name.split()).lower()


def find_sheet(wb, expected_name, required=True):
    if expected_name in wb.sheetnames:
        return wb[expected_name]
    target = _normalize_sheet_name(expected_name)
    for name in wb.sheetnames:
        if _normalize_sheet_name(name) == target:
            return wb[name]
    if required:
        raise ConversionError(f"Could not find sheet '{expected_name}'. Available sheets: {wb.sheetnames}")
    return None


def run_conversion(input_ws, price_ws, category_ws, size_chart_ws, stock_ws=None,
                   currency_code="PHP", price_col_setting="D", keep_debug_writes=False,
                   progress_callback=None, custom_headings=None):
    amount_map = construct_amount_map(price_ws)
    category_map = construct_category_map(category_ws)
    size_chart_map = get_template_attribute1(size_chart_ws)
    price_col_idx = parse_column_setting(input_ws, price_col_setting)

    # Group rows by Parent ID
    groups = {}
    for r in range(2, input_ws.max_row + 1):
        division = val(input_ws, r, 14)
        parent_id = get_parent_key(input_ws, r, division)
        if not parent_id:
            parent_id = f"UNKNOWN_{r}"
        groups.setdefault(parent_id, []).append(r)

    main = OutputSheet()
    create_heading_for_target_sheet(main, custom_headings)

    current_out_row = 2
    total_parents = len(groups)
    p_counter = 0

    for parent_id, row_indices in groups.items():
        p_counter += 1
        if progress_callback:
            progress_callback(p_counter, total_parents)

        first_idx = row_indices[0]

        products_division = val(input_ws, first_idx, 14)
        brand = val(input_ws, first_idx, 3)
        regional_display_name = val(input_ws, first_idx, 2)
        gender = val(input_ws, first_idx, 5)
        activity_group = val(input_ws, first_idx, 8)
        article_type = val(input_ws, first_idx, 7)
        search_color_name = val(input_ws, first_idx, 13)
        age_group = val(input_ws, first_idx, 4)
        article_group = val(input_ws, first_idx, 6)
        long_description = val(input_ws, first_idx, 25)
        care_instruction = val(input_ws, first_idx, 43)

        item_title = get_item_title(regional_display_name, brand, gender, activity_group, article_type, search_color_name, products_division)
        mapped_key = f"{age_group}-{gender}-{article_group}-{article_type}-{activity_group}"
        cat_val = category_map.get(mapped_key)
        cat_id = cat_val[1] if (cat_val and len(cat_val) > 1) else ""

        size_chart_key = f"{age_group}-{gender}-{article_group}-{article_type}"
        size_chart_val = size_chart_map.get(size_chart_key)
        size_chart_attr = ("sizechart=" + s(size_chart_val[1])) if (size_chart_val and len(size_chart_val) > 1) else ""

        parent_rrp = val(input_ws, first_idx, price_col_idx)
        short_desc = build_short_description(input_ws, first_idx)

        desc_attr = f"description={replace_spl_character(long_description)}" if long_description else ""
        care_attr = f"care={replace_spl_character(care_instruction)}" if care_instruction else ""

        # -------------------------------------------------------------------
        # 1. WRITE PARENT ROW
        # -------------------------------------------------------------------
        main.set_value(current_out_row, 1, parent_id)                              # SKU (Parent ID)
        main.set_value(current_out_row, 4, parent_id)                              # customSKU (Parent SKU)
        main.set_value(current_out_row, 5, replace_spl_character(item_title))         # itemTitle
        main.set_value(current_out_row, 9, len(row_indices))                       # noOfVariants (Total Count)
        main.set_value(current_out_row, 10, "color_family")                        # variation1
        main.set_value(current_out_row, 11, "size")                                # variation2
        main.set_value(current_out_row, 13, replace_spl_character(short_desc))       # shortDescription
        main.set_value(current_out_row, 17, parent_rrp)                            # itemAmount
        main.set_value(current_out_row, 18, currency_code)                         # currencyCode
        main.set_value(current_out_row, 21, cat_id)                                # categoryID
        main.set_value(current_out_row, 23, brand)                                 # brand
        main.set_value(current_out_row, 30, f"1 X {replace_spl_character(item_title)}") # packageContent
        
        if size_chart_attr:
            main.set_value(current_out_row, 56, size_chart_attr)                   # templateAttribute1
        if desc_attr:
            main.set_value(current_out_row, 57, desc_attr)                          # templateAttribute2
        if care_attr:
            main.set_value(current_out_row, 59, care_attr)                          # templateAttribute4

        current_out_row += 1

        # -------------------------------------------------------------------
        # 2. SORT AND WRITE CHILD VARIANT ROWS
        # -------------------------------------------------------------------
        sorted_row_indices = sorted(
            row_indices,
            key=lambda idx: size_sort_key(get_variation2_size(input_ws, idx))
        )

        for r_idx in sorted_row_indices:
            custom_sku = s(val(input_ws, r_idx, 16)).strip()                       # customSKU (Graas SKU)
            variant_rrp = val(input_ws, r_idx, price_col_idx)                      # itemAmount
            
            # Use Color Name (Col 9) first, fallback to Col 13 if Col 9 is empty
            color_name = val(input_ws, r_idx, 9)
            if not color_name:
                color_name = val(input_ws, r_idx, 13)

            size_uk_val = get_variation2_size(input_ws, r_idx)                    # variation2 (Size UK)

            amt_val = amount_map.get(custom_sku) if custom_sku else None
            if variant_rrp == "" and amt_val:
                variant_rrp = amt_val[3]

            sale_price = amt_val[4] if (amt_val and len(amt_val) > 4) else ""

            main.set_value(current_out_row, 1, parent_id)                          # SKU (Parent ID reference)
            main.set_value(current_out_row, 4, custom_sku)                         # customSKU (Seller SKU)
            main.set_value(current_out_row, 5, replace_spl_character(item_title))     # itemTitle
            main.set_value(current_out_row, 10, color_name)                        # variation1 (Color Name)
            main.set_value(current_out_row, 11, size_uk_val)                       # variation2 (Size UK)
            main.set_value(current_out_row, 13, replace_spl_character(short_desc))    # shortDescription
            main.set_value(current_out_row, 14, sale_price)                        # salePrice
            main.set_value(current_out_row, 17, variant_rrp)                       # itemAmount
            main.set_value(current_out_row, 18, currency_code)                     # currencyCode
            main.set_value(current_out_row, 21, cat_id)                            # categoryID
            main.set_value(current_out_row, 23, brand)                             # brand
            main.set_value(current_out_row, 30, f"1 X {replace_spl_character(item_title)}") # packageContent
            
            if size_chart_attr:
                main.set_value(current_out_row, 56, size_chart_attr)              # templateAttribute1
            if desc_attr:
                main.set_value(current_out_row, 57, desc_attr)                  # templateAttribute2
            if care_attr:
                main.set_value(current_out_row, 59, care_attr)                  # templateAttribute4

            current_out_row += 1

    return main


def build_output_workbook(input_bytes, price_bytes=None, category_bytes=None,
                          size_chart_bytes=None, sample_output_bytes=None,
                          currency_code="PHP", price_col_setting="D",
                          keep_debug_writes=False, progress_callback=None):
    try:
        wb = load_workbook(io.BytesIO(input_bytes), data_only=True)
    except Exception as e:
        raise ConversionError(f"Could not open main input workbook: {e}")

    input_ws = find_sheet(wb, "Input")

    def get_target_ws(file_bytes, sheet_name):
        if file_bytes:
            temp_wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
            return temp_wb.active
        return find_sheet(wb, sheet_name, required=False)

    price_ws = get_target_ws(price_bytes, "Price Sheet")
    category_ws = get_target_ws(category_bytes, "Category sheet")
    size_chart_ws = get_target_ws(size_chart_bytes, "Size chart")
    stock_ws = find_sheet(wb, "Stock sheet", required=False)

    if not price_ws:
        raise ConversionError("Price Sheet missing from main file and no standalone upload provided.")
    if not category_ws:
        raise ConversionError("Category Sheet missing from main file and no standalone upload provided.")
    if not size_chart_ws:
        raise ConversionError("Size Chart Sheet missing from main file and no standalone upload provided.")

    custom_headings = None
    if sample_output_bytes:
        sample_wb = load_workbook(io.BytesIO(sample_output_bytes), data_only=True)
        sample_ws = sample_wb.active
        custom_headings = [val(sample_ws, 1, c) for c in range(1, sample_ws.max_column + 1) if val(sample_ws, 1, c) != ""]

    output = run_conversion(
        input_ws, price_ws, category_ws, size_chart_ws,
        stock_ws=stock_ws, currency_code=currency_code,
        price_col_setting=price_col_setting,
        keep_debug_writes=keep_debug_writes,
        progress_callback=progress_callback,
        custom_headings=custom_headings
    )

    out_wb = output.to_workbook()
    buf = io.BytesIO()
    out_wb.save(buf)
    buf.seek(0)
    return buf.read()
