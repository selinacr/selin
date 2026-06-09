"""arXiv kaynağı — ücretsiz, anahtarsız; önbaskı (preprint) kapsamı.

arXiv API'si Atom (XML) döner; standart kütüphane ile ayrıştırılır (ek bağımlılık yok).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..http_util import get_text
from ..models import ONBASKI, Paper
from .base import SourceAdapter

BASE = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivSource(SourceAdapter):
    name = "arxiv"
    label = "arXiv"

    def search(self, query, *, year_from=None, year_to=None, limit=50):
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(max(limit, 1), 100),
            "sortBy": "relevance",
        }
        text = get_text(BASE, params=params)
        root = ET.fromstring(text)
        papers = []
        for entry in root.findall("atom:entry", NS):
            paper = self._parse(entry)
            if paper is None:
                continue
            if year_from and paper.year and paper.year < year_from:
                continue
            if year_to and paper.year and paper.year > year_to:
                continue
            papers.append(paper)
        return papers

    @staticmethod
    def _text(entry, tag):
        el = entry.find(tag, NS)
        return el.text.strip() if el is not None and el.text else None

    @classmethod
    def _parse(cls, entry) -> Paper | None:
        title = cls._text(entry, "atom:title")
        if not title:
            return None
        title = " ".join(title.split())

        authors = [
            a.text.strip()
            for a in entry.findall("atom:author/atom:name", NS)
            if a.text
        ]

        published = cls._text(entry, "atom:published")
        year = int(published[:4]) if published and published[:4].isdigit() else None

        abstract = cls._text(entry, "atom:summary")
        if abstract:
            abstract = " ".join(abstract.split())

        url = cls._text(entry, "atom:id")
        doi = cls._text(entry, "arxiv:doi")

        return Paper(
            title=title,
            authors=authors,
            year=year,
            venue="arXiv",
            pub_type=ONBASKI,
            doi=doi,
            url=url,
            abstract=abstract,
            tldr=None,
            citations=None,
            source=cls.name,
            concepts=[],
            raw_type="preprint",
        )
