"""SQLite deposu: tüm veri tek dosyada, JSON alanlar hâlinde tutulur."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

VARSAYILAN_YOL = Path(__file__).resolve().parent.parent / "veri" / "panel.db"

ALANLAR = {
    "kurum_kayitlari": list, "personel": list, "adjunct": list, "ad_esleme": dict,
    "quartiller": dict, "metrikler": list,
    "aylik_kayitlar": list, "kurallar": dict, "duzeltmeler": dict,
}


class Depo:
    def __init__(self, yol: str | Path = VARSAYILAN_YOL):
        self.yol = Path(yol)
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        with self._baglanti() as db:
            db.execute("CREATE TABLE IF NOT EXISTS veri (anahtar TEXT PRIMARY KEY, icerik TEXT)")

    def _baglanti(self):
        return sqlite3.connect(self.yol)

    def oku(self, anahtar: str):
        varsayilan = ALANLAR.get(anahtar, list)()
        with self._baglanti() as db:
            satir = db.execute("SELECT icerik FROM veri WHERE anahtar = ?", (anahtar,)).fetchone()
        if not satir:
            return varsayilan
        try:
            return json.loads(satir[0])
        except json.JSONDecodeError:
            return varsayilan

    def yaz(self, anahtar: str, icerik) -> None:
        with self._baglanti() as db:
            db.execute("INSERT INTO veri (anahtar, icerik) VALUES (?, ?) "
                       "ON CONFLICT(anahtar) DO UPDATE SET icerik = excluded.icerik",
                       (anahtar, json.dumps(icerik, ensure_ascii=False)))

    def hepsini_oku(self) -> dict:
        return {anahtar: self.oku(anahtar) for anahtar in ALANLAR}

    def kayitlari_ekle(self, yeniler: list[dict], kaynak: str, yil: int | None = None) -> int:
        """Aynı kaynağın aynı yılı tazelenir, diğer kaynaklar korunur."""
        mevcut = self.oku("kurum_kayitlari")
        yillar = {y for y in ((k.get("yil") for k in yeniler) if yil is None else [yil]) if y}
        kalanlar = [k for k in mevcut
                    if not ((k.get("kaynak") or "WoS") == kaynak and k.get("yil") in yillar)]
        birlesik = [*kalanlar, *yeniler]
        self.yaz("kurum_kayitlari", birlesik)
        return len(birlesik)

    def ay_ekle(self, donem: str, kayitlar: list[dict]) -> int:
        mevcut = [k for k in self.oku("aylik_kayitlar") if k.get("donem") != donem]
        birlesik = [*mevcut, *kayitlar]
        self.yaz("aylik_kayitlar", birlesik)
        return len(birlesik)

    def ay_sil(self, donem: str) -> None:
        self.yaz("aylik_kayitlar", [k for k in self.oku("aylik_kayitlar") if k.get("donem") != donem])

    def quartil_ekle(self, yil: int, harita: dict[str, str]) -> None:
        mevcut = self.oku("quartiller")
        mevcut[str(yil)] = harita
        self.yaz("quartiller", mevcut)

    def metrik_ekle(self, yeniler: list[dict]) -> int:
        harita = {k.get("kimlik") or k["ad"]: k for k in self.oku("metrikler")}
        for kayit in yeniler:
            harita[kayit.get("kimlik") or kayit["ad"]] = kayit
        birlesik = list(harita.values())
        self.yaz("metrikler", birlesik)
        return len(birlesik)
