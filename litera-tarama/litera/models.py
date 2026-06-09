"""Ortak veri modelleri ve yayın türü normalizasyonu.

Tüm kaynak eklentileri (OpenAlex, Crossref, Semantic Scholar, arXiv) sonuçlarını
buradaki ``Paper`` modeline çevirir; böylece birleştirme, özetleme ve raporlama
katmanları tek tip veriyle çalışır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Kanonik (Türkçe) yayın türleri -----------------------------------------
MAKALE = "makale"
BILDIRI = "bildiri"
TEZ = "tez"
ONBASKI = "önbaskı"
KITAP = "kitap"
DERLEME = "derleme"
DIGER = "diğer"

TUM_TURLER = [MAKALE, BILDIRI, TEZ, ONBASKI, KITAP, DERLEME, DIGER]


def normalize_type(raw: str | None) -> str:
    """Kaynağa özgü tür etiketini kanonik Türkçe türe eşler."""
    if not raw:
        return DIGER
    r = str(raw).lower()
    if "dissertation" in r or "thesis" in r or "tez" in r:
        return TEZ
    if "proceedings" in r or "conference" in r or "bildiri" in r:
        return BILDIRI
    if "preprint" in r or "posted-content" in r or "posted content" in r:
        return ONBASKI
    if "review" in r:
        return DERLEME
    if "book" in r or "monograph" in r or "chapter" in r:
        return KITAP
    if "journal" in r or "journalarticle" in r or r == "article":
        return MAKALE
    return DIGER


def abstract_from_inverted_index(inv: dict | None) -> str | None:
    """OpenAlex'in ters-indeks (inverted index) abstract'ını düz metne çevirir."""
    if not inv:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    text = " ".join(word for _, word in positions)
    return text or None


def strip_tags(text: str | None) -> str | None:
    """Crossref'in JATS-XML abstract'ından etiketleri temizler."""
    if not text:
        return None
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean or None


def clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "").strip().lower() or None


@dataclass
class Paper:
    """Tek bir yayının normalize edilmiş kaydı."""

    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    pub_type: str = DIGER
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    tldr: str | None = None
    citations: int | None = None
    source: str = ""               # kaydı ilk üreten veritabanı
    concepts: list[str] = field(default_factory=list)
    raw_type: str | None = None    # kaynaktaki orijinal tür etiketi (izlenebilirlik)
    sources: list[str] = field(default_factory=list)  # birleşmeden sonra tüm kaynaklar

    def __post_init__(self) -> None:
        if not self.sources and self.source:
            self.sources = [self.source]
        self.doi = clean_doi(self.doi)

    # --- yardımcılar ---------------------------------------------------------
    @property
    def authors_str(self) -> str:
        if not self.authors:
            return "—"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return ", ".join(self.authors[:3]) + f" ve diğerleri (+{len(self.authors) - 3})"

    @property
    def summary_text(self) -> str | None:
        """Özet için en iyi kısa metin: önce TLDR, sonra abstract'ın ilk cümleleri."""
        if self.tldr:
            return self.tldr
        if self.abstract:
            cumleler = re.split(r"(?<=[.!?])\s+", self.abstract)
            return " ".join(cumleler[:2]).strip()
        return None

    def to_record(self) -> dict:
        """Matris (CSV/Excel) için düz sözlük."""
        return {
            "Başlık": self.title,
            "Yazarlar": "; ".join(self.authors) if self.authors else "",
            "Yıl": self.year or "",
            "Tür": self.pub_type,
            "Yayın Yeri": self.venue or "",
            "Atıf": self.citations if self.citations is not None else "",
            "Kaynak DB": "+".join(self.sources),
            "DOI": self.doi or "",
            "URL": self.url or "",
            "Anahtar Kavramlar": "; ".join(self.concepts),
            "Özet": self.summary_text or "",
        }
