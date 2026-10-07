"""Saat başı çalışan toplama döngüsü.

Ek bağımlılık istemediği için basit bir arka plan iş parçacığı kullanılır: bir sonraki
tam saate kadar bekler, senkronu çalıştırır, tekrar bekler. Süreç kapanırsa son senkron
zamanı veritabanında kaldığı için tekrar başlatıldığında kaldığı yerden devam eder.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from . import senkronize

gunlukcu = logging.getLogger("yayin_paneli.zamanlayici")


def sonraki_tam_saat(simdi: datetime | None = None) -> datetime:
    simdi = simdi or datetime.now(timezone.utc)
    return (simdi + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


class Zamanlayici:
    def __init__(self, depo, aralik_dk: int | None = None, hemen: bool = False):
        self.depo = depo
        self.aralik_dk = aralik_dk or int(depo.ayarlar().get("senk_aralik_dk") or 60)
        self.hemen = hemen
        self._dur = threading.Event()
        self._is: threading.Thread | None = None
        self.son_sonuc: list[dict] = []

    def _bekleme_saniyesi(self) -> float:
        if self.aralik_dk == 60:
            return max(30.0, (sonraki_tam_saat() - datetime.now(timezone.utc)).total_seconds())
        return self.aralik_dk * 60

    def _dongu(self) -> None:
        if self.hemen:
            self.bir_tur()
        while not self._dur.wait(self._bekleme_saniyesi()):
            self.bir_tur()

    def bir_tur(self) -> list[dict]:
        try:
            self.son_sonuc = senkronize(self.depo)
        except Exception as hata:  # pragma: no cover - döngü ayakta kalmalı
            gunlukcu.exception("Senkron turu başarısız: %s", hata)
            self.son_sonuc = [{"durum": "hata", "mesaj": str(hata)}]
        return self.son_sonuc

    def basla(self) -> None:
        if self._is and self._is.is_alive():
            return
        self._dur.clear()
        self._is = threading.Thread(target=self._dongu, name="yayin-paneli-senk", daemon=True)
        self._is.start()

    def dur(self) -> None:
        self._dur.set()
        if self._is:
            self._is.join(timeout=5)

    @property
    def calisiyor(self) -> bool:
        return bool(self._is and self._is.is_alive())
