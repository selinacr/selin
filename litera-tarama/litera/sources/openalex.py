"""OpenAlex kaynağı — ücretsiz, anahtarsız, en geniş kapsam (IEEE/Scopus/WoS
içeriğinin büyük kısmını da indeksler)."""

from __future__ import annotations

from ..http_util import CONTACT_EMAIL, get_json
from ..models import Paper, abstract_from_inverted_index, normalize_type
from .base import SourceAdapter

BASE = "https://api.openalex.org/works"


class OpenAlexSource(SourceAdapter):
    name = "openalex"
    label = "OpenAlex"

    def search(self, query, *, year_from=None, year_to=None, limit=50):
        params = {
            "search": query,
            "per-page": min(max(limit, 1), 200),
            "mailto": CONTACT_EMAIL,
        }
        filters = []
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")
        if filters:
            params["filter"] = ",".join(filters)

        data = get_json(BASE, params=params)
        return [self._parse(w) for w in data.get("results", [])]

    @staticmethod
    def _parse(w: dict) -> Paper:
        authors = [
            a.get("author", {}).get("display_name")
            for a in w.get("authorships", [])
        ]
        authors = [a for a in authors if a]

        primary = w.get("primary_location") or {}
        src = primary.get("source") or {}
        venue = src.get("display_name")

        concepts = [
            c.get("display_name")
            for c in (w.get("concepts") or [])[:6]
            if c.get("display_name")
        ]

        raw_type = w.get("type") or w.get("type_crossref")
        doi = w.get("doi")
        url = doi or primary.get("landing_page_url") or w.get("id")

        return Paper(
            title=w.get("display_name") or w.get("title") or "(başlıksız)",
            authors=authors,
            year=w.get("publication_year"),
            venue=venue,
            pub_type=normalize_type(raw_type),
            doi=doi,
            url=url,
            abstract=abstract_from_inverted_index(w.get("abstract_inverted_index")),
            tldr=None,
            citations=w.get("cited_by_count"),
            source=OpenAlexSource.name,
            concepts=concepts,
            raw_type=raw_type,
        )
