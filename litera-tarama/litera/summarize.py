"""Anahtarsız özetleme: meta veri toplama + hazır TLDR/abstract derlemesi.

LLM kullanmaz. Çıktı, raporlama ve arayüzün tükettiği istatistik sözlüğüdür.
"""

from __future__ import annotations

from collections import Counter

from .models import TUM_TURLER, Paper


def summarize(papers: list[Paper], top_n: int = 10) -> dict:
    by_type = Counter(p.pub_type for p in papers)
    years = [p.year for p in papers if p.year]
    by_year = Counter(years)

    author_counter: Counter[str] = Counter()
    for p in papers:
        author_counter.update(p.authors)

    venue_counter: Counter[str] = Counter(p.venue for p in papers if p.venue)

    concept_counter: Counter[str] = Counter()
    for p in papers:
        concept_counter.update(c for c in p.concepts if c)

    source_counter: Counter[str] = Counter()
    for p in papers:
        source_counter.update(p.sources)

    top_cited = [p for p in papers if (p.citations or 0) > 0][:top_n]
    recent = sorted(
        [p for p in papers if p.year], key=lambda p: p.year, reverse=True
    )[:top_n]

    return {
        "total": len(papers),
        "by_type": {t: by_type.get(t, 0) for t in TUM_TURLER if by_type.get(t, 0)},
        "by_year": dict(sorted(by_year.items())),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "top_authors": author_counter.most_common(15),
        "top_venues": venue_counter.most_common(10),
        "top_concepts": concept_counter.most_common(20),
        "by_source": dict(source_counter),
        "top_cited": top_cited,
        "recent": recent,
    }
