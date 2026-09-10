"""Adjunct yayin takibi - cekirdek katman.

Aylik "... Yayinlari" Excel dosyalarini ayristirir, SQLite'a yazar ve
kisi / donem / para birimi bazinda ozet-pivot sorgulari uretir.

Dosya duzeni (her ay ayni):
    AGUSTOS 2026 Yayinlari              <- baslik, donemi verir
    <Kisi Adi>                          <- bolum basligi
    Sira | Article Title | Journal | Authors | DOI | Quartile | Date |
         Index Link | Kontrol | Payments
    1    | ...                                                   | 431
    ...
                                 Toplam |      | 1293             <- bolum toplami
    ...
    OZET / SUMMARY                      <- kisi bazinda toplam listesi
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from dataclasses import dataclass, asdict
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

VARSAYILAN_DB = os.path.join(os.path.expanduser("~"), "yayin_takip.db")

AY_ADLARI = [
    "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran",
    "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik",
]

PARA_BIRIMLERI = ["USD", "EUR", "CNY", "TRY", "GBP"]

_AY_ANAHTAR = {
    "ocak": 1, "oca": 1, "january": 1, "jan": 1,
    "subat": 2, "sub": 2, "february": 2, "feb": 2,
    "mart": 3, "mar": 3, "march": 3,
    "nisan": 4, "nis": 4, "april": 4, "apr": 4,
    "mayis": 5, "may": 5,
    "haziran": 6, "haz": 6, "june": 6, "jun": 6,
    "temmuz": 7, "tem": 7, "july": 7, "jul": 7,
    "agustos": 8, "agu": 8, "august": 8, "aug": 8,
    "eylul": 9, "eyl": 9, "september": 9, "sept": 9, "sep": 9,
    "ekim": 10, "eki": 10, "october": 10, "oct": 10,
    "kasim": 11, "kas": 11, "november": 11, "nov": 11,
    "aralik": 12, "ara": 12, "december": 12, "dec": 12,
}

# Bolum tablosunun basliklari -> alan adi (basliktaki anahtar kelimeler)
SUTUN_ANAHTARLARI = {
    "sira": ["sira", "no", "sno"],
    "baslik": ["article title", "title", "baslik", "makale", "yayin adi", "eser"],
    "dergi": ["journal", "conference", "dergi", "yayinevi"],
    "yazarlar": ["authors", "author", "yazar"],
    "doi": ["doi"],
    "quartile": ["quartile", "quartil", "q index", "kategori"],
    "tarih": ["date", "tarih", "yayin tarihi"],
    "index_link": ["index link", "index", "link", "scopus", "wos"],
    "kontrol": ["kontrol", "note", "not", "aciklama"],
    "odeme": ["payments", "payment", "odeme", "tutar", "ucret"],
}


# --------------------------------------------------------------------------- #
# Metin / sayi / tarih yardimcilari
# --------------------------------------------------------------------------- #

def sadelestir(metin) -> str:
    """Karsilastirma icin: kucuk harf, Turkce karakter sadelestirme, tek bosluk."""
    s = str(metin or "").strip().lower()
    for a, b in (("ı", "i"), ("İ", "i"), ("ş", "s"), ("ğ", "g"),
                 ("ü", "u"), ("ö", "o"), ("ç", "c"), ("â", "a")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def temiz_ad(metin) -> str:
    """Kisi adindaki satir sonu ve fazla bosluklari temizler."""
    return re.sub(r"\s+", " ", str(metin or "").replace("\n", " ")).strip()


def sayiya_cevir(deger):
    """Hucre degerini sayiya cevirir; sayi yoksa None doner."""
    if deger is None:
        return None
    if isinstance(deger, bool):
        return None
    if isinstance(deger, (int, float)):
        return float(deger)
    s = str(deger).strip()
    if not s:
        return None
    negatif = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("\xa0", "").replace(" ", "")
    s = re.sub(r"(?i)(tl|try|₺|\$|eur|€|usd|cny|¥|gbp|£)", "", s)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # Sadece nokta: "2.500" gibi son grubu 3 haneli degerler binlik ayracidir.
        parcalar = s.split(".")
        if len(parcalar) > 2 or (len(parcalar[-1]) == 3 and parcalar[0].lstrip("-").isdigit()):
            s = "".join(parcalar)
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", "."):
        return None
    try:
        sonuc = float(s)
    except ValueError:
        return None
    return -sonuc if negatif else sonuc


def tarih_metni(deger) -> str:
    """Date sutunu cok bicimli; ekranda okunur bir metne indirger."""
    if deger is None:
        return ""
    if isinstance(deger, datetime):
        return deger.date().isoformat()
    if isinstance(deger, date):
        return deger.isoformat()
    return re.sub(r"\s+", " ", str(deger)).strip()


def donem_coz(metin):
    """'AGUSTOS 2026 Yayinlari' / 'Agustos Yayinlari_Adjunct' -> (yil, ay). Yoksa None."""
    sade = sadelestir(metin)
    if not sade:
        return None
    yil_bul = re.search(r"\b(20\d{2})\b", sade)
    ay = None
    for anahtar, no in _AY_ANAHTAR.items():
        if re.search(rf"\b{anahtar}", sade):
            ay = no
            break
    if ay and yil_bul:
        return int(yil_bul.group(1)), ay
    if ay:
        return None if not yil_bul else (int(yil_bul.group(1)), ay)
    kalip = re.search(r"\b(20\d{2})[ \-_/]?(0[1-9]|1[0-2])\b", sade)
    if kalip:
        return int(kalip.group(1)), int(kalip.group(2))
    return None


def donem_etiketi(yil: int, ay: int) -> str:
    return f"{AY_ADLARI[ay - 1]} {yil}" if 1 <= (ay or 0) <= 12 else str(yil)


def donem_kisa(yil: int, ay: int) -> str:
    return f"{yil}-{ay:02d}" if ay else str(yil)


def para_birimi_coz(kontrol: str, kisi_kurallari=None, kisi: str = ""):
    """Kontrol notundan para birimini ve varsa USD karsiligini belirler.

    - Not 'EUR/USD paritesi' iceriyorsa tutar EUR'dur; nottaki '500/1.1595'
      ifadesinin payi (500) USD karsiligidir.
    - Not Cin Yuani / CNY diyorsa CNY.
    - Kisi bazli zorlama (or. hep Yuan alan biri) kurallardan gelir.
    - Aksi halde USD.
    """
    not_sade = sadelestir(kontrol)
    zorlanan = (kisi_kurallari or {}).get(temiz_ad(kisi))
    parite = re.search(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", str(kontrol or ""))
    usd_karsiligi = sayiya_cevir(parite.group(1)) if parite else None

    if zorlanan:
        return zorlanan, usd_karsiligi
    if re.search(r"\b(cny|yuan|yuani|rmb|cin)\b", not_sade):
        return "CNY", usd_karsiligi
    if "eur" in not_sade or "parite" in not_sade or "paraite" in not_sade:
        return "EUR", usd_karsiligi
    return "USD", usd_karsiligi


# --------------------------------------------------------------------------- #
# Ayristirma
# --------------------------------------------------------------------------- #

@dataclass
class Yayin:
    kisi: str
    yil: int
    ay: int
    sira: str = ""
    baslik: str = ""
    dergi: str = ""
    yazarlar: str = ""
    doi: str = ""
    quartile: str = ""
    tarih: str = ""
    index_link: str = ""
    kontrol: str = ""
    tutar: float | None = None
    para_birimi: str = "USD"
    usd_karsiligi: float | None = None
    onayli: int = 0
    kaynak: str = ""

    def imza(self) -> str:
        kimlik = (self.doi.strip().lower() or
                  f"{sadelestir(self.baslik)}|{sadelestir(self.dergi)}")
        ham = f"{sadelestir(self.kisi)}|{self.yil}|{self.ay}|{kimlik}|{self.sira}"
        return hashlib.sha256(ham.encode("utf-8")).hexdigest()


def sayfa_adlari(dosya: str):
    kitap = load_workbook(dosya, read_only=True, data_only=True)
    try:
        return list(kitap.sheetnames)
    finally:
        kitap.close()


def _sutun_haritasi(satir):
    """Bolum baslik satirindan alan -> kolon indeksi haritasi kurar."""
    harita = {}
    for i, hucre in enumerate(satir):
        sade = sadelestir(hucre)
        if not sade:
            continue
        for alan, anahtarlar in SUTUN_ANAHTARLARI.items():
            if alan in harita:
                continue
            for anahtar in anahtarlar:
                a = sadelestir(anahtar)
                if sade == a or sade.startswith(a) or a in sade:
                    harita[alan] = i
                    break
    return harita


def _metin(satir, harita, alan) -> str:
    i = harita.get(alan)
    if i is None or i >= len(satir) or satir[i] is None:
        return ""
    return re.sub(r"\s+", " ", str(satir[i])).strip()


def dosyayi_ayristir(dosya: str, sayfa: str | None = None, donem=None,
                     kisi_kurallari=None):
    """Excel'i okuyup (donem, yayinlar, ozet, uyarilar) doner.

    donem: (yil, ay) verilirse dosyadaki basliga bakilmaz.
    ozet:  dosyanin kendi 'OZET / SUMMARY' bloğu {kisi: toplam}
    """
    kitap = load_workbook(dosya, read_only=True, data_only=True)
    try:
        calisma = kitap[sayfa] if sayfa else kitap[kitap.sheetnames[0]]
        satirlar = [list(s) for s in calisma.iter_rows(values_only=True)]
    finally:
        kitap.close()

    uyarilar = []
    if donem is None:
        for satir in satirlar[:5]:
            for hucre in satir:
                cozulen = donem_coz(hucre)
                if cozulen:
                    donem = cozulen
                    break
            if donem:
                break
    if donem is None:
        donem = donem_coz(os.path.basename(dosya))
    if donem is None:
        raise ValueError(
            "Dosyanin donemi bulunamadi. Baslik satirinda 'AGUSTOS 2026 Yayinlari' "
            "gibi bir ifade yoksa donemi elle secin.")
    yil, ay = donem

    yayinlar, ozet = [], {}
    harita, kisi = {}, ""
    ozet_bolumu = False
    kaynak = os.path.basename(dosya)

    for no, satir in enumerate(satirlar, start=1):
        metinler = [("" if h is None else str(h).strip()) for h in satir]
        dolu = [m for m in metinler if m]
        if not dolu:
            continue
        birlesik = sadelestir(" ".join(dolu))

        if "ozet" in birlesik or "summary" in birlesik:
            ozet_bolumu = True
            continue
        if ozet_bolumu:
            # 'OZET' blogu: <bos> | Kisi | Toplam
            adaylar = [m for m in metinler if m]
            if len(adaylar) >= 2:
                tutar = sayiya_cevir(adaylar[-1])
                ad = temiz_ad(adaylar[-2])
                if tutar is not None and ad and sadelestir(ad) not in ("adjunct", "toplam odeme"):
                    ozet[ad] = tutar
            continue

        ilk_sade = sadelestir(metinler[0]) if metinler else ""
        if ilk_sade in ("sira", "no") or (harita == {} and "article title" in birlesik):
            harita = _sutun_haritasi(metinler)
            continue
        if "toplam" in birlesik and len(dolu) <= 3:
            continue  # bolum toplami; degerler satirlardan hesaplanir
        if len(dolu) == 1 and metinler[0]:
            # Tek dolu hucre: ya dosya basligi ya da kisi adi
            if donem_coz(metinler[0]) or "yayin" in ilk_sade:
                continue
            kisi = temiz_ad(metinler[0])
            continue
        if not kisi:
            continue
        if not harita:
            uyarilar.append(f"{no}. satir: baslik satiri bulunamadan veri geldi, atlandi.")
            continue

        baslik = _metin(satir, harita, "baslik")
        doi = _metin(satir, harita, "doi")
        if not baslik and not doi:
            continue

        kontrol = _metin(satir, harita, "kontrol")
        tutar = sayiya_cevir(satir[harita["odeme"]]) if "odeme" in harita else None
        para, usd = para_birimi_coz(kontrol, kisi_kurallari, kisi)
        if tutar is not None and usd is None and para == "USD":
            usd = tutar
        yayinlar.append(Yayin(
            kisi=kisi, yil=yil, ay=ay,
            sira=_metin(satir, harita, "sira"),
            baslik=baslik,
            dergi=_metin(satir, harita, "dergi"),
            yazarlar=_metin(satir, harita, "yazarlar"),
            doi=doi,
            quartile=_metin(satir, harita, "quartile").upper(),
            tarih=tarih_metni(satir[harita["tarih"]]) if "tarih" in harita else "",
            index_link=_metin(satir, harita, "index_link"),
            kontrol=kontrol,
            tutar=tutar,
            para_birimi=para,
            usd_karsiligi=usd,
            onayli=1 if (tutar or 0) > 0 else 0,
            kaynak=kaynak,
        ))

    if not yayinlar:
        uyarilar.append("Dosyada kayit bulunamadi; sayfa secimini kontrol edin.")

    # Dosyanin kendi ozet toplamlari ile hesaplanan toplamlari karsilastir.
    for ad, beyan in ozet.items():
        hesap = sum(y.tutar or 0 for y in yayinlar if sadelestir(y.kisi) == sadelestir(ad))
        if abs(hesap - beyan) > 0.5:
            uyarilar.append(
                f"{ad}: dosyadaki ozet {beyan:g}, satirlardan hesaplanan {hesap:g} "
                f"(satirlar esas alindi).")
    return (yil, ay), yayinlar, ozet, uyarilar


# --------------------------------------------------------------------------- #
# Veritabani
# --------------------------------------------------------------------------- #

SEMA = """
CREATE TABLE IF NOT EXISTS yayinlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kisi TEXT NOT NULL,
    yil INTEGER NOT NULL,
    ay INTEGER NOT NULL,
    sira TEXT DEFAULT '',
    baslik TEXT DEFAULT '',
    dergi TEXT DEFAULT '',
    yazarlar TEXT DEFAULT '',
    doi TEXT DEFAULT '',
    quartile TEXT DEFAULT '',
    tarih TEXT DEFAULT '',
    index_link TEXT DEFAULT '',
    kontrol TEXT DEFAULT '',
    tutar REAL,
    para_birimi TEXT DEFAULT 'USD',
    usd_karsiligi REAL,
    onayli INTEGER DEFAULT 0,
    kaynak TEXT DEFAULT '',
    imza TEXT NOT NULL UNIQUE,
    eklenme TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_yayin_donem ON yayinlar (yil, ay);
CREATE INDEX IF NOT EXISTS ix_yayin_kisi ON yayinlar (kisi);

CREATE TABLE IF NOT EXISTS kisi_kurallari (
    kisi TEXT PRIMARY KEY,
    para_birimi TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS aktarimlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya TEXT, sayfa TEXT, yil INTEGER, ay INTEGER,
    eklenen INTEGER, silinen INTEGER, atlanan INTEGER,
    zaman TEXT NOT NULL
);
"""

OLCULER = {
    "tutar": "Odeme tutari",
    "usd_karsiligi": "USD karsiligi",
    "yayin": "Kayit sayisi",
    "onayli": "Onayli yayin sayisi",
}


class Veritabani:
    """SQLite deposu ve raporlama sorgulari."""

    def __init__(self, yol: str = VARSAYILAN_DB):
        self.yol = yol
        klasor = os.path.dirname(os.path.abspath(yol))
        if klasor:
            os.makedirs(klasor, exist_ok=True)
        self.baglanti = sqlite3.connect(yol)
        self.baglanti.row_factory = sqlite3.Row
        self._goc()
        self.baglanti.executescript(SEMA)
        self.baglanti.commit()

    # -- sema gocu --------------------------------------------------------- #

    def _sutunlar(self, tablo: str):
        return [s["name"] for s in self.baglanti.execute(f"PRAGMA table_info({tablo})")]

    def _goc(self):
        """Eski surumlerden kalan tablolari yeni semaya uyarlar.

        'aktarimlar' sadece kayit gunlugudur; eksik sutun varsa yeniden
        olusturulur. 'yayinlar' eksikse veri kaybetmemek icin yeniden
        adlandirilir ve bos tablo kurulur (dosyalari tekrar yuklemek yeter).
        """
        beklenen = {
            "aktarimlar": {"dosya", "sayfa", "yil", "ay", "eklenen", "silinen",
                           "atlanan", "zaman"},
            "yayinlar": {"kisi", "yil", "ay", "tutar", "para_birimi", "usd_karsiligi",
                         "onayli", "imza"},
        }
        damga = datetime.now().strftime("%Y%m%d%H%M%S")
        for tablo, sutunlar in beklenen.items():
            mevcut = set(self._sutunlar(tablo))
            if not mevcut or sutunlar <= mevcut:
                continue
            if tablo == "aktarimlar":
                self.baglanti.execute("DROP TABLE aktarimlar")
            else:
                self.baglanti.execute(f"ALTER TABLE {tablo} RENAME TO {tablo}_eski_{damga}")
        self.baglanti.commit()

    def kapat(self):
        self.baglanti.close()

    # -- yazma ------------------------------------------------------------- #

    def aktar(self, yayinlar, yil: int, ay: int, dosya: str = "", sayfa: str = "",
              donemi_degistir: bool = True):
        """Ayin verisini yazar. Varsayilan davranis: o ayi silip yeniden yazmak."""
        imlec = self.baglanti.cursor()
        silinen = 0
        if donemi_degistir:
            imlec.execute("DELETE FROM yayinlar WHERE yil=? AND ay=?", (yil, ay))
            silinen = imlec.rowcount
        eklenen = atlanan = 0
        simdi = datetime.now().isoformat(timespec="seconds")
        for yayin in yayinlar:
            veri = asdict(yayin)
            veri["imza"] = yayin.imza()
            veri["eklenme"] = simdi
            try:
                imlec.execute(
                    """INSERT INTO yayinlar
                       (kisi, yil, ay, sira, baslik, dergi, yazarlar, doi, quartile, tarih,
                        index_link, kontrol, tutar, para_birimi, usd_karsiligi, onayli,
                        kaynak, imza, eklenme)
                       VALUES (:kisi,:yil,:ay,:sira,:baslik,:dergi,:yazarlar,:doi,:quartile,
                               :tarih,:index_link,:kontrol,:tutar,:para_birimi,:usd_karsiligi,
                               :onayli,:kaynak,:imza,:eklenme)""", veri)
                eklenen += 1
            except sqlite3.IntegrityError:
                atlanan += 1
        imlec.execute(
            """INSERT INTO aktarimlar (dosya, sayfa, yil, ay, eklenen, silinen, atlanan, zaman)
               VALUES (?,?,?,?,?,?,?,?)""",
            (dosya, sayfa, yil, ay, eklenen, silinen, atlanan, simdi))
        self.baglanti.commit()
        return {"eklenen": eklenen, "silinen": silinen, "atlanan": atlanan}

    def donem_sil(self, yil: int, ay: int | None = None) -> int:
        imlec = self.baglanti.cursor()
        if ay:
            imlec.execute("DELETE FROM yayinlar WHERE yil=? AND ay=?", (yil, ay))
        else:
            imlec.execute("DELETE FROM yayinlar WHERE yil=?", (yil,))
        self.baglanti.commit()
        return imlec.rowcount

    def kural_kaydet(self, kisi: str, para_birimi: str | None):
        if para_birimi:
            self.baglanti.execute(
                "INSERT OR REPLACE INTO kisi_kurallari (kisi, para_birimi) VALUES (?,?)",
                (temiz_ad(kisi), para_birimi))
        else:
            self.baglanti.execute("DELETE FROM kisi_kurallari WHERE kisi=?", (temiz_ad(kisi),))
        self.baglanti.commit()

    def kurallar(self) -> dict:
        return {s["kisi"]: s["para_birimi"]
                for s in self.baglanti.execute("SELECT kisi, para_birimi FROM kisi_kurallari")}

    def kural_uygula(self, kisi: str, para_birimi: str) -> int:
        """Kurali gecmis kayitlara da uygular (para birimini toptan gunceller)."""
        imlec = self.baglanti.cursor()
        imlec.execute("UPDATE yayinlar SET para_birimi=? WHERE kisi=?", (para_birimi, kisi))
        self.baglanti.commit()
        return imlec.rowcount

    # -- okuma ------------------------------------------------------------- #

    def _kosul(self, yil=None, ay=None, kisi=None, para_birimi=None, quartile=None,
               sadece_onayli=False, arama=None):
        kosullar, degerler = [], []
        if yil:
            kosullar.append("yil = ?"); degerler.append(int(yil))
        if ay:
            kosullar.append("ay = ?"); degerler.append(int(ay))
        if kisi:
            kosullar.append("kisi = ?"); degerler.append(kisi)
        if para_birimi:
            kosullar.append("para_birimi = ?"); degerler.append(para_birimi)
        if quartile:
            kosullar.append("quartile = ?"); degerler.append(quartile)
        if sadece_onayli:
            kosullar.append("onayli = 1")
        if arama:
            kosullar.append("(kisi LIKE ? OR baslik LIKE ? OR dergi LIKE ? OR doi LIKE ? "
                            "OR yazarlar LIKE ? OR kontrol LIKE ?)")
            degerler += [f"%{arama}%"] * 6
        return ("WHERE " + " AND ".join(kosullar) if kosullar else ""), degerler

    def donemler(self):
        return [(s["yil"], s["ay"]) for s in self.baglanti.execute(
            "SELECT DISTINCT yil, ay FROM yayinlar ORDER BY yil, ay")]

    def yillar(self):
        return [s[0] for s in self.baglanti.execute(
            "SELECT DISTINCT yil FROM yayinlar ORDER BY yil DESC")]

    def kisiler(self):
        return [s[0] for s in self.baglanti.execute(
            "SELECT DISTINCT kisi FROM yayinlar ORDER BY kisi")]

    def kullanilan_para_birimleri(self):
        return [s[0] for s in self.baglanti.execute(
            "SELECT DISTINCT para_birimi FROM yayinlar ORDER BY para_birimi")]

    def genel_ozet(self, **filtre):
        kosul, degerler = self._kosul(**filtre)
        satir = self.baglanti.execute(
            f"""SELECT COUNT(*) kayit, COALESCE(SUM(onayli),0) onayli,
                       COUNT(DISTINCT kisi) kisi_sayisi,
                       COALESCE(SUM(usd_karsiligi),0) usd_karsiligi
                FROM yayinlar {kosul}""", degerler).fetchone()
        ozet = dict(satir)
        ozet["para"] = {s["para_birimi"]: s["toplam"] for s in self.baglanti.execute(
            f"""SELECT para_birimi, COALESCE(SUM(tutar),0) toplam
                FROM yayinlar {kosul} GROUP BY para_birimi ORDER BY toplam DESC""", degerler)}
        return ozet

    def kisi_ozet(self, **filtre):
        """Kisi bazinda: kayit / onayli sayisi ve para birimi kirilimli toplamlar."""
        kosul, degerler = self._kosul(**filtre)
        birimler = self.kullanilan_para_birimleri() or ["USD"]
        secmeler = ", ".join(
            f"COALESCE(SUM(CASE WHEN para_birimi='{b}' THEN tutar END),0) AS \"{b}\""
            for b in birimler)
        satirlar = [dict(s) for s in self.baglanti.execute(
            f"""SELECT kisi, COUNT(*) kayit, COALESCE(SUM(onayli),0) onayli,
                       COALESCE(SUM(usd_karsiligi),0) usd_karsiligi, {secmeler}
                FROM yayinlar {kosul} GROUP BY kisi ORDER BY usd_karsiligi DESC, kisi""",
            degerler)]
        return birimler, satirlar

    def donem_ozet(self, **filtre):
        kosul, degerler = self._kosul(**filtre)
        birimler = self.kullanilan_para_birimleri() or ["USD"]
        secmeler = ", ".join(
            f"COALESCE(SUM(CASE WHEN para_birimi='{b}' THEN tutar END),0) AS \"{b}\""
            for b in birimler)
        satirlar = [dict(s) for s in self.baglanti.execute(
            f"""SELECT yil, ay, COUNT(*) kayit, COALESCE(SUM(onayli),0) onayli,
                       COUNT(DISTINCT kisi) kisi_sayisi,
                       COALESCE(SUM(usd_karsiligi),0) usd_karsiligi, {secmeler}
                FROM yayinlar {kosul} GROUP BY yil, ay ORDER BY yil, ay""", degerler)]
        return birimler, satirlar

    def kirilim(self, alan: str, **filtre):
        """quartile / para_birimi / dergi / tutar bazinda dagilim."""
        if alan not in ("quartile", "para_birimi", "dergi", "tutar", "kisi"):
            raise ValueError("Gecersiz kirilim alani")
        kosul, degerler = self._kosul(**filtre)
        return [dict(s) for s in self.baglanti.execute(
            f"""SELECT COALESCE(NULLIF({alan},''),'(bos)') anahtar, COUNT(*) kayit,
                       COALESCE(SUM(onayli),0) onayli, COUNT(DISTINCT kisi) kisi_sayisi,
                       COALESCE(SUM(tutar),0) tutar, COALESCE(SUM(usd_karsiligi),0) usd_karsiligi
                FROM yayinlar {kosul} GROUP BY anahtar ORDER BY usd_karsiligi DESC, kayit DESC""",
            degerler)]

    def pivot(self, satir_alani: str = "kisi", olcu: str = "tutar", yil: int | None = None,
              **filtre):
        """Satir = kisi/quartile/dergi/para_birimi, sutun = donemler + yil toplamlari."""
        if satir_alani not in ("kisi", "quartile", "dergi", "para_birimi"):
            raise ValueError("Gecersiz satir alani")
        ifade = {"tutar": "COALESCE(SUM(tutar),0)",
                 "usd_karsiligi": "COALESCE(SUM(usd_karsiligi),0)",
                 "yayin": "COUNT(*)",
                 "onayli": "COALESCE(SUM(onayli),0)"}[olcu]
        filtre.pop("yil", None)
        kosul, degerler = self._kosul(yil=yil, **filtre)
        ham = self.baglanti.execute(
            f"""SELECT COALESCE(NULLIF({satir_alani},''),'(bos)') anahtar, yil, ay,
                       {ifade} deger
                FROM yayinlar {kosul} GROUP BY anahtar, yil, ay ORDER BY yil, ay""",
            degerler).fetchall()
        donemler = sorted({(s["yil"], s["ay"]) for s in ham})
        yillar = sorted({y for y, _ in donemler})
        indeks = {d: i for i, d in enumerate(donemler)}
        tablo = {}
        for s in ham:
            satir = tablo.setdefault(s["anahtar"], [0.0] * len(donemler))
            satir[indeks[(s["yil"], s["ay"])]] += float(s["deger"] or 0)
        satirlar = []
        for ad, degerler_ in tablo.items():
            yil_toplam = [sum(d for (y, _), d in zip(donemler, degerler_) if y == yil_)
                          for yil_ in yillar]
            satirlar.append([ad] + degerler_ + yil_toplam + [sum(degerler_)])
        satirlar.sort(key=lambda r: r[-1], reverse=True)
        etiket = {"kisi": "Kisi", "quartile": "Quartile",
                  "dergi": "Dergi", "para_birimi": "Para birimi"}[satir_alani]
        basliklar = ([etiket] + [f"{AY_ADLARI[a-1]} {y}" for y, a in donemler]
                     + [str(y) for y in yillar] + ["Toplam"])
        return basliklar, satirlar, len(donemler)

    def kayitlar(self, limit: int = 5000, **filtre):
        kosul, degerler = self._kosul(**filtre)
        return [dict(s) for s in self.baglanti.execute(
            f"""SELECT * FROM yayinlar {kosul}
                ORDER BY yil DESC, ay DESC, kisi, CAST(sira AS INTEGER) LIMIT ?""",
            degerler + [limit])]

    def kisi_detay(self, kisi: str):
        yillik = [dict(s) for s in self.baglanti.execute(
            """SELECT yil, COUNT(*) kayit, COALESCE(SUM(onayli),0) onayli,
                      COALESCE(SUM(usd_karsiligi),0) usd_karsiligi
               FROM yayinlar WHERE kisi=? GROUP BY yil ORDER BY yil DESC""", (kisi,))]
        aylik = [dict(s) for s in self.baglanti.execute(
            """SELECT yil, ay, COUNT(*) kayit, COALESCE(SUM(onayli),0) onayli,
                      COALESCE(SUM(tutar),0) tutar, para_birimi
               FROM yayinlar WHERE kisi=? GROUP BY yil, ay, para_birimi
               ORDER BY yil DESC, ay DESC""", (kisi,))]
        return yillik, aylik

    def son_aktarimlar(self, limit: int = 20):
        return [dict(s) for s in self.baglanti.execute(
            "SELECT * FROM aktarimlar ORDER BY id DESC LIMIT ?", (limit,))]


# --------------------------------------------------------------------------- #
# Excel cikti
# --------------------------------------------------------------------------- #

def excel_yaz(dosya: str, basliklar, satirlar, sayfa_adi: str = "Rapor",
              sayi_kolonlari=None, baslik_notu: str | None = None):
    sayi_kolonlari = set(sayi_kolonlari or [])
    kitap = Workbook()
    calisma = kitap.active
    calisma.title = (sayfa_adi or "Rapor")[:31]
    ilk = 1
    if baslik_notu:
        calisma.cell(row=1, column=1, value=baslik_notu).font = Font(bold=True, size=12)
        ilk = 3
    dolgu = PatternFill("solid", fgColor="DDE7F0")
    for j, baslik in enumerate(basliklar, start=1):
        hucre = calisma.cell(row=ilk, column=j, value=baslik)
        hucre.font = Font(bold=True)
        hucre.fill = dolgu
        hucre.alignment = Alignment(horizontal="center", wrap_text=True)
    for i, satir in enumerate(satirlar, start=ilk + 1):
        for j, deger in enumerate(satir, start=1):
            hucre = calisma.cell(row=i, column=j, value=deger)
            if (j - 1) in sayi_kolonlari and isinstance(deger, (int, float)):
                hucre.number_format = '#,##0'
    for j, baslik in enumerate(basliklar, start=1):
        genislik = max([len(str(baslik))] +
                       [len(str(s[j-1])) for s in satirlar[:200] if len(s) >= j]) + 2
        calisma.column_dimensions[get_column_letter(j)].width = min(max(genislik, 10), 45)
    calisma.freeze_panes = calisma.cell(row=ilk + 1, column=2)
    kitap.save(dosya)
    return dosya
