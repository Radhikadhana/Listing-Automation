# Function modification in logic.py

def create_heading_for_target_sheet(main: OutputSheet, custom_headings=None):
    """Populate headings based on provided custom sample output sheet or defaults."""
    headings = custom_headings if custom_headings else HEADINGS
    for i, h in enumerate(headings):
        main.set_value(1, i + 1, h)

# Updated build_output_workbook in logic.py

def build_output_workbook(
    input_bytes, 
    price_bytes=None, 
    category_bytes=None, 
    size_chart_bytes=None, 
    sample_output_bytes=None,
    keep_debug_writes=False, 
    progress_callback=None
):
    """
    Builds the ZECOM feed output sheet from uploaded individual/combined files.
    """
    try:
        wb = load_workbook(io.BytesIO(input_bytes), data_only=True)
    except Exception as e:
        raise ConversionError(f"Could not open the uploaded main file: {e}")

    input_ws = find_sheet(wb, "Input")

    # Helper function to extract individual sheet or fallback to workbook sheet
    def get_target_ws(file_bytes, sheet_name):
        if file_bytes:
            temp_wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
            return temp_wb.active
        return find_sheet(wb, sheet_name, required=False)

    price_ws = get_target_ws(price_bytes, "Price Sheet")
    category_ws = get_target_ws(category_bytes, "Category sheet")
    size_chart_ws = get_target_ws(size_chart_bytes, "Size chart")
    stock_ws = find_sheet(wb, "Stock sheet", required=False)

    if price_ws is None:
        raise ConversionError("Price Sheet is required either inside the main workbook or uploaded separately.")
    if category_ws is None:
        raise ConversionError("Category Sheet is required either inside the main workbook or uploaded separately.")
    if size_chart_ws is None:
        raise ConversionError("Size Chart Sheet is required either inside the main workbook or uploaded separately.")

    # Extract dynamic headers from Sample Output Sheet if provided
    custom_headings = None
    if sample_output_bytes:
        sample_wb = load_workbook(io.BytesIO(sample_output_bytes), data_only=True)
        sample_ws = sample_wb.active
        custom_headings = [val(sample_ws, 1, c) for c in range(1, sample_ws.max_column + 1) if val(sample_ws, 1, c) != ""]

    output = run_conversion(
        input_ws, price_ws, category_ws, size_chart_ws,
        stock_ws=stock_ws, 
        keep_debug_writes=keep_debug_writes,
        progress_callback=progress_callback,
        custom_headings=custom_headings
    )

    out_wb = output.to_workbook()
    buf = io.BytesIO()
    out_wb.save(buf)
    buf.seek(0)
    return buf.read()
