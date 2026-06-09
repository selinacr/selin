"""Crossref kaynağı — ücretsiz, anahtarsız; DOI'li yayınlar için güçlü metadata."""

from __future__ import annotations

from ..http_util import CONTACT_EMAIL, get_json
from ..models import Paper, normalize_type, strip_tags
from .base import SourceAdapter

BASE = "https://api.crossref.org/works"
SELECT = (
    "DOI,title,author,issued,container-title,type,"
    "is-referenced-by-count,abstract,URL,subject"
)


class CrossrefSource(SourceAdapter):
    name = "crossref"
    label = "Crossref"

    def search(self, query, *, year_from=None, year_to=None, limit=50):
        params = {
            "query": query,
            "rows": min(max(limit, 1), 100),
            "mailto": CONTACT_EMAIL,
            "select": SELECT,
        }
        filters = []
        if year_from:
            filters.append(f"from-pub-date:{year_from}-01-01")
        if year_to:
            filters.append(f"until-pub-date:{year_to}-12-31")
        if filters:
            params["filter"] = ",".join(filters)

        data = get_json(BASE, params=params)
        items = (data.get("message") or {}).get("items", [])
        return [self._parse(it) for it in items]

    @staticmethod
    def _year(item: dict) -> int | None:
        issued = (item.get("issued") or {}).get("date-parts") or []
        if issued and issued[0]:
            return issued[0][0]
        return None

    @classmethod
    def _parse(cls, item: dict) -> Paper:
        title_list = item.get("title") or []
        title = title_list[0] if title_list else "(başlıksız)"

        authors = []
        for a in item.get("author", []) or []:
            name = " ".join(p for p in (a.get("given"), a.get("family")) if p)
            if name:
                authors.append(name)

        container = item.get("container-title") or []
        venue = container[0] if container else None

        return Paper(
            title=title,
            authors=authors,
            year=cls._year(item),
            venue=venue,
            pub_type=normalize_type(item.get("type")),
            doi=item.get("DOI"),
            url=item.get("URL"),
            abstract=strip_tags(item.get("abstract")),
            tldr=None,
            citations=item.get("is-referenced-by-count"),
            source=cls.name,
            concepts=(item.get("subject") or [])[:6],
            raw_type=item.get("type"),
        )
