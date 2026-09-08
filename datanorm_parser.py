from typing import List, Optional, Tuple
import pandas as pd
import sqlite3

ENCODING_CHOICES = {
    "Auto-detect (recommended)": None,
    "CP850 (DOS Western Europe)": "cp850",
    "UTF-8": "utf-8",
    "Windows-1252 / Latin-1": "cp1252",
}

# Step 2: encoding detection + manual override

def detect_encoding(raw: bytes, override: Optional[str] = None) -> Tuple[str, List[str]]:
    warnings: List[str] = []

    if override:
        try:
            raw.decode(override)
        except UnicodeDecodeError as e:
            warnings.append(f"Manual encoding '{override}' failed: {e}")
        return override, warnings

    try:
        raw.decode("utf-8")
        return "utf-8", warnings
    except UnicodeDecodeError:
        pass

    try:
        raw.decode("cp850")
        return "cp850", warnings
    except UnicodeDecodeError:
        pass

    warnings.append("Falling back to Latin-1 — check umlauts in output.")
    return "latin-1", warnings


def decode_file(raw: bytes, override: Optional[str] = None) -> Tuple[str, str, List[str]]:
    encoding, warnings = detect_encoding(raw, override)
    text = raw.decode(encoding, errors="replace")
    if "�" in text:
        warnings.append(f"Some bytes could not decode as {encoding}.")
    return text, encoding, warnings


# Step 3: classify_file(filename)

def classify_file(filename: str) -> str:
    name = filename.upper()
    if "WRG" in name:
        return "groups"
    if "RAB" in name:
        return "discounts"
    if "PREIS" in name:
        return "price_update"
    if "TEXT" in name:
        return "text"
    return "article"


#Step 4: parse_line(satzart, fields)

def split_line(line: str) -> Tuple[str, List[str]]:
    parts = line.split(";")
    return parts[0], parts[1:]


def parse_line(satzart: str, fields: List[str]) -> Optional[dict]:
    if satzart in ("A", "B"):
        artnr, _, group_code, desc, _, unit, price, _, flag = fields
        return {"type": "article", "artnr": artnr, "group_code": group_code,
                "desc": desc, "unit": unit, "price": price, "flag": flag}

    if satzart in ("T", "E"):
        artnr, _, text = fields
        return {"type": "text", "artnr": artnr, "text": text}

    if satzart == "Z":
        artnr, _, *tier_fields = fields
        tiers = list(zip(tier_fields[0::2], tier_fields[1::2]))
        return {"type": "tier", "artnr": artnr, "tiers": tiers}

    if satzart == "S":
        code, _, name = fields
        return {"type": "group", "code": code, "name": name}

    if satzart == "R":
        code, _, name, percent = fields
        return {"type": "discount", "code": code, "name": name, "percent": percent}

    if satzart == "P":
        artnr, _, price = fields
        return {"type": "price_update", "artnr": artnr, "price": price}

    return None


# Step 5: warnings collection

def parse_file(filename: str, text: str) -> Tuple[List[dict], List[str]]:
    records: List[dict] = []
    warnings: List[str] = []

    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        satzart, fields = split_line(line)

        try:
            record = parse_line(satzart, fields)
        except ValueError as e:
            warnings.append(f"{filename} line {i}: could not parse '{satzart}' record ({e}) — skipped")
            continue

        if record is None:
            warnings.append(f"{filename} line {i}: unrecognized record type '{satzart}' — skipped")
            continue

        record["_source_file"] = filename
        record["_line"] = i
        records.append(record)

    return records, warnings


# Step 6: merge_catalog(parsed_files)

def merge_catalog(all_records: List[dict]) -> Tuple[pd.DataFrame, List[str]]:
    warnings: List[str] = []
    groups = {}
    articles = {}

    for r in all_records:
        if r["type"] == "group":
            groups[r["code"]] = r["name"]

    for r in all_records:
        if r["type"] == "article":
            articles[r["artnr"]] = {
                "artnr": r["artnr"],
                "group": groups.get(r["group_code"], f"?({r['group_code']})"),
                "desc": r["desc"],
                "unit": r["unit"],
                "price": r["price"].replace(",", "."),
                "status": "discontinued" if r["flag"] == "X" else "active",
                "long_text": "",
                "tiers": "",
            }

    for r in all_records:
        if r["type"] == "text":
            if r["artnr"] in articles:
                articles[r["artnr"]]["long_text"] = r["text"]
            else:
                warnings.append(f"{r['_source_file']} line {r['_line']}: text for unknown article {r['artnr']}")

        elif r["type"] == "tier":
            if r["artnr"] in articles:
                tiers = ", ".join(f"{qty}+ @ {price.replace(',', '.')}" for qty, price in r["tiers"])
                articles[r["artnr"]]["tiers"] = tiers
            else:
                warnings.append(f"{r['_source_file']} line {r['_line']}: tier pricing for unknown article {r['artnr']}")

        elif r["type"] == "price_update":
            if r["artnr"] in articles:
                articles[r["artnr"]]["price"] = r["price"].replace(",", ".")
            else:
                warnings.append(f"{r['_source_file']} line {r['_line']}: price update for unknown article {r['artnr']}")

    df = pd.DataFrame(articles.values())
    if not df.empty:
        df = df.sort_values("artnr").reset_index(drop=True)
    return df, warnings


# Step 7-10: export_excel / export_csv / export_json / export_sqlite

def export_excel(df: pd.DataFrame, path: str) -> None:
    df.to_excel(path, index=False)


def export_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)


def export_json(df: pd.DataFrame, path: str) -> None:
    df.to_json(path, orient="records", indent=2, force_ascii=False)


def export_sqlite(df: pd.DataFrame, path: str, table_name: str = "articles") -> None:
    conn = sqlite3.connect(path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()