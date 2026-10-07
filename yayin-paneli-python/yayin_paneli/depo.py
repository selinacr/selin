"""SQLite deposu.

Kayıtlar, dergi ve kişi metrikleri, takma adlar, onay kuyruğu ve senkron günlüğü ayrı
tablolarda tutulur. Personel listesi, adjunct listesi, aylık ödeme kayıtları ve ayarlar
gibi serbest biçimli veriler `veri(anahtar, icerik)` tablosunda JSON olarak kalır.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

VARSAYILAN_YOL = Path(__file__).resolve().parent.parent / "veri" / "panel.db"

ALANLAR = {
    "personel": list, "adjunct": list, "ad_esleme": dict,
    "aylik_kayitlar": list, "kurallar": dict, "duzeltmeler": dict, "ayarlar": dict,
}

VARSAYILAN_AYARLAR = {
    "toplama_yolu": "api",          # "api" | "tarayici"
    "kurum_sorgusu": "Dogus University",
    "wos_kurum": "Dogus University",
    "scopus_kurum_kimligi": "",
    "ilk_yil": 2022,
    "senk_aralik_dk": 60,
}

SEMA = """
CREATE TABLE IF NOT EXISTS veri (anahtar TEXT PRIMARY KEY, icerik TEXT);

CREATE TABLE IF NOT EXISTS kayit (
  id TEXT NOT NULL, kaynak TEXT NOT NULL, yil INTEGER, doi TEXT, baslik TEXT,
  dergi TEXT, issn TEXT, eissn TEXT, oa TEXT, belge_turu TEXT, belge_turu_ham TEXT,
  atif INTEGER DEFAULT 0, indeksler TEXT, kurum_yazarlari TEXT, ham TEXT,
  ilk_gorulme TEXT, son_gorulme TEXT,
  PRIMARY KEY (kaynak, id)
);
CREATE INDEX IF NOT EXISTS kayit_yil ON kayit (yil);
CREATE INDEX IF NOT EXISTS kayit_doi ON kayit (doi);

CREATE TABLE IF NOT EXISTS dergi_metrik (
  kaynak TEXT NOT NULL, yil INTEGER NOT NULL, issn TEXT NOT NULL DEFAULT '',
  dergi TEXT NOT NULL DEFAULT '', kategori TEXT NOT NULL DEFAULT '',
  q TEXT, deger REAL, guncelleme TEXT,
  PRIMARY KEY (kaynak, yil, issn, dergi, kategori)
);

CREATE TABLE IF NOT EXISTS kisi_metrik (
  kaynak TEXT NOT NULL, profil_kimlik TEXT NOT NULL, ad TEXT,
  h INTEGER DEFAULT 0, atif INTEGER DEFAULT 0, yayin INTEGER DEFAULT 0,
  guncelleme TEXT,
  PRIMARY KEY (kaynak, profil_kimlik)
);

CREATE TABLE IF NOT EXISTS takma_ad (
  ham_sade TEXT PRIMARY KEY, ham TEXT, hedef TEXT, tur TEXT,
  kaynak TEXT, karar_veren TEXT, tarih TEXT
);

CREATE TABLE IF NOT EXISTS onay_kuyrugu (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ham TEXT UNIQUE, kaynak TEXT,
  adaylar TEXT, benzerlik REAL, gecis INTEGER DEFAULT 0,
  durum TEXT DEFAULT 'bekliyor', tarih TEXT
);

CREATE TABLE IF NOT EXISTS senk_gunlugu (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kaynak TEXT, baslangic TEXT, bitis TEXT,
  durum TEXT, yeni_kayit INTEGER DEFAULT 0, mesaj TEXT
);
"""

KAYIT_SUTUNLARI = ("id", "kaynak", "yil", "doi", "baslik", "dergi", "issn", "eissn", "oa",
                   "belge_turu", "belge_turu_ham", "atif", "indeksler", "kurum_yazarlari", "ham")


def _simdi() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Depo:
    def __init__(self, yol: str | Path = VARSAYILAN_YOL):
        self.yol = Path(yol)
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        with self._baglanti() as db:
            db.executescript(SEMA)
        self.goc_et()

    def _baglanti(self):
        db = sqlite3.connect(self.yol)
        db.row_factory = sqlite3.Row
        return db

    # --- serbest biçimli alanlar -------------------------------------
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

    def sil(self, anahtar: str) -> None:
        with self._baglanti() as db:
            db.execute("DELETE FROM veri WHERE anahtar = ?", (anahtar,))

    def ayarlar(self) -> dict:
        return {**VARSAYILAN_AYARLAR, **self.oku("ayarlar")}

    def ayar_yaz(self, yeniler: dict) -> dict:
        birlesik = {**self.ayarlar(), **yeniler}
        self.yaz("ayarlar", birlesik)
        return birlesik

    # --- kayıtlar ----------------------------------------------------
    def kayitlari_ekle(self, yeniler: list[dict], kaynak: str, yil: int | None = None) -> int:
        """Aynı kaynağın aynı yılı tazelenir, diğer kaynaklar korunur."""
        yillar = {y for y in ((k.get("yil") for k in yeniler) if yil is None else [yil]) if y}
        simdi = _simdi()
        with self._baglanti() as db:
            if yillar:
                db.execute("DELETE FROM kayit WHERE kaynak = ? AND yil IN (%s)"
                           % ",".join("?" * len(yillar)), (kaynak, *sorted(yillar)))
            for kayit in yeniler:
                eski = db.execute("SELECT ilk_gorulme FROM kayit WHERE kaynak = ? AND id = ?",
                                  (kaynak, kayit["id"])).fetchone()
                db.execute(
                    "INSERT INTO kayit (id, kaynak, yil, doi, baslik, dergi, issn, eissn, oa, "
                    "belge_turu, belge_turu_ham, atif, indeksler, kurum_yazarlari, ham, "
                    "ilk_gorulme, son_gorulme) VALUES (%s, ?, ?) "
                    "ON CONFLICT(kaynak, id) DO UPDATE SET yil=excluded.yil, doi=excluded.doi, "
                    "baslik=excluded.baslik, dergi=excluded.dergi, issn=excluded.issn, "
                    "eissn=excluded.eissn, oa=excluded.oa, belge_turu=excluded.belge_turu, "
                    "belge_turu_ham=excluded.belge_turu_ham, atif=excluded.atif, "
                    "indeksler=excluded.indeksler, kurum_yazarlari=excluded.kurum_yazarlari, "
                    "ham=excluded.ham, son_gorulme=excluded.son_gorulme" % ",".join("?" * 15),
                    (kayit["id"], kaynak, kayit.get("yil"), kayit.get("doi"), kayit.get("baslik"),
                     kayit.get("dergi"), kayit.get("issn"), kayit.get("eissn"), kayit.get("oa"),
                     kayit.get("belge_turu"), kayit.get("belge_turu_ham"), kayit.get("atif") or 0,
                     json.dumps(kayit.get("indeksler", []), ensure_ascii=False),
                     json.dumps(kayit.get("kurum_yazarlari", []), ensure_ascii=False),
                     json.dumps({k: v for k, v in kayit.items()
                                 if k not in KAYIT_SUTUNLARI}, ensure_ascii=False),
                     (eski["ilk_gorulme"] if eski else simdi), simdi))
            return db.execute("SELECT COUNT(*) FROM kayit").fetchone()[0]

    def kayitlar(self, kaynak: str | None = None) -> list[dict]:
        sorgu = "SELECT * FROM kayit" + (" WHERE kaynak = ?" if kaynak else "")
        with self._baglanti() as db:
            satirlar = db.execute(sorgu, (kaynak,) if kaynak else ()).fetchall()
        return [self._kayit_coz(s) for s in satirlar]

    @staticmethod
    def _kayit_coz(satir: sqlite3.Row) -> dict:
        kayit = dict(satir)
        kayit["indeksler"] = json.loads(kayit.pop("indeksler") or "[]")
        kayit["kurum_yazarlari"] = json.loads(kayit.pop("kurum_yazarlari") or "[]")
        kayit.update(json.loads(kayit.pop("ham") or "{}"))
        return kayit

    def yeni_kayitlar(self, esikten_sonra: str) -> list[dict]:
        with self._baglanti() as db:
            satirlar = db.execute("SELECT * FROM kayit WHERE ilk_gorulme > ? ORDER BY ilk_gorulme DESC",
                                  (esikten_sonra,)).fetchall()
        return [self._kayit_coz(s) for s in satirlar]

    # --- dergi ve kişi metrikleri ------------------------------------
    def dergi_metrik_ekle(self, satirlar: list[dict]) -> int:
        simdi = _simdi()
        with self._baglanti() as db:
            for s in satirlar:
                db.execute(
                    "INSERT INTO dergi_metrik (kaynak, yil, issn, dergi, kategori, q, deger, guncelleme) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(kaynak, yil, issn, dergi, kategori) DO UPDATE SET "
                    "q=excluded.q, deger=excluded.deger, guncelleme=excluded.guncelleme",
                    (s["kaynak"], int(s.get("yil") or 0), s.get("issn") or "", s.get("dergi") or "",
                     s.get("kategori") or "", s.get("q"), s.get("deger"), simdi))
            return db.execute("SELECT COUNT(*) FROM dergi_metrik").fetchone()[0]

    def dergi_metrikleri(self) -> list[dict]:
        with self._baglanti() as db:
            return [dict(s) for s in db.execute("SELECT * FROM dergi_metrik").fetchall()]

    def kisi_metrik_ekle(self, satirlar: list[dict]) -> int:
        simdi = _simdi()
        with self._baglanti() as db:
            for s in satirlar:
                db.execute(
                    "INSERT INTO kisi_metrik (kaynak, profil_kimlik, ad, h, atif, yayin, guncelleme) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(kaynak, profil_kimlik) DO UPDATE SET ad=excluded.ad, h=excluded.h, "
                    "atif=excluded.atif, yayin=excluded.yayin, guncelleme=excluded.guncelleme",
                    (s["kaynak"], str(s.get("profil_kimlik") or s.get("ad") or ""), s.get("ad"),
                     int(s.get("h") or 0), int(s.get("atif") or 0), int(s.get("yayin") or 0), simdi))
            return db.execute("SELECT COUNT(*) FROM kisi_metrik").fetchone()[0]

    def kisi_metrikleri(self) -> list[dict]:
        with self._baglanti() as db:
            return [dict(s) for s in db.execute("SELECT * FROM kisi_metrik").fetchall()]

    # --- takma adlar ve onay kuyruğu ---------------------------------
    def takma_adlar(self) -> dict[str, str]:
        with self._baglanti() as db:
            return {s["ham_sade"]: s["hedef"]
                    for s in db.execute("SELECT ham_sade, hedef FROM takma_ad").fetchall()}

    def takma_ad_yaz(self, ham_sade: str, ham: str, hedef: str, tur: str = "personel",
                     kaynak: str = "", karar_veren: str = "kullanici") -> None:
        with self._baglanti() as db:
            db.execute("INSERT INTO takma_ad (ham_sade, ham, hedef, tur, kaynak, karar_veren, tarih) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(ham_sade) DO UPDATE SET "
                       "hedef=excluded.hedef, tur=excluded.tur, kaynak=excluded.kaynak, "
                       "karar_veren=excluded.karar_veren, tarih=excluded.tarih",
                       (ham_sade, ham, hedef, tur, kaynak, karar_veren, _simdi()))

    def takma_ad_sil(self, ham_sade: str) -> None:
        with self._baglanti() as db:
            db.execute("DELETE FROM takma_ad WHERE ham_sade = ?", (ham_sade,))

    def kuyruga_ekle(self, kayitlar: list[dict]) -> int:
        with self._baglanti() as db:
            for k in kayitlar:
                db.execute(
                    "INSERT INTO onay_kuyrugu (ham, kaynak, adaylar, benzerlik, gecis, durum, tarih) "
                    "VALUES (?, ?, ?, ?, ?, 'bekliyor', ?) ON CONFLICT(ham) DO UPDATE SET "
                    "adaylar=excluded.adaylar, benzerlik=excluded.benzerlik, "
                    "gecis=onay_kuyrugu.gecis + 1 WHERE onay_kuyrugu.durum = 'bekliyor'",
                    (k["ham"], k.get("kaynak", ""),
                     json.dumps(k.get("adaylar", []), ensure_ascii=False),
                     float(k.get("benzerlik") or 0), int(k.get("gecis") or 0), _simdi()))
            return db.execute("SELECT COUNT(*) FROM onay_kuyrugu WHERE durum = 'bekliyor'").fetchone()[0]

    def kuyruk(self, durum: str = "bekliyor") -> list[dict]:
        with self._baglanti() as db:
            satirlar = db.execute("SELECT * FROM onay_kuyrugu WHERE durum = ? "
                                  "ORDER BY benzerlik DESC, ham", (durum,)).fetchall()
        kayitlar = []
        for s in satirlar:
            kayit = dict(s)
            kayit["adaylar"] = json.loads(kayit["adaylar"] or "[]")
            kayitlar.append(kayit)
        return kayitlar

    def kuyruk_karari(self, ham: str, durum: str, hedef: str = "", tur: str = "personel") -> None:
        """durum: 'onayli' (hedefe bağla), 'reddedildi' (bir daha sorma, eşleşmesiz kalsın)."""
        with self._baglanti() as db:
            db.execute("UPDATE onay_kuyrugu SET durum = ?, tarih = ? WHERE ham = ?",
                       (durum, _simdi(), ham))
        if durum == "onayli" and hedef:
            from .metin import sade
            self.takma_ad_yaz(sade(ham), ham, hedef, tur)

    # --- senkron günlüğü ---------------------------------------------
    def senk_basla(self, kaynak: str) -> int:
        with self._baglanti() as db:
            imlec = db.execute("INSERT INTO senk_gunlugu (kaynak, baslangic, durum) "
                               "VALUES (?, ?, 'calisiyor')", (kaynak, _simdi()))
            return imlec.lastrowid

    def senk_bitir(self, kimlik: int, durum: str, yeni_kayit: int = 0, mesaj: str = "") -> None:
        with self._baglanti() as db:
            db.execute("UPDATE senk_gunlugu SET bitis = ?, durum = ?, yeni_kayit = ?, mesaj = ? "
                       "WHERE id = ?", (_simdi(), durum, yeni_kayit, mesaj[:2000], kimlik))

    def senk_gunlugu(self, adet: int = 20) -> list[dict]:
        with self._baglanti() as db:
            return [dict(s) for s in db.execute(
                "SELECT * FROM senk_gunlugu ORDER BY id DESC LIMIT ?", (adet,)).fetchall()]

    def son_senk(self, kaynak: str) -> str | None:
        with self._baglanti() as db:
            satir = db.execute("SELECT bitis FROM senk_gunlugu WHERE kaynak = ? AND durum = 'tamam' "
                               "ORDER BY id DESC LIMIT 1", (kaynak,)).fetchone()
        return satir["bitis"] if satir else None

    # --- aylık ödemeler ----------------------------------------------
    def ay_ekle(self, donem: str, kayitlar: list[dict]) -> int:
        mevcut = [k for k in self.oku("aylik_kayitlar") if k.get("donem") != donem]
        birlesik = [*mevcut, *kayitlar]
        self.yaz("aylik_kayitlar", birlesik)
        return len(birlesik)

    def ay_sil(self, donem: str) -> None:
        self.yaz("aylik_kayitlar", [k for k in self.oku("aylik_kayitlar") if k.get("donem") != donem])

    # --- panel beslemesi ---------------------------------------------
    def hepsini_oku(self) -> dict:
        veri = {anahtar: self.oku(anahtar) for anahtar in ALANLAR}
        veri["kurum_kayitlari"] = self.kayitlar()
        veri["dergi_metrikleri"] = self.dergi_metrikleri()
        veri["kisi_metrikleri"] = self.kisi_metrikleri()
        veri["takma_adlar"] = self.takma_adlar()
        return veri

    # --- göç ---------------------------------------------------------
    def goc_et(self) -> dict:
        """Sürüm 1 verisini yeni tablolara taşır; birden çok çağrıda güvenlidir."""
        sonuc = {"kayit": 0, "dergi_metrik": 0, "kisi_metrik": 0}
        with self._baglanti() as db:
            var = {s["anahtar"] for s in db.execute("SELECT anahtar FROM veri").fetchall()}
            bos = db.execute("SELECT COUNT(*) FROM kayit").fetchone()[0] == 0

        if "kurum_kayitlari" in var and bos:
            eski = self.oku("kurum_kayitlari")
            for kaynak in {k.get("kaynak") or "WoS" for k in eski}:
                altkume = [k for k in eski if (k.get("kaynak") or "WoS") == kaynak]
                sonuc["kayit"] = self.kayitlari_ekle(altkume, kaynak, yil=None)
            self.sil("kurum_kayitlari")

        if "quartiller" in var:
            satirlar = []
            for yil, harita in (self.oku("quartiller") or {}).items():
                for issn, q in harita.items():
                    satirlar.append({"kaynak": "miras", "yil": int(yil), "issn": issn,
                                     "kategori": "", "q": q})
            if satirlar:
                sonuc["dergi_metrik"] = self.dergi_metrik_ekle(satirlar)
            self.sil("quartiller")

        if "metrikler" in var:
            eski = self.oku("metrikler") or []
            if eski:
                sonuc["kisi_metrik"] = self.kisi_metrik_ekle(
                    [{"kaynak": "miras", "profil_kimlik": k.get("kimlik") or k.get("ad"),
                      "ad": k.get("ad"), "h": k.get("h"), "atif": k.get("atif")} for k in eski])
            self.sil("metrikler")
        return sonuc
