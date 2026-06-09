"""Orkestrasyon: tüm seçili kaynakları SIFIRDAN, eşzamanlı sorgular; birleştirir."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

from .aggregate import merge_papers
from .models import Paper
from .sources import build_sources
from .summarize import summarize


@dataclass
class SearchResult:
    query: str
    papers: list[Paper]
    per_source_counts: dict[str, int]
    errors: dict[str, str]
    summary: dict
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


def run_search(
    query: str,
    *,
    sources: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    per_source_limit: int = 50,
    progress=None,
) -> SearchResult:
    """Her çağrıda kaynakları baştan tarar (önbellek yok = her zaman güncel)."""
    adapters = build_sources(sources)
    raw: list[Paper] = []
    counts: dict[str, int] = {}
    errors: dict[str, str] = {}

    def work(adapter):
        return adapter.name, adapter.search(
            query, year_from=year_from, year_to=year_to, limit=per_source_limit
        )

    with ThreadPoolExecutor(max_workers=max(1, len(adapters))) as ex:
        futures = {ex.submit(work, a): a for a in adapters}
        for fut in as_completed(futures):
            adapter = futures[fut]
            try:
                name, papers = fut.result()
                raw.extend(papers)
                counts[name] = len(papers)
            except Exception as exc:  # bir kaynağın hatası diğerlerini düşürmesin
                errors[adapter.name] = str(exc)
                counts[adapter.name] = 0
            if progress:
                progress(adapter.name)

    merged = merge_papers(raw)
    summary = summarize(merged)
    return SearchResult(
        query=query,
        papers=merged,
        per_source_counts=counts,
        errors=errors,
        summary=summary,
    )
