"""Kaynak eklentisi taban sınıfı.

Yeni bir veritabanı eklemek için bu sınıftan türetip ``search`` metodunu yazmak
yeterli. IEEE/Scopus/WoS/Scholar gibi anahtar gerektiren kaynaklar ileride aynı
arayüzle eklenebilir (``requires_key = True``).
"""

from __future__ import annotations

from ..models import Paper


class SourceAdapter:
    name: str = "base"
    label: str = "Base"
    requires_key: bool = False

    def __init__(self, **options) -> None:
        self.options = options

    def available(self) -> bool:
        """Anahtar gerektiren kaynaklar için: yapılandırma tamam mı?"""
        return True

    def search(
        self,
        query: str,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
        limit: int = 50,
    ) -> list[Paper]:
        raise NotImplementedError
