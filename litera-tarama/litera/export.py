"""Matris (CSV/Excel) dışa aktarımı. Pandas/openpyxl yalnızca burada import edilir."""

from __future__ import annotations

import csv
import io

from .models import Paper

COLUMNS = [
    "Başlık", "Yazarlar", "Yıl", "Tür", "Yayın Yeri",
    "Atıf", "Kaynak DB", "DOI", "URL", "Anahtar Kavramlar", "Özet",
]


def to_records(papers: list[Paper]) -> list[dict]:
    return [p.to_record() for p in papers]


def to_dataframe(papers: list[Paper]):
    import pandas as pd  # ağır bağımlılık — yerel import

    return pd.DataFrame(to_records(papers), columns=COLUMNS)


def csv_bytes(papers: list[Paper]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader()
    for rec in to_records(papers):
        writer.writerow(rec)
    return buf.getvalue().encode("utf-8-sig")  # Excel'de Türkçe için BOM


def excel_bytes(papers: list[Paper]) -> bytes:
    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        to_dataframe(papers).to_excel(writer, index=False, sheet_name="Literatür")
    return buf.getvalue()
