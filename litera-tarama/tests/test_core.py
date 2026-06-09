"""Çevrimdışı testler — ağ gerektirmez (ayrıştırma, normalizasyon, birleştirme,
özet, rapor ve dışa aktarım mantığını kapsar)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from litera.aggregate import merge_papers
from litera.export import COLUMNS, csv_bytes, to_records
from litera.models import (
    BILDIRI, MAKALE, ONBASKI, TEZ, Paper,
    abstract_from_inverted_index, normalize_type, strip_tags,
)
from litera.report import build_markdown
from litera.search import SearchResult
from litera.sources.arxiv import ArxivSource
from litera.sources.crossref import CrossrefSource
from litera.sources.openalex import OpenAlexSource
from litera.sources.semantic_scholar import SemanticScholarSource
from litera.summarize import summarize


# --- tür normalizasyonu ------------------------------------------------------
def test_normalize_type():
    assert normalize_type("journal-article") == MAKALE
    assert normalize_type("proceedings-article") == BILDIRI
    assert normalize_type("Conference") == BILDIRI
    assert normalize_type("dissertation") == TEZ
    assert normalize_type("posted-content") == ONBASKI
    assert normalize_type("preprint") == ONBASKI
    assert normalize_type(None) == "diğer"
    assert normalize_type("article") == MAKALE


def test_abstract_inverted_index():
    inv = {"Fractional": [0], "order": [1], "filter": [2]}
    assert abstract_from_inverted_index(inv) == "Fractional order filter"
    assert abstract_from_inverted_index(None) is None


def test_strip_tags():
    assert strip_tags("<jats:p>Hello <b>world</b></jats:p>") == "Hello world"
    assert strip_tags(None) is None


# --- kaynak ayrıştırıcıları (sabit örneklerle) -------------------------------
def test_openalex_parse():
    w = {
        "display_name": "Fractional Filter Design",
        "publication_year": 2021,
        "type": "article",
        "doi": "https://doi.org/10.1000/XYZ",
        "cited_by_count": 12,
        "authorships": [{"author": {"display_name": "A. Yılmaz"}}],
        "primary_location": {"source": {"display_name": "IEEE TCAS"}},
        "concepts": [{"display_name": "Fractional calculus"}],
        "abstract_inverted_index": {"Tunable": [0], "roll-off": [1]},
    }
    p = OpenAlexSource._parse(w)
    assert p.title == "Fractional Filter Design"
    assert p.year == 2021
    assert p.pub_type == MAKALE
    assert p.doi == "10.1000/xyz"
    assert p.citations == 12
    assert p.venue == "IEEE TCAS"
    assert p.abstract == "Tunable roll-off"
    assert p.authors == ["A. Yılmaz"]


def test_crossref_parse():
    item = {
        "DOI": "10.1/abc",
        "title": ["Pulse Shaping"],
        "author": [{"given": "Selin", "family": "Acar"}],
        "issued": {"date-parts": [[2023, 5]]},
        "container-title": ["Conf. on Sensors"],
        "type": "proceedings-article",
        "is-referenced-by-count": 3,
        "abstract": "<jats:p>An OTA-C approach.</jats:p>",
        "URL": "http://x",
    }
    p = CrossrefSource._parse(item)
    assert p.year == 2023
    assert p.pub_type == BILDIRI
    assert p.authors == ["Selin Acar"]
    assert p.abstract == "An OTA-C approach."


def test_s2_parse():
    rec = {
        "title": "TLDR paper",
        "year": 2020,
        "authors": [{"name": "X"}],
        "tldr": {"text": "Kısa özet."},
        "publicationTypes": ["JournalArticle"],
        "externalIds": {"DOI": "10.2/q"},
        "citationCount": 7,
        "venue": "J. Filters",
        "url": "http://s2",
    }
    p = SemanticScholarSource._parse(rec)
    assert p.tldr == "Kısa özet."
    assert p.summary_text == "Kısa özet."
    assert p.pub_type == MAKALE


def test_arxiv_parse():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"
                  xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2101.00001</id>
        <title>Fractional   Order   Survey</title>
        <summary>  A   broad   review.  </summary>
        <published>2021-01-02T00:00:00Z</published>
        <author><name>R. Author</name></author>
      </entry>
    </feed>"""
    import xml.etree.ElementTree as ET
    entry = ET.fromstring(xml).find("{http://www.w3.org/2005/Atom}entry")
    p = ArxivSource._parse(entry)
    assert p.title == "Fractional Order Survey"
    assert p.abstract == "A broad review."
    assert p.year == 2021
    assert p.pub_type == ONBASKI


# --- birleştirme / dedup -----------------------------------------------------
def test_merge_by_doi():
    a = Paper(title="X", doi="10.1/a", source="openalex", citations=5,
              abstract="full abstract")
    b = Paper(title="X (v2)", doi="10.1/A", source="crossref", citations=8,
              tldr="özet")
    merged = merge_papers([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert set(m.sources) == {"openalex", "crossref"}
    assert m.citations == 8          # daha yüksek atıf alınır
    assert m.abstract == "full abstract"
    assert m.tldr == "özet"


def test_merge_by_title_when_no_doi():
    a = Paper(title="Fractional Filter!", source="arxiv")
    b = Paper(title="fractional   filter", source="openalex")
    assert len(merge_papers([a, b])) == 1


# --- özet + rapor ------------------------------------------------------------
def _sample_result():
    papers = [
        Paper(title="A", year=2021, pub_type=MAKALE, citations=10, source="openalex",
              authors=["A. Yılmaz"], venue="IEEE", concepts=["Fractional calculus"],
              tldr="özet a"),
        Paper(title="B", year=2023, pub_type=BILDIRI, citations=2, source="crossref",
              authors=["B. Demir"], venue="Conf"),
        Paper(title="C", year=2019, pub_type=TEZ, source="openalex",
              authors=["C. Kaya"]),
    ]
    s = summarize(papers)
    return SearchResult("test", papers, {"openalex": 2, "crossref": 1}, {}, s,
                        timestamp="2026-06-09T10:00:00")


def test_summarize_counts():
    r = _sample_result()
    s = r.summary
    assert s["total"] == 3
    assert s["by_type"][MAKALE] == 1
    assert s["by_type"][TEZ] == 1
    assert s["year_min"] == 2019 and s["year_max"] == 2023
    assert s["top_cited"][0].title == "A"


def test_build_markdown():
    r = _sample_result()
    md = build_markdown("test", r, r.summary)
    assert "# Literatür Tarama Raporu" in md
    assert "Tür Dağılımı" in md
    assert "Öne Çıkan Çalışmalar" in md
    assert "2019–2023" in md


def test_export_records():
    r = _sample_result()
    recs = to_records(r.papers)
    assert list(recs[0].keys()) == COLUMNS
    raw = csv_bytes(r.papers)
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM (Excel/Türkçe)
    assert b"Ba\xc5\x9fl\xc4\xb1k" in raw or "Başlık".encode("utf-8") in raw


def test_empty_report():
    s = summarize([])
    r = SearchResult("bos", [], {"openalex": 0}, {}, s, "2026-06-09T10:00:00")
    md = build_markdown("bos", r, s)
    assert "sonuç bulunamadı" in md
