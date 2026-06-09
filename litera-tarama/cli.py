"""litera-tarama — komut satırı arayüzü (test ve toplu kullanım için).

Örnek:
    python cli.py "fractional-order analog filter" --from 2018 --to 2025 \
        --out rapor.md --csv matris.csv
"""

from __future__ import annotations

import argparse
import sys

from litera.export import csv_bytes
from litera.report import build_markdown
from litera.search import run_search
from litera.sources import DEFAULT_SOURCES


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Çok kaynaklı literatür tarama")
    ap.add_argument("query", help="Anahtar kelime / konu")
    ap.add_argument("--sources", nargs="+", default=DEFAULT_SOURCES,
                    help=f"Kaynaklar (varsayılan: {' '.join(DEFAULT_SOURCES)})")
    ap.add_argument("--from", dest="year_from", type=int, default=None)
    ap.add_argument("--to", dest="year_to", type=int, default=None)
    ap.add_argument("--limit", type=int, default=50,
                    help="Kaynak başına azami kayıt")
    ap.add_argument("--out", default=None, help="Markdown rapor dosyası")
    ap.add_argument("--csv", default=None, help="CSV matris dosyası")
    args = ap.parse_args(argv)

    print(f"'{args.query}' için kaynaklar taranıyor…", file=sys.stderr)
    result = run_search(
        args.query,
        sources=args.sources,
        year_from=args.year_from,
        year_to=args.year_to,
        per_source_limit=args.limit,
        progress=lambda n: print(f"  ✓ {n}", file=sys.stderr),
    )

    s = result.summary
    print(f"\nToplam {s['total']} çalışma (tekilleştirilmiş).", file=sys.stderr)
    for t, n in s["by_type"].items():
        print(f"  {t}: {n}", file=sys.stderr)
    if result.errors:
        print(f"  hatalar: {result.errors}", file=sys.stderr)

    md = build_markdown(args.query, result, s)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Rapor yazıldı: {args.out}", file=sys.stderr)
    else:
        print(md)

    if args.csv:
        with open(args.csv, "wb") as f:
            f.write(csv_bytes(result.papers))
        print(f"Matris yazıldı: {args.csv}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
