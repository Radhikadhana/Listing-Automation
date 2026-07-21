"""
Python port of the original Google Apps Script (main / myFunction / helpers).

Design notes
------------
* Sheets are read with openpyxl and accessed with 1-based (row, col) just like
  Apps Script's `sheet.getRange(row, col).getValue()`.
* Apps Script's `.replace(stringA, stringB)` only replaces the FIRST
  occurrence (it's not a global regex). Python's `str.replace` replaces all
  occurrences by default, so a `replace_first()` helper is used everywhere a
  chained `.replace(...)` call appears in the original script, to preserve
  identical behaviour.
* `getValue()` on an empty Sheets cell returns `""`, never `None`. The `val()`
  helper below reproduces that.
* This is a faithful, function-by-function translation. Because the original
  script depends on the exact shape/column layout of a specific workbook,
  test the output against a known-good sample before using it in production,
  especially around the size-sorting logic (`sortChildIndexBasedOnSize`) and
  `variation2`, which are the most format-sensitive parts.
"""

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
import io


# ---------------------------------------------------------------------------
# Small helpers to mirror Apps Script semantics
# ---------------------------------------------------------------------------

def val(ws, row, col):
    """Mirror sheet.getRange(row, col).getValue() -> "" instead of None."""
    v = ws.cell(row=row, column=col).value
    return "" if v is None else v


def s(v):
    """Force to string safely (Apps Script auto-coerces to string for
    .includes()/.indexOf()/.replace() calls)."""
    if v is None:
        return ""
    return str(v)


def replace_first(text, old, new):
    """Mirror JS `"...".replace(old, new)` -> replaces only first match."""
    return s(text).replace(old, new, 1)


def is_not_number(v):
    """Mirror JS isNaN(v) for the way it's used in this script (checking
    whether a size value is numeric)."""
    try:
        float(s(v).strip())
        return False
    except (ValueError, TypeError):
        return True


class OutputSheet:
    """A growable 2D array addressed with 1-based (row, col), mirroring
    main.getRange(row, col).setValue(value) from the Apps Script."""

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


def create_heading_for_target_sheet(main: OutputSheet):
    for i, h in enumerate(HEADINGS):
        main.set_value(1, i + 1, h)


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def replace_spl_character(value):
    value = s(value)
    pairs = [
        ("â€œ", "\u201c"), ("â€", "\u201d"), ("â€˜", "\u2018"), ("â€™", "\u2019"),
        ("â€”", "\u2013"), ("â€“", "\u2014"), ("â€¢", "-"), ("â€¦", "\u2026"),
        ("Ã˜", "\u00d8"), ("Ã‚Â®", "\u00ae"), ("Â³", "\u00b3"), ("Â®", "\u00ae"),
        ("Ã¸", "\u0178"), ("Ã‚", "\u0178"),
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


def form_title(brand, new_regional_display_name, activity_group, article_type,
                gender, search_color_name, products_division):
    brand = s(brand)
    new_regional_display_name = s(new_regional_display_name)
    gender = s(gender) if gender is not None else gender
    search_color_name = s(search_color_name)

    title = "[NEW] "
    if "Licence" in brand:
        title += replace_first(brand, "Licence", "PUMA")
    else:
        title += brand

    if gender not in (None, "") and gender not in title:
        if gender == "Unisex":
            title += " " + gender

    if new_regional_display_name not in title:
        if "Trainers" in new_regional_display_name:
            check = replace_first(new_regional_display_name, "Trainers", "Shoes")
            title += " " + check
        elif "Sandals" in new_regional_display_name:
            check = replace_first(new_regional_display_name, "Sandals", "Sports Sandals")
            title += " " + check
        elif "Slides" in new_regional_display_name:
            check = replace_first(new_regional_display_name, "Slides", "Slides Slippers")
            title += " " + check
        elif "Trainer" in new_regional_display_name:
            check = replace_first(new_regional_display_name, "Trainer", "Shoes")
            title += " " + check
        else:
            title += " " + new_regional_display_name

    if products_division == "Footwear":
        if search_color_name not in title:
            title += " (" + search_color_name + ") "

    return title


def get_item_title(regional_display_name, brand, gender, activity_group,
                    article_type, search_color_name, products_division):
    regional_display_name = s(regional_display_name)
    search_color_name = s(search_color_name)

    new_regional_display_name = regional_display_name
    if "\u2019s" in regional_display_name:
        new_regional_display_name = replace_first(regional_display_name, "\u2019s", "'s\u2122")

    get_search_color_name = ""
    if " - " in search_color_name:
        get_search_color_name = search_color_name.split(" - ")[1]

    if "Men" in regional_display_name or "Women" in regional_display_name:
        title = form_title(brand, new_regional_display_name, activity_group,
                            article_type, "", get_search_color_name, products_division)
    else:
        title = form_title(brand, new_regional_display_name, activity_group,
                            article_type, gender, get_search_color_name, products_division)
    return remove_duplicates(title)


def get_short_description(short_description, brand, search_color_name, gender,
                           activity_group, collection, material, material_local,
                           upper_material, mid_sole_material, outer_sole_material,
                           shell_material, toe_type, heel_type, fastener, fit,
                           puma_technology, technology_purpose, style):
    short_desc = s(short_description)

    def add(label, value, exclude_other=False):
        nonlocal short_desc
        if value not in ("", None) and not (exclude_other and value == "Other"):
            short_desc += f"<li>{label} : {value}</li>"

    add("Brand", brand)
    add("Color Name", search_color_name)
    add("Gender", gender)
    add("Activity Group", activity_group)
    add("Collection", collection)

    if material not in ("", None) and material != "Other":
        new_material = f"<li>Material : {material}</li>"
        main_material_2_present = False
        if "Main Material 1" in new_material:
            new_material = replace_first(new_material, "<li>Material : ", "<li>")
        if "Main Material 2" in new_material:
            main_material_2_present = True
            new_material = replace_first(new_material, "<li>Material : ", "<li>")
            new_material = replace_first(new_material, "Main Material 2", "</li><li>Main Material 2")
        if "Main Material 3" in new_material:
            new_material = replace_first(new_material, "<li>Material : ", "<li>")
            if not main_material_2_present:
                new_material = replace_first(new_material, "Main Material 3", "</li><li>Main Material 2")
            else:
                new_material = replace_first(new_material, "Main Material 3", "</li><li>Main Material 3")
        short_desc += new_material

    add("Material Local", material_local, exclude_other=True)
    add("Upper Material", upper_material, exclude_other=True)
    add("Mid Sole Material", mid_sole_material, exclude_other=True)
    add("Outer Sole Material", outer_sole_material, exclude_other=True)
    add("Shell Material", shell_material, exclude_other=True)
    add("Toe Type", toe_type)
    add("Heel Type", heel_type)
    add("Fastener", fastener)
    add("Fit", fit)
    add("PUMA Technology", puma_technology)
    add("Technology Purpose", technology_purpose)
    add("Style Number", style)

    return short_desc


def fill_template_attributes(main: OutputSheet, template_attribute1,
                              template_attribute4, template_attribute5,
                              index, long_description):
    long_description = s(long_description)
    template_attribute2 = ""
    template_attribute3 = ""

    if "FEATURES" in long_description:
        template_attribute2 = long_description[long_description.find("<p>"):long_description.find("FEATURES")]
        template_attribute3 = long_description[long_description.find("FEATURES"):]
    elif "DETAILS" in long_description:
        template_attribute2 = long_description[long_description.find("<p>"):long_description.find("DETAILS")]
        template_attribute3 = long_description[long_description.find("DETAILS"):]
    else:
        template_attribute2 = long_description[long_description.find("<p>"):]

    main.set_value(index, 56, "sizechart=" + s(template_attribute1))
    if template_attribute2 != "":
        main.set_value(index, 57, "description=" + replace_first(
            replace_spl_character(template_attribute2), "<h3>", ""))
    if template_attribute3 != "":
        main.set_value(index, 58, "productstory=<h3>" + replace_spl_character(template_attribute3))
    if template_attribute4 != "":
        main.set_value(index, 59, "care=" + replace_spl_character(template_attribute4))


def fill_default_values(main: OutputSheet, index, amount_map_value):
    if amount_map_value not in ("", None):
        sale_price = amount_map_value[4]
        if sale_price not in ("", None):
            main.set_value(index, 15, "2024-05-10 00:00:00")
            main.set_value(index, 16, "2024-06-10 23:59:00")
    main.set_value(index, 6, "userTemplate-PH_PumaAccessories")
    main.set_value(index, 18, "PHP")
    main.set_value(index, 22, "default")
    main.set_value(index, 25, "No Warranty")
    main.set_value(index, 26, "0.5")
    main.set_value(index, 27, "15")
    main.set_value(index, 28, "12")
    main.set_value(index, 29, "12")


# ---------------------------------------------------------------------------
# variation2
# ---------------------------------------------------------------------------

def variation2(input_ws, i):
    product_division = val(input_ws, i, 14)
    size_uk = val(input_ws, i, 22)
    size_fr = val(input_ws, i, 21)
    size_asia = val(input_ws, i, 23)
    size_us = val(input_ws, i, 20)

    variation = None

    if product_division == "Footwear":
        if size_uk != "":
            variation = ("Int:" + s(size_uk)) if is_not_number(size_uk) else ("UK:" + s(size_uk))
        else:
            variation = ("Int:" + s(size_fr)) if is_not_number(size_fr) else ("US:" + s(size_fr))

    if product_division == "Apparel":
        if size_uk != "":
            variation = ("Int:" + s(size_uk)) if is_not_number(size_uk) else ("UK:" + s(size_uk))
        elif size_uk == "" and size_us != "":
            variation = ("Int:" + s(size_us)) if is_not_number(size_us) else ("US:" + s(size_us))
        else:
            variation = ("Int:" + s(size_asia)) if is_not_number(size_asia) else ("ASIA:" + s(size_asia))

    if product_division == "Accessories":
        if size_uk != "":
            variation = ("Int:" + s(size_uk)) if is_not_number(size_uk) else ("UK:" + s(size_uk))
        else:
            variation = ("Int:" + s(size_us)) if is_not_number(size_us) else ("US:" + s(size_us))

    if product_division == "Socks":
        if size_uk != "":
            variation = ("Int:" + s(size_uk)) if is_not_number(size_uk) else ("UK:" + s(size_uk))
        else:
            variation = ("Int:" + s(size_fr)) if is_not_number(size_fr) else ("US:" + s(size_fr))

    if variation is None:
        return ""

    if "/" in variation:
        if "S/M" in variation or "M/L" in variation or "L/XL" in variation:
            return variation
        v = replace_first(variation, "Int:", "Int:W")
        v = replace_first(v, "/", " L")
        return v
    elif any(tag in variation for tag in ("OSFA", "Mini", "Kids", "Youth", "Adult", "UA")):
        if "OSFA" in variation:
            return "Int:One size"
        if "Mini" in variation:
            return "Int:XS"
        if "Kids" in variation:
            return "Int:S"
        if "Youth" in variation:
            return "Int:M"
        if "Adult" in variation:
            return "Int:L"
        if "UA" in variation:
            return "Int:UA"
    else:
        if "Youth" in variation:
            return variation
        else:
            return replace_first(variation, "Y", " yrs")

    return variation


# ---------------------------------------------------------------------------
# Map constructors
# ---------------------------------------------------------------------------

def construct_amount_map(price_ws):
    amount_map = {}
    last_row = price_ws.max_row
    for r in range(2, last_row + 1):
        row = [val(price_ws, r, c) for c in range(1, 6)]  # A:E
        custom_sku = row[2]
        if custom_sku not in ("", None):
            amount_map[custom_sku] = row
    return amount_map


def construct_quantity_map(stock_ws):
    quantity_map = {}
    if stock_ws is None:
        return quantity_map
    last_row = stock_ws.max_row
    for r in range(2, last_row + 1):
        row = [val(stock_ws, r, c) for c in range(1, 3)]  # A:B
        custom_sku = row[0]
        if custom_sku not in ("", None):
            quantity_map[custom_sku] = row
    return quantity_map


def construct_category_map(category_ws):
    category_map = {}
    last_row = category_ws.max_row
    for r in range(2, last_row + 1):
        row = [val(category_ws, r, c) for c in range(1, 4)]  # A:C
        name = row[0]
        if name not in ("", None):
            category_map[name] = row
    return category_map


def get_template_attribute1(size_chart_ws):
    size_chart_map = {}
    last_row = size_chart_ws.max_row
    for r in range(2, last_row + 1):
        row = [val(size_chart_ws, r, c) for c in range(1, 3)]  # A:B
        key = row[0]
        if key not in ("", None):
            size_chart_map[key] = row
    return size_chart_map


def count_no_of_items(input_ws):
    result = {}
    last_row = input_ws.max_row
    for i in range(2, last_row + 1):
        products = val(input_ws, i, 14)
        key = val(input_ws, i, 9) if products == "Footwear" else val(input_ws, i, 1)
        if key not in ("", None):
            result[key] = result.get(key, 0) + 1
    return result


# ---------------------------------------------------------------------------
# Size sorting
# ---------------------------------------------------------------------------

STRING_SIZE_ORDER = [
    "3XS", "XXXS", "XXS", "XS", "S", "S/M", "M", "M/L", "L", "L/XL", "XL",
    "XXL", "XXXL", "3XL", "4XL", "5XL", "6XL", "1-2Y", "2-3Y", "3-4Y", "4-5Y",
    "5-6Y", "6-7Y", "7-8Y", "8-9Y", "9-10Y", "10-11Y", "11-12Y", "12-13Y",
    "13-14Y", "14-15Y", "15-16Y", "16-17Y", "17-18Y", "18-19Y", "19-20Y",
    "6Y", "8Y", "10Y", "12Y", "14Y", "16Y", "18Y", "20Y", "OSFA", "One size",
    "UA", "Mini", "Kids", "Adult", "Youth",
]

STRING_SIZE_TRIGGERS = set(STRING_SIZE_ORDER)


def _sort_by_int_values(child_array, temp_array, child_update_index_map, colour_array):
    colour_size_map = []
    available_colour = []
    for size, colour in zip(child_array, colour_array):
        if colour not in available_colour:
            available_colour.append(colour)
        colour_size_map.append(f"{colour}_{size}")

    colour_count = 0
    for colour in available_colour:
        for size in temp_array:
            key = f"{colour}_{size}"
            if key in colour_size_map:
                child_update_index_map[key] = colour_count
                colour_count += 1


def _sort_by_string_values(child_array, temp_array, child_update_index_map, colour_array):
    colour_size_map = []
    available_colour = []
    for size, colour in zip(child_array, colour_array):
        if colour not in available_colour:
            available_colour.append(colour)
        colour_size_map.append(f"{colour}_{size}")

    colour_count = 0
    for colour in available_colour:
        for size in STRING_SIZE_ORDER:
            key = f"{colour}_{size}"
            if key in colour_size_map:
                child_update_index_map[key] = colour_count
                colour_count += 1


def sort_child_index_based_on_size(input_ws, child_update_index_map, style_count, j):
    child_end_index = j + style_count - 1
    child_array = []
    colour_array = []
    temp_array = []
    parent_quantity = 0

    for i in range(j, child_end_index + 1):
        row = [val(input_ws, i, c) for c in range(12, 23)]  # L:V (12..22)
        colour = row[0]
        custom_sku = row[4]
        qty = row[5]
        try:
            parent_quantity += float(qty) if qty not in ("", None) else 0
        except (ValueError, TypeError):
            pass

        size_value = s(variation2(input_ws, i))
        for old, new in (("UK:", ""), ("FR:", ""), ("US:", ""), ("ASIA:", ""),
                         ("Int:", ""), (" yrs", "Y")):
            size_value = replace_first(size_value, old, new)
        if " L" in size_value:
            size_value = replace_first(size_value, "Int:W", "")
            size_value = replace_first(size_value, "Int:", "")
            size_value = replace_first(size_value, "W", "")
            size_value = replace_first(size_value, " L", "/")

        if size_value not in temp_array:
            temp_array.append(size_value)
        child_array.append(size_value)
        colour_array.append(colour)

    sort_by_string = any(v in STRING_SIZE_TRIGGERS for v in child_array)

    if sort_by_string:
        _sort_by_string_values(child_array, temp_array, child_update_index_map, colour_array)
    else:
        def sort_key(v):
            try:
                return (0, float(v))
            except (ValueError, TypeError):
                return (1, v)
        temp_array_sorted = sorted(temp_array, key=sort_key)
        _sort_by_int_values(child_array, temp_array_sorted, child_update_index_map, colour_array)

    return parent_quantity


# ---------------------------------------------------------------------------
# fillParentRow
# ---------------------------------------------------------------------------

def fill_parent_row(main: OutputSheet, input_ws, index, i, category_map,
                     amount_map, style_count_map, child_update_index_map,
                     size_chart_map):
    custom_sku = val(input_ws, i, 16)
    age_group = val(input_ws, i, 4)
    article_group = val(input_ws, i, 6)
    brand = val(input_ws, i, 3)
    regional_display_name = val(input_ws, i, 2)
    gender = val(input_ws, i, 5)
    activity_group = val(input_ws, i, 8)
    article_type = val(input_ws, i, 7)
    search_color_name = val(input_ws, i, 13)
    long_description = val(input_ws, i, 25)
    collection = val(input_ws, i, 26)
    material = val(input_ws, i, 27)
    material_local = val(input_ws, i, 28)
    upper_material = val(input_ws, i, 29)
    mid_sole_material = val(input_ws, i, 30)
    outer_sole_material = val(input_ws, i, 31)
    shell_material = val(input_ws, i, 32)
    toe_type = val(input_ws, i, 33)
    heel_type = val(input_ws, i, 34)
    fastener = val(input_ws, i, 66)
    fit = val(input_ws, i, 67)
    puma_technology = val(input_ws, i, 35)
    technology_purpose = val(input_ws, i, 36)
    short_description = val(input_ws, i, 24)
    care = val(input_ws, i, 43)
    care_label = val(input_ws, i, 44)
    products_division = val(input_ws, i, 14)

    item_title = get_item_title(regional_display_name, brand, gender, activity_group,
                                 article_type, search_color_name, products_division)
    main.set_value(index, 5, replace_spl_character(item_title))
    main.set_value(index, 30, "1 X " + replace_spl_character(item_title))

    mapped_key = f"{age_group}-{gender}-{article_group}-{article_type}-{activity_group}"
    category_map_value = category_map.get(mapped_key)
    amount_map_value = amount_map.get(custom_sku)

    if amount_map_value not in ("", None):
        item_amount = amount_map_value[3]
        main.set_value(index, 17, item_amount)

    act_group = val(input_ws, i, 8)
    if act_group == "Prime/Select":
        act_group = "Others"
    elif act_group in ("Sport Classics", "Evolution", "Basics", "Kids", "Auto"):
        act_group = "Lifestyle"

    material2 = s(val(input_ws, i, 27))
    val1 = ""
    if "100% polyester" in material2:
        val1 = 'normal.clothing_material=["Polyester",]'
    elif "100% nylon" in material2:
        val1 = 'normal.clothing_material=["Nylon",]'
    elif "100% cotton" in material2:
        val1 = 'normal.clothing_material=["Cotton",]'
    elif "polyester" in material2 and "nylon" in material2:
        val1 = 'normal.clothing_material=["Polyester+Nylon",]'
    elif "polyester" in material2 and "cotton" in material2:
        val1 = 'normal.clothing_material=["Polyester+Cotton",]'
    elif "polyester" in material2 and "elastane" in material2:
        val1 = 'normal.clothing_material=["Polyester+Elasteane",]'
    elif "polyester" in material2 and "spandex" in material2:
        val1 = 'normal.clothing_material=["Polyester+Spandex",]'

    item_spec_index = 33
    main.set_value(index, item_spec_index, f'normal.activity_type=["{act_group}",]')
    if val1 != "":
        item_spec_index += 1
        main.set_value(index, item_spec_index, val1)
    item_spec_index += 1
    main.set_value(index, item_spec_index, 'normal.delivery_option_economy=["No",]')

    if article_group not in ("", None):
        if s(article_group).lower() == "tops":
            tops_type = ""
            if article_type == "Tee":
                tops_type = "T-Shirts"
            elif article_type == "Polo":
                tops_type = "Polo"
            if tops_type != "":
                item_spec_index += 1
                main.set_value(index, item_spec_index, f'normal.tops_type=["{tops_type}",]')

    if category_map_value not in (None,) and len(category_map_value) > 0:
        main.set_value(index, 21, category_map_value[1])
    else:
        main.set_value(index, 21, "error")

    style = val(input_ws, i, 9) if products_division == "Footwear" else val(input_ws, i, 1)

    short_description_full = get_short_description(
        short_description, brand, search_color_name, gender, activity_group,
        collection, material, material_local, upper_material, mid_sole_material,
        outer_sole_material, shell_material, toe_type, heel_type, fastener, fit,
        puma_technology, technology_purpose, style)

    style_count = style_count_map.get(style)
    sort_child_index_based_on_size(input_ws, child_update_index_map, style_count, i)

    fill_default_values(main, index, amount_map_value)

    size_chart_key = f"{age_group}-{gender}-{article_group}-{article_type}"
    template_attribute_value = size_chart_map.get(size_chart_key)
    template_attribute1 = ""
    template_attribute4 = ""
    template_attribute5 = ""
    if template_attribute_value not in ("", None):
        template_attribute1 = template_attribute_value[1]
    if care not in ("", None):
        template_attribute4 += f"<p><strong>Care:</strong>{care}<p>"
    if care_label not in ("", None):
        template_attribute4 += f"<p><strong>Care Label:</strong>{care_label}<p>"

    fill_template_attributes(main, template_attribute1, template_attribute4,
                              template_attribute5, index, long_description)

    main.set_value(index, 19, 0)

    if style_count_map.get(style, 0) > 1:
        main.set_value(index, 4, style)
        main.set_value(index, 9, style_count)
        main.set_value(index, 10, "color_family")
        main.set_value(index, 11, "size")
    else:
        main.set_value(index, 4, custom_sku)

    main.set_value(index, 13, "<ul>" + replace_spl_character(short_description_full) + "</ul>")
    main.set_value(index, 23, brand)
    main.set_value(index, 24, style)


# ---------------------------------------------------------------------------
# Top level orchestration (mirrors main() / myFunction())
# ---------------------------------------------------------------------------

def run_conversion(input_ws, price_ws, category_ws, size_chart_ws, stock_ws=None,
                    keep_debug_writes=False, progress_callback=None):
    """
    Faithful port of myFunction(). Returns an OutputSheet.

    keep_debug_writes: the original script has three lines that write debug
    info ("mappingKey : ...", "childIndex : ...", the whole
    childUpdateIndexMap) into output columns 1-3 at row `i` (the *input* row
    number), which looks like leftover debugging rather than intentional
    output and will visually corrupt the top of the Output sheet for large
    files. Default False = skip them. Set True to reproduce the original
    (buggy) behaviour exactly.
    """
    amount_map = construct_amount_map(price_ws)
    category_map = construct_category_map(category_ws)
    style_count_map = count_no_of_items(input_ws)
    size_chart_map = get_template_attribute1(size_chart_ws)

    main = OutputSheet()
    processed_style = []
    index = 2
    parent_row = 2
    processed_parent_count = 0
    current_parent_index = 2
    child_update_index_map = {}

    last_row = input_ws.max_row

    for i in range(2, last_row + 1):
        if progress_callback and (i % 25 == 0 or i == last_row):
            progress_callback(i - 1, last_row - 1)

        if i == 2:
            create_heading_for_target_sheet(main)

        products = val(input_ws, i, 14)
        if products == "Footwear":
            style = val(input_ws, i, 9)
            style_next_row = val(input_ws, i + 1, 9) if i + 1 <= last_row else ""
        else:
            style = val(input_ws, i, 1)
            style_next_row = val(input_ws, i + 1, 1) if i + 1 <= last_row else ""

        if (style_count_map.get(style) == 1) or (style == style_next_row and style not in processed_style):
            fill_parent_row(main, input_ws, index, i, category_map, amount_map,
                             style_count_map, child_update_index_map, size_chart_map)
            current_parent_index = index
            if style_count_map.get(style, 0) > 1:
                parent_row = i + processed_parent_count
                processed_parent_count += 1
            index += 1

        if style_count_map.get(style) == 1:
            continue

        custom_sku = val(input_ws, i, 16)
        variation1 = s(val(input_ws, i, 12))
        new_variation1 = replace_first(variation1, "Puma", "PUMA") if "Puma" in variation1 else variation1

        variation_two = s(variation2(input_ws, i))
        temp_var_2 = variation_two
        if " L" in temp_var_2:
            temp_var_2 = replace_first(temp_var_2, "Int:W", "")
            temp_var_2 = replace_first(temp_var_2, "Int:", "")
            temp_var_2 = replace_first(temp_var_2, "W", "")
            temp_var_2 = replace_first(temp_var_2, " L", "/")

        temp_var_2_clean = temp_var_2
        for old, new in (("UK:", ""), ("FR:", ""), ("US:", ""), ("ASIA:", ""),
                         ("Int:", ""), (" yrs", "Y"), ("W", ""), (" L", "/")):
            temp_var_2_clean = replace_first(temp_var_2_clean, old, new)
        mapping_key = variation1 + "_" + temp_var_2_clean

        if keep_debug_writes:
            main.set_value(i, 2, "mappingKey : " + mapping_key)
            main.set_value(i, 3, "childIndex : " + s(child_update_index_map.get(mapping_key)))
            main.set_value(i, 1, str(child_update_index_map))

        child_index = child_update_index_map.get(mapping_key)
        if child_index is None:
            index += 1
            continue
        child_index = child_index + parent_row + 1

        main.set_value(child_index, 11, variation_two)
        processed_style.append(style)

        amount_map_value = amount_map.get(custom_sku)
        item_amount = ""
        sale_price = ""
        if amount_map_value not in ("", None):
            item_amount = amount_map_value[3]
            sale_price = amount_map_value[4]
        else:
            main.set_value(child_index, 17, "error")
            main.set_value(child_index, 14, "error")

        age_group = val(input_ws, i, 4)
        article_group = val(input_ws, i, 6)
        brand = val(input_ws, i, 3)
        regional_display_name = s(val(input_ws, i, 2))
        gender = val(input_ws, i, 5)
        activity_group = val(input_ws, i, 8)
        article_type = val(input_ws, i, 7)
        search_color_name = s(val(input_ws, i, 13))
        color_name = val(input_ws, i, 9)

        new_regional_display_name = regional_display_name
        if "\u2019s" in regional_display_name:
            new_regional_display_name = replace_first(regional_display_name, "\u2019s", "'s\u2122")

        get_search_color_name = ""
        if " - " in search_color_name:
            get_search_color_name = search_color_name.split(" - ")[1]

        if "Men" in regional_display_name or "Women" in regional_display_name:
            title = form_title(brand, new_regional_display_name, activity_group,
                                article_type, "", get_search_color_name, products)
        else:
            title = form_title(brand, new_regional_display_name, activity_group,
                                article_type, gender, get_search_color_name, products)
        item_title = remove_duplicates(title)

        mapped_key = f"{age_group}-{gender}-{article_group}-{article_type}-{activity_group}"
        category_map_value = category_map.get(mapped_key)
        if category_map_value not in (None,) and len(category_map_value) > 0:
            main.set_value(child_index, 21, category_map_value[1])
        else:
            main.set_value(index, 21, "error")

        main.set_value(child_index, 4, custom_sku)
        main.set_value(child_index, 5, replace_spl_character(item_title))
        if sale_price not in ("", None):
            main.set_value(child_index, 14, sale_price)

        main.set_value(child_index, 10, new_variation1)
        fill_default_values(main, child_index, amount_map_value)

        main.set_value(child_index, 17, item_amount)
        main.set_value(child_index, 19, 0)

        main.set_value(child_index, 23, brand)
        main.set_value(child_index, 24, color_name)
        main.set_value(child_index, 30, "1 X " + replace_spl_character(item_title))
        main.set_value(child_index, 31, 'sku.color_family=["' + s(new_variation1) + '",]')
        main.set_value(child_index, 32, 'sku.size=["' + variation_two + '",]')
        main.set_value(current_parent_index, 31, main.get_value(current_parent_index + 1, 31))
        main.set_value(current_parent_index, 32, main.get_value(current_parent_index + 1, 32))
        index += 1

    return main


class ConversionError(Exception):
    """Raised for problems that would otherwise silently produce an empty or
    near-empty Output sheet, so the UI can show a clear message instead of
    just 'nothing happened'."""


def _normalize_sheet_name(name):
    return "".join(name.split()).lower()


def find_sheet(wb, expected_name, required=True):
    """Look up a worksheet by name, tolerating case and stray whitespace
    differences (a very common cause of 'required sheet not found')."""
    if expected_name in wb.sheetnames:
        return wb[expected_name]
    target = _normalize_sheet_name(expected_name)
    for name in wb.sheetnames:
        if _normalize_sheet_name(name) == target:
            return wb[name]
    if required:
        raise ConversionError(
            f"Could not find a sheet named '{expected_name}' (case/whitespace "
            f"insensitive match also failed). Sheets present in the uploaded "
            f"file: {wb.sheetnames}"
        )
    return None


def _sheet_has_any_values(ws, max_check_rows=5):
    """Quick check: does this worksheet have any non-empty cells at all in its
    first few data rows? Used to catch the common case where a workbook was
    saved with live formulas and no cached results, so data_only=True reads
    come back as all-None."""
    if ws is None:
        return True
    last_row = min(ws.max_row, max_check_rows + 1)
    for r in range(2, last_row + 1):
        for c in range(1, min(ws.max_column, 40) + 1):
            if ws.cell(row=r, column=c).value not in (None, ""):
                return True
    return ws.max_row <= 1  # genuinely empty sheet (no data rows) isn't itself an error here


def build_output_workbook(input_bytes, keep_debug_writes=False, progress_callback=None):
    """Load an xlsx (as bytes) containing Input / Price Sheet / Category sheet /
    Size chart (and optionally Stock sheet) worksheets, run the conversion,
    and return an in-memory xlsx workbook (bytes) with the Output sheet."""
    try:
        wb = load_workbook(io.BytesIO(input_bytes), data_only=True)
    except Exception as e:
        raise ConversionError(
            f"Could not open the uploaded file as an .xlsx workbook: {e}. "
            f"Make sure it's a real Excel file (not .xls, .csv, or a Google "
            f"Sheets export link) and hasn't been corrupted."
        )

    input_ws = find_sheet(wb, "Input")
    price_ws = find_sheet(wb, "Price Sheet")
    category_ws = find_sheet(wb, "Category sheet")
    size_chart_ws = find_sheet(wb, "Size chart")
    stock_ws = find_sheet(wb, "Stock sheet", required=False)

    if input_ws.max_row < 2:
        raise ConversionError(
            "The 'Input' sheet has no data rows below the header (row 1). "
            "Nothing to convert."
        )

    if not _sheet_has_any_values(input_ws):
        raise ConversionError(
            "The 'Input' sheet's data rows all read as empty. This usually "
            "means the workbook stores live formulas without cached values "
            "(common when a file is exported from Google Sheets with "
            "'File > Download' right after edits, or opened/re-saved by a "
            "tool that strips cached formula results). Try opening the file "
            "in Excel and re-saving it, or in Google Sheets doing "
            "File > Download > Microsoft Excel (.xlsx), then re-upload."
        )

    output = run_conversion(input_ws, price_ws, category_ws, size_chart_ws,
                             stock_ws=stock_ws, keep_debug_writes=keep_debug_writes,
                             progress_callback=progress_callback)

    if output.max_row < 2:
        raise ConversionError(
            "The conversion ran but produced zero output rows. This usually "
            "means the 'products division' column (column N / 14 in 'Input') "
            "doesn't contain any of the expected values "
            "('Footwear', 'Apparel', 'Accessories', 'Socks') for any row, or "
            "the style columns (A or I) are empty for every row."
        )

    out_wb = output.to_workbook()
    buf = io.BytesIO()
    out_wb.save(buf)
    buf.seek(0)
    return buf.read()
