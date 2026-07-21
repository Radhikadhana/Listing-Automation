"""
Logic module for Product Feed Generator / Zecom Tracker processing.
Supports dynamic price column selection, currency code settings, and
division-based parent SKU mapping (Apparel/Accessories -> Style; Footwear -> Color No.).
"""

from openpyxl import Workbook, load_workbook
from openpyxl.utils import column_index_from_string
import io


class ConversionError(Exception):
    """Raised for issues that prevent proper generation of the Output sheet."""
    pass


# ---------------------------------------------------------------------------
# Default Headings & Helpers
# ---------------------------------------------------------------------------

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
    """Mirror sheet.getRange(row, col).getValue() -> "" instead of None."""
    v = ws.cell(row=row, column=col).value
    return "" if v is None else v


def s(v):
    if v is None:
        return ""
    return str(v)


def replace_first(text, old, new):
    return s(text).replace(old, new, 1)


def is_not_number(v):
    try:
        float(s(v).strip())
        return False
    except (ValueError, TypeError):
        return True


def parse_column_setting(ws, col_setting):
    """Parse column setting (letter like 'D' or '1' or header name) to 1-based index."""
    if not col_setting:
        return 4  # Default column D

    col_setting_str = str(col_setting).strip()

    # Try column letter (e.g. 'D', 'AA')
    if col_setting_str.isalpha():
        try:
            return column_index_from_string(col_setting_str.upper())
        except ValueError:
            pass

    # Try column integer index
    if col_setting_str.isdigit():
        return int(col_setting_str)

    # Search header row (Row 1) for matching column name
    for c in range(1, ws.max_column + 1):
        header_val = str(val(ws, 1, c)).strip().lower()
        if header_val == col_setting_str.lower():
            return c

    return 4  # Fallback to column D


class OutputSheet:
    def __init__(self):
        self.rows = {}
        self.max_col = 0
        self.max_row = 0

    def set_value(self, row, col, value):
        self.rows.setdefault(row, {})[col] = value
        self.max_row = max(self.max_row, row)
        self.max_col = max(self.max_col, col)

    def get_value(self, row, col):
        return self.rows.get(row, {}).get(col, "")

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
    get_search_color_name = search_color_name.split(" - ")[1] if " - " in search_color_name else ""

    if "Men" in regional_display_name or "Women" in regional_display_name:
        title = form_title(brand, new_regional_display_name, activity_group, article_type, "", get_search_color_name, products_division)
    else:
        title = form_title(brand, new_regional_display_name, activity_group, article_type, gender, get_search_color_name, products_division)
    return remove_duplicates(title)


def construct_amount_map(price_ws):
    amount_map = {}
    for r in range(2, price_ws.max_row + 1):
        row = [val(price_ws, r, c) for c in range(1, 6)]
        custom_sku = row[2]  # Col C
        if custom_sku:
            amount_map[custom_sku] = row
    return amount_map


def construct_category_map(category_ws):
    category_map = {}
    for r in range(2, category_ws.max_row + 1):
        row = [val(category_ws, r, c) for c in range(1, 4)]
        key = row[0]  # Col A
        if key:
            category_map[key] = row
    return category_map


def get_template_attribute1(size_chart_ws):
    size_chart_map = {}
    for r in range(2, size_chart_ws.max_row + 1):
        row = [val(size_chart_ws, r, c) for c in range(1, 3)]
        key = row[0]  # Col A
        if key:
            size_chart_map[key] = row
    return size_chart_map


def get_parent_sku(input_ws, row_idx, products_division):
    """
    Parent SKU Rules:
    - Apparel and Accessories: Use Style (Col 1)
    - Footwear: Use Color No. (Col 9)
    """
    if products_division in ["Apparel", "Accessories"]:
        return val(input_ws, row_idx, 1)  # Style column
    elif products_division == "Footwear":
        return val(input_ws, row_idx, 9)  # Color No. column
    else:
        # Default fallback to Style (Col 1) if not specified
        return val(input_ws, row_idx, 1)


def count_no_of_items(input_ws):
    result = {}
    for i in range(2, input_ws.max_row + 1):
        products = val(input_ws, i, 14)
        parent_sku = get_parent_sku(input_ws, i, products)
        if parent_sku:
            result[parent_sku] = result.get(parent_sku, 0) + 1
    return result


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
    style_count_map = count_no_of_items(input_ws)
    size_chart_map = get_template_attribute1(size_chart_ws)

    # Parse tracker price column (defaults to Col D if invalid)
    price_col_idx = parse_column_setting(input_ws, price_col_setting)

    main = OutputSheet()
    index = 2
    last_row = input_ws.max_row

    for i in range(2, last_row + 1):
        if progress_callback and (i % 25 == 0 or i == last_row):
            progress_callback(i - 1, last_row - 1)

        if i == 2:
            create_heading_for_target_sheet(main, custom_headings)

        products_division = val(input_ws, i, 14)
        custom_sku = val(input_ws, i, 16)
        brand = val(input_ws, i, 3)
        regional_display_name = val(input_ws, i, 2)
        gender = val(input_ws, i, 5)
        activity_group = val(input_ws, i, 8)
        article_type = val(input_ws, i, 7)
        search_color_name = val(input_ws, i, 13)
        age_group = val(input_ws, i, 4)
        article_group = val(input_ws, i, 6)

        # Apply Parent SKU logic
        parent_sku = get_parent_sku(input_ws, i, products_division)

        # Set Parent SKU into customSKU / Parent Column (Col 4)
        main.set_value(index, 4, parent_sku if parent_sku else custom_sku)

        # Set Item Title
        item_title = get_item_title(regional_display_name, brand, gender, activity_group, article_type, search_color_name, products_division)
        main.set_value(index, 5, replace_spl_character(item_title))

        # 1. Price / RRP Mapping: Read from selected Tracker Price Column
        tracker_price = val(input_ws, i, price_col_idx)
        if tracker_price != "":
            # Set RRP into itemAmount (Col 17)
            main.set_value(index, 17, tracker_price)
        else:
            # Fallback to Price Sheet itemAmount (Col D)
            amount_map_value = amount_map.get(custom_sku)
            if amount_map_value:
                main.set_value(index, 17, amount_map_value[3])

        # Sale Price mapping from Price Sheet if available
        amount_map_value = amount_map.get(custom_sku)
        if amount_map_value and len(amount_map_value) > 4:
            main.set_value(index, 14, amount_map_value[4])  # Col E (salePrice)

        # 2. Currency Code Setting (Col 18)
        main.set_value(index, 18, currency_code)

        # Category mapping
        mapped_key = f"{age_group}-{gender}-{article_group}-{article_type}-{activity_group}"
        cat_val = category_map.get(mapped_key)
        if cat_val and len(cat_val) > 1:
            main.set_value(index, 21, cat_val[1])  # Col B

        # Size Chart mapping
        size_chart_key = f"{age_group}-{gender}-{article_group}-{article_type}"
        size_chart_val = size_chart_map.get(size_chart_key)
        if size_chart_val and len(size_chart_val) > 1:
            main.set_value(index, 56, "sizechart=" + s(size_chart_val[1]))

        index += 1

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
