"""Kaynak eklenti kaydı.

Yeni kaynak eklemek: sınıfı yaz, REGISTRY'ye ekle. Varsayılan (ücretsiz/anahtarsız)
çekirdek DEFAULT_SOURCES içinde.
"""

from __future__ import annotations

from .arxiv import ArxivSource
from .base import SourceAdapter
from .crossref import CrossrefSource
from .openalex import OpenAlexSource
from .semantic_scholar import SemanticScholarSource

REGISTRY: dict[str, type[SourceAdapter]] = {
    cls.name: cls
    for cls in (OpenAlexSource, CrossrefSource, SemanticScholarSource, ArxivSource)
}

# Ücretsiz / anahtarsız çekirdek — kullanıcı seçimi gereği aktif olanlar.
DEFAULT_SOURCES: list[str] = ["openalex", "crossref", "semantic_scholar", "arxiv"]


def build_sources(names: list[str] | None = None) -> list[SourceAdapter]:
    selected = names or DEFAULT_SOURCES
    return [REGISTRY[n]() for n in selected if n in REGISTRY]


def source_labels() -> dict[str, str]:
    return {name: cls.label for name, cls in REGISTRY.items()}
