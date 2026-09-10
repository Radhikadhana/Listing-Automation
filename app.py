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
            guess_gender_article_group_column(sct_cols_available)
            or guess_composite_key_column(sct_cols_available)
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
