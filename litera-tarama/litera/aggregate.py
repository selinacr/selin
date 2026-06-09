"""Kaynaklardan gelen kayıtları tekilleştirir (dedup) ve birleştirir.

Aynı yayın birden çok veritabanından gelebilir; DOI varsa DOI'ye, yoksa
normalize edilmiş başlığa göre eşlenir ve alanlar tamamlayıcı biçimde birleştirilir.
"""

from __future__ import annotations

import re

from .models import DIGER, Paper


def _norm_title(title: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _key(p: Paper) -> tuple[str, str]:
    if p.doi:
        return ("doi", p.doi.lower())
    return ("title", _norm_title(p.title))


def _combine(a: Paper, b: Paper) -> Paper:
    """``b``'deki tamamlayıcı bilgiyi ``a`` üzerine işler (a yerinde güncellenir)."""
    a.sources = sorted(set(a.sources + b.sources))
    if not a.abstract and b.abstract:
        a.abstract = b.abstract
    if not a.tldr and b.tldr:
        a.tldr = b.tldr
    if not a.venue and b.venue:
        a.venue = b.venue
    if not a.doi and b.doi:
        a.doi = b.doi
    if not a.year and b.year:
        a.year = b.year
    if not a.url and b.url:
        a.url = b.url
    if (b.citations or 0) > (a.citations or 0):
        a.citations = b.citations
    if len(b.authors) > len(a.authors):
        a.authors = b.authors
    if not a.concepts and b.concepts:
        a.concepts = b.concepts
    # 'diğer' türünü daha belirgin bir türle değiştir
    if a.pub_type == DIGER and b.pub_type != DIGER:
        a.pub_type = b.pub_type
    return a


def merge_papers(papers: list[Paper]) -> list[Paper]:
    merged: dict[tuple[str, str], Paper] = {}
    for p in papers:
        k = _key(p)
        if k in merged:
            _combine(merged[k], p)
        else:
            merged[k] = p
    out = list(merged.values())
    out.sort(key=lambda p: ((p.citations or 0), (p.year or 0)), reverse=True)
    return out
