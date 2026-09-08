import os
import tempfile

import streamlit as st
import datanorm_parser as dp


def to_bytes(export_func, df, suffix):
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        path = tmp.name
    export_func(df, path)
    with open(path, "rb") as f:
        data = f.read()
    os.remove(path)
    return data

st.set_page_config(page_title="DATANORM Toolkit", layout="wide")
st.title("DATANORM Toolkit")

uploaded_files = st.file_uploader(
    "Upload DATANORM files (article master, groups, discounts, price updates)",
    accept_multiple_files=True,
)

encoding_label = st.selectbox("Encoding", list(dp.ENCODING_CHOICES.keys()))
encoding_override = dp.ENCODING_CHOICES[encoding_label]

if st.button("Parse"):
    if not uploaded_files:
        st.warning("Upload at least one file first.")
    else:
        all_records = []
        all_warnings = []

        for uf in uploaded_files:
            raw = uf.read()
            text, encoding, enc_warnings = dp.decode_file(raw, encoding_override)
            records, parse_warnings = dp.parse_file(uf.name, text)
            all_records.extend(records)
            all_warnings.extend(enc_warnings + parse_warnings)

        df, merge_warnings = dp.merge_catalog(all_records)
        all_warnings.extend(merge_warnings)

        st.session_state["df"] = df
        st.session_state["warnings"] = all_warnings

if "df" in st.session_state:
    df = st.session_state["df"]
    warnings = st.session_state["warnings"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Articles", len(df))
    col2.metric("Groups", df["group"].nunique() if not df.empty else 0)
    col3.metric("Discontinued", (df["status"] == "discontinued").sum() if not df.empty else 0)
    col4.metric("Warnings", len(warnings))

    if warnings:
        with st.expander(f"Warnings ({len(warnings)})"):
            for w in warnings:
                st.write(w)

    st.dataframe(df, use_container_width=True)

    st.subheader("Look up a product")
    col_a, col_b = st.columns(2)
    article_query = col_a.text_input("Article number")
    group_options = ["All"] + sorted(df["group"].unique().tolist()) if not df.empty else ["All"]
    group_query = col_b.selectbox("Group", group_options)

    if article_query or group_query != "All":
        filtered = df
        if article_query:
            filtered = filtered[filtered["artnr"].str.contains(article_query, case=False, na=False)]
        if group_query != "All":
            filtered = filtered[filtered["group"] == group_query]

        if filtered.empty:
            st.info("No matching products.")
        else:
            for _, row in filtered.iterrows():
                with st.container(border=True):
                    st.markdown(f"**{row['artnr']} — {row['desc']}**")
                    st.write(f"Group: {row['group']} | Unit: {row['unit']} | Price: {row['price']} | Status: {row['status']}")
                    if row["long_text"]:
                        st.write(row["long_text"])
                    if row["tiers"]:
                        st.write(f"Tiered pricing: {row['tiers']}")

    st.subheader("Download")
    col_x, col_c, col_j, col_s = st.columns(4)
    col_x.download_button("Excel", to_bytes(dp.export_excel, df, ".xlsx"), file_name="datanorm_catalog.xlsx")
    col_c.download_button("CSV", to_bytes(dp.export_csv, df, ".csv"), file_name="datanorm_catalog.csv")
    col_j.download_button("JSON", to_bytes(dp.export_json, df, ".json"), file_name="datanorm_catalog.json")
    col_s.download_button("SQLite", to_bytes(dp.export_sqlite, df, ".db"), file_name="datanorm_catalog.db")