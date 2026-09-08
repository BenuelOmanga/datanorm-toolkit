import os
import datanorm_parser as dp
import tempfile

SAMPLE_DIR = "sample_data"
FILES = ["DATANORM.WRG", "DATANORM.001", "DATANORM.RAB", "DATPREIS.001"]


def run():
    all_records = []
    all_warnings = []

    for fname in FILES:
        path = os.path.join(SAMPLE_DIR, fname)
        raw = open(path, "rb").read()
        text, encoding, enc_warnings = dp.decode_file(raw)
        records, parse_warnings = dp.parse_file(fname, text)
        all_records.extend(records)
        all_warnings.extend(enc_warnings + parse_warnings)
        print(f"{fname}: encoding={encoding}, records={len(records)}")

    df, merge_warnings = dp.merge_catalog(all_records)
    all_warnings.extend(merge_warnings)

    print()
    print(df.to_string(index=False))
    print()
    print("warnings:", all_warnings)

    assert len(df) == 5, f"expected 5 articles, got {len(df)}"
    assert all_warnings == [], f"expected no warnings, got {all_warnings}"

    row_10001 = df[df["artnr"] == "10001"].iloc[0]
    assert row_10001["price"] == "13.50", "price update for 10001 was not applied"

    row_10005 = df[df["artnr"] == "10005"].iloc[0]
    assert row_10005["status"] == "discontinued", "X flag on 10005 was not honoured"

    tmp_dir = tempfile.gettempdir()
    out_xlsx = os.path.join(tmp_dir, "test_out.xlsx")
    out_csv = os.path.join(tmp_dir, "test_out.csv")
    out_json = os.path.join(tmp_dir, "test_out.json")
    out_db = os.path.join(tmp_dir, "test_out.db")

    dp.export_excel(df, out_xlsx)
    dp.export_csv(df, out_csv)
    dp.export_json(df, out_json)
    dp.export_sqlite(df, out_db)
    for f in [out_xlsx, out_csv, out_json, out_db]:
        assert os.path.exists(f) and os.path.getsize(f) > 0, f"{f} was not created"
    print(f"export files written to: {tmp_dir}")


if __name__ == "__main__":
    run()