"""Semantic Scholar kaynağı — ücretsiz, anahtarsız; hazır TLDR özetleri sağlar.

Not: Anahtarsız kullanımda hız sınırı serttir (429). http_util geri çekilmeli
yeniden deneme uygular; yine de yoğun kullanımda boş dönebilir, bu durum tarama
sonucunda 'kaynak hatası' olarak raporlanır (çökme olmaz).
"""

from __future__ import annotations

from ..http_util import get_json
from ..models import Paper, normalize_type
from .base import SourceAdapter

BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = (
    "title,year,authors,abstract,tldr,venue,"
    "publicationTypes,externalIds,citationCount,url"
)


class SemanticScholarSource(SourceAdapter):
    name = "semantic_scholar"
    label = "Semantic Scholar"

    def search(self, query, *, year_from=None, year_to=None, limit=50):
        params = {
            "query": query,
            "limit": min(max(limit, 1), 100),
            "fields": FIELDS,
        }
        if year_from and year_to:
            params["year"] = f"{year_from}-{year_to}"
        elif year_from:
            params["year"] = f"{year_from}-"
        elif year_to:
            params["year"] = f"-{year_to}"

        data = get_json(BASE, params=params)
        return [self._parse(p) for p in data.get("data", [])]

    @staticmethod
    def _parse(p: dict) -> Paper:
        authors = [a.get("name") for a in (p.get("authors") or []) if a.get("name")]
        types = p.get("publicationTypes") or []
        raw_type = types[0] if types else None
        tldr_obj = p.get("tldr") or {}
        doi = (p.get("externalIds") or {}).get("DOI")

        return Paper(
            title=p.get("title") or "(başlıksız)",
            authors=authors,
            year=p.get("year"),
            venue=p.get("venue"),
            pub_type=normalize_type(raw_type),
            doi=doi,
            url=p.get("url"),
            abstract=p.get("abstract"),
            tldr=tldr_obj.get("text"),
            citations=p.get("citationCount"),
            source=SemanticScholarSource.name,
            concepts=[],
            raw_type=raw_type,
        )
