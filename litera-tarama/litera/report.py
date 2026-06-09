"""Markdown özet rapor üretimi."""

from __future__ import annotations

from .models import Paper


def _bar(n: int, max_n: int, width: int = 24) -> str:
    if max_n <= 0:
        return ""
    return "█" * max(1, round(n / max_n * width))


def _paper_block(p: Paper, idx: int) -> str:
    lines = [f"**{idx}. {p.title}**", ""]
    meta = []
    if p.authors:
        meta.append(p.authors_str)
    if p.year:
        meta.append(str(p.year))
    meta.append(p.pub_type)
    if p.venue:
        meta.append(f"*{p.venue}*")
    if p.citations:
        meta.append(f"{p.citations} atıf")
    lines.append(" · ".join(meta))
    if p.summary_text:
        lines += ["", f"> {p.summary_text}"]
    link = p.url or (f"https://doi.org/{p.doi}" if p.doi else None)
    if link:
        lines += ["", f"[Bağlantı]({link})  ·  kaynak: {'+'.join(p.sources)}"]
    return "\n".join(lines)


def build_markdown(query: str, result, summary: dict) -> str:
    s = summary
    out: list[str] = []
    out.append(f"# Literatür Tarama Raporu: «{query}»")
    out.append("")
    out.append(f"*Oluşturulma:* {result.timestamp}  ·  *Toplam (tekilleştirilmiş):* **{s['total']}** çalışma")

    # Kaynak başına ham sayılar + hatalar
    src_parts = [f"{k}: {v}" for k, v in result.per_source_counts.items()]
    out.append(f"*Sorgulanan kaynaklar:* {', '.join(src_parts)}")
    if result.errors:
        err_parts = [f"{k} ({v})" for k, v in result.errors.items()]
        out.append(f"> ⚠️ Erişilemeyen/hatalı kaynaklar: {', '.join(err_parts)}")
    out.append("")

    if s["total"] == 0:
        out.append("Bu sorgu için kaynaklarda sonuç bulunamadı.")
        return "\n".join(out)

    # Tür dağılımı
    out.append("## Tür Dağılımı")
    out.append("")
    out.append("| Tür | Adet |")
    out.append("|-----|------|")
    for t, n in s["by_type"].items():
        out.append(f"| {t} | {n} |")
    out.append("")

    # Yıl dağılımı (grafik)
    if s["by_year"]:
        out.append("## Yıllara Göre Dağılım")
        out.append(f"*Tarih aralığı:* {s['year_min']}–{s['year_max']}")
        out.append("")
        out.append("```")
        max_n = max(s["by_year"].values())
        for yr, n in s["by_year"].items():
            out.append(f"{yr}  {_bar(n, max_n)} {n}")
        out.append("```")
        out.append("")

    # En çok atıf alan çalışmalar
    if s["top_cited"]:
        out.append("## Öne Çıkan Çalışmalar (en çok atıf alan)")
        out.append("")
        for i, p in enumerate(s["top_cited"], 1):
            out.append(_paper_block(p, i))
            out.append("")

    # En güncel çalışmalar
    if s["recent"]:
        out.append("## En Güncel Çalışmalar")
        out.append("")
        for i, p in enumerate(s["recent"], 1):
            out.append(_paper_block(p, i))
            out.append("")

    # Sık geçen kavramlar
    if s["top_concepts"]:
        out.append("## Sık Geçen Anahtar Kavramlar")
        out.append("")
        out.append(", ".join(f"{c} ({n})" for c, n in s["top_concepts"]))
        out.append("")

    # Üretken yazarlar
    if s["top_authors"]:
        out.append("## En Çok Çıkan Yazarlar")
        out.append("")
        out.append(", ".join(f"{a} ({n})" for a, n in s["top_authors"]))
        out.append("")

    out.append("---")
    out.append("*Bu rapor litera-tarama tarafından otomatik üretildi; her çalıştırmada kaynaklar sıfırdan sorgulanır.*")
    return "\n".join(out)
