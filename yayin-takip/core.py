"""Yayin takip cekirdek katmani.

Excel okuma, kolon eslestirme, SQLite depolama ve ozet/pivot sorgulari.
Arayuzden bagimsizdir; komut satirindan veya testlerden de kullanilabilir.
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

_AY_ANAHTAR = {
    "ocak": 1, "oca": 1, "january": 1, "jan": 1,
    "subat": 2, "sub": 2, "şubat": 2, "february": 2, "feb": 2,
    "mart": 3, "mar": 3, "march": 3,
    "nisan": 4, "nis": 4, "april": 4, "apr": 4,
    "mayis": 5, "may": 5, "mayıs": 5,
    "haziran": 6, "haz": 6, "june": 6, "jun": 6,
    "temmuz": 7, "tem": 7, "july": 7, "jul": 7,
    "agustos": 8, "agu": 8, "ağustos": 8, "august": 8, "aug": 8,
    "eylul": 9, "eyl": 9, "eylül": 9, "september": 9, "sep": 9,
    "ekim": 10, "eki": 10, "october": 10, "oct": 10,
    "kasim": 11, "kas": 11, "kasım": 11, "november": 11, "nov": 11,
    "aralik": 12, "ara": 12, "aralık": 12, "december": 12, "dec": 12,
}

# Eslestirilebilir alanlar: alan -> (etiket, zorunlu mu, baslikta aranan anahtarlar)
ALANLAR = {
    "kisi": ("Kisi / Hak sahibi", True,
             ["kisi", "kişi", "ad soyad", "adsoyad", "sanatci", "sanatçı", "hak sahibi",
              "uye", "üye", "isim", "ad", "personel", "yazar", "besteci", "icracı", "icraci"]),
    "tarih": ("Tarih / Donem", True,
              ["tarih", "donem", "dönem", "ay", "period", "date", "yayin tarihi", "yayın tarihi"]),
    "odeme_turu": ("Odeme turu", False,
                   ["odeme", "ödeme", "odeme turu", "ödeme türü", "tur", "tür", "kategori",
                    "gelir turu", "gelir türü", "tip", "hak turu", "hak türü"]),
    "eser": ("Eser / Aciklama", False,
             ["eser", "eser adi", "eser adı", "sarki", "şarkı", "parca", "parça",
              "aciklama", "açıklama", "urun", "ürün", "baslik", "başlık"]),
    "kanal": ("Kanal / Platform", False,
              ["kanal", "platform", "mecra", "yayinci", "yayıncı", "radyo", "tv", "kaynak"]),
    "adet": ("Adet / Yayin sayisi", False,
             ["adet", "sayi", "sayı", "yayin sayisi", "yayın sayısı", "tekrar", "count", "miktar"]),
    "brut": ("Brut tutar", False,
             ["brut", "brut tutar", "tutar", "gross", "toplam", "hasilat", "hasılat", "ucret", "ücret"]),
    "kesinti": ("Kesinti / Stopaj", False,
                ["kesinti", "stopaj", "vergi", "komisyon", "kdv", "indirim"]),
    "net": ("Net tutar (odenen)", False,
            ["net", "net tutar", "odenen", "ödenen", "net odeme", "net ödeme", "eline gecen"]),
}

ZORUNLU_ALANLAR = [a for a, (_, z, _) in ALANLAR.items() if z]


# --------------------------------------------------------------------------- #
# Yardimci donusturucular
# --------------------------------------------------------------------------- #

def _sadelestir(metin) -> str:
    """Baslik karsilastirmasi icin kucuk harfe indirip Turkce karakterleri sadelestirir."""
    s = str(metin or "").strip().lower()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c"), ("İ", "i")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def sayiya_cevir(deger) -> float:
    """'1.234,56 TL', '(120)', 1234.5 gibi degerleri float'a cevirir."""
    if deger is None:
        return 0.0
    if isinstance(deger, bool):
        return 0.0
    if isinstance(deger, (int, float)):
        return float(deger)
    s = str(deger).strip()
    if not s:
        return 0.0
    negatif = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("\xa0", "").replace(" ", "")
    s = re.sub(r"(?i)(tl|try|₺|\$|eur|€|usd)", "", s)
    if "," in s and "." in s:
        # Hangisi ondalik ayraci: en sagdaki isaret belirler.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # Sadece nokta var: TR bicimindeki binlik ayraci (1.234 / 2.500.000) ile
        # ondalik noktayi ayirt et. Son grup tam 3 haneyse binlik kabul edilir.
        parcalar = s.split(".")
        if len(parcalar) > 2 or (len(parcalar[-1]) == 3 and parcalar[0].lstrip("-").isdigit()):
            s = "".join(parcalar)
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", "."):
        return 0.0
    try:
        sonuc = float(s)
    except ValueError:
        return 0.0
    return -sonuc if negatif else sonuc


def tarihe_cevir(deger):
    """Hucre degerinden (yil, ay, iso_tarih|None) uretir. Cozemezse None doner."""
    if deger is None or (isinstance(deger, str) and not deger.strip()):
        return None
    if isinstance(deger, datetime):
        return deger.year, deger.month, deger.date().isoformat()
    if isinstance(deger, date):
        return deger.year, deger.month, deger.isoformat()
    if isinstance(deger, (int, float)) and not isinstance(deger, bool):
        # 202601 / 2026 gibi sayisal donemler
        tam = int(deger)
        if 190001 <= tam <= 299912:
            return tam // 100, tam % 100, None
        if 1900 <= tam <= 2999:
            return tam, 0, None
        return None

    s = str(deger).strip()
    kalip = re.match(r"^(\d{4})[-/.](\d{1,2})(?:[-/.](\d{1,2}))?$", s)
    if kalip:
        yil, ay, gun = int(kalip.group(1)), int(kalip.group(2)), kalip.group(3)
        if 1 <= ay <= 12:
            iso = date(yil, ay, int(gun)).isoformat() if gun else None
            return yil, ay, iso
    kalip = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", s)
    if kalip:
        gun, ay, yil = int(kalip.group(1)), int(kalip.group(2)), int(kalip.group(3))
        if 1 <= ay <= 12 and 1 <= gun <= 31:
            return yil, ay, date(yil, ay, gun).isoformat()
    kalip = re.match(r"^(\d{1,2})[-/.](\d{4})$", s)
    if kalip and 1 <= int(kalip.group(1)) <= 12:
        return int(kalip.group(2)), int(kalip.group(1)), None
    # "Ocak 2026", "2026 Ocak", "Oca-26"
    sade = _sadelestir(s)
    yil_bul = re.search(r"(19|20)\d{2}", sade)
    for anahtar, ay in _AY_ANAHTAR.items():
        anahtar_sade = _sadelestir(anahtar)
        if re.search(rf"\b{re.escape(anahtar_sade)}", sade):
            if yil_bul:
                return int(yil_bul.group(0)), ay, None
            kisa_yil = re.search(r"\b(\d{2})\b", sade)
            if kisa_yil:
                return 2000 + int(kisa_yil.group(1)), ay, None
    if yil_bul and len(sade) <= 6:
        return int(yil_bul.group(0)), 0, None
    return None


def donem_etiketi(yil: int, ay: int) -> str:
    return f"{yil}-{ay:02d}" if ay else f"{yil}"


# --------------------------------------------------------------------------- #
# Excel okuma / yazma
# --------------------------------------------------------------------------- #

def sayfa_adlari(dosya: str):
    kitap = load_workbook(dosya, read_only=True, data_only=True)
    try:
        return list(kitap.sheetnames)
    finally:
        kitap.close()


def excel_oku(dosya: str, sayfa: str | None = None, baslik_satiri: int = 1):
    """(basliklar, satirlar) doner. Satirlar ham hucre degerleridir."""
    kitap = load_workbook(dosya, read_only=True, data_only=True)
    try:
        calisma = kitap[sayfa] if sayfa else kitap[kitap.sheetnames[0]]
        tum = list(calisma.iter_rows(values_only=True))
    finally:
        kitap.close()
    if not tum:
        return [], []
    idx = max(1, baslik_satiri) - 1
    if idx >= len(tum):
        return [], []
    basliklar = [("" if h is None else str(h).strip()) for h in tum[idx]]
    satirlar = [s for s in tum[idx + 1:] if any(h is not None and str(h).strip() for h in s)]
    return basliklar, satirlar


def baslik_satiri_bul(dosya: str, sayfa: str | None = None, tarama: int = 15) -> int:
    """Ilk 15 satiri tarayip en cok alanla eslesen satiri baslik kabul eder (1 tabanli)."""
    kitap = load_workbook(dosya, read_only=True, data_only=True)
    try:
        calisma = kitap[sayfa] if sayfa else kitap[kitap.sheetnames[0]]
        ilk = []
        for i, satir in enumerate(calisma.iter_rows(values_only=True)):
            if i >= tarama:
                break
            ilk.append(satir)
    finally:
        kitap.close()
    en_iyi, en_iyi_puan = 1, -1
    for i, satir in enumerate(ilk, start=1):
        basliklar = [("" if h is None else str(h)) for h in satir]
        puan = len(otomatik_esle(basliklar)) + sum(1 for b in basliklar if b.strip())/100
        if puan > en_iyi_puan:
            en_iyi, en_iyi_puan = i, puan
    return en_iyi


def otomatik_esle(basliklar) -> dict:
    """Baslik metinlerinden alan -> kolon indeksi esleme onerisi uretir."""
    esleme = {}
    kullanilan = set()
    sade_basliklar = [_sadelestir(b) for b in basliklar]
    for alan, (_, _, anahtarlar) in ALANLAR.items():
        en_iyi, en_iyi_puan = None, 0
        for i, baslik in enumerate(sade_basliklar):
            if not baslik or i in kullanilan:
                continue
            for anahtar in anahtarlar:
                a = _sadelestir(anahtar)
                if baslik == a:
                    puan = 100 + len(a)
                elif baslik.startswith(a) or baslik.endswith(a):
                    puan = 60 + len(a)
                elif a in baslik:
                    puan = 40 + len(a)
                else:
                    continue
                if puan > en_iyi_puan:
                    en_iyi, en_iyi_puan = i, puan
        if en_iyi is not None:
            esleme[alan] = en_iyi
            kullanilan.add(en_iyi)
    return esleme


def excel_yaz(dosya: str, basliklar, satirlar, sayfa_adi: str = "Rapor",
              para_kolonlari=None, baslik_notu: str | None = None):
    """Basit bicimli bir Excel raporu yazar."""
    para_kolonlari = set(para_kolonlari or [])
    kitap = Workbook()
    calisma = kitap.active
    calisma.title = sayfa_adi[:31] or "Rapor"
    ilk_satir = 1
    if baslik_notu:
        calisma.cell(row=1, column=1, value=baslik_notu).font = Font(bold=True, size=12)
        ilk_satir = 3
    dolgu = PatternFill("solid", fgColor="DDE7F0")
    for j, baslik in enumerate(basliklar, start=1):
        hucre = calisma.cell(row=ilk_satir, column=j, value=baslik)
        hucre.font = Font(bold=True)
        hucre.fill = dolgu
        hucre.alignment = Alignment(horizontal="center", wrap_text=True)
    for i, satir in enumerate(satirlar, start=ilk_satir + 1):
        for j, deger in enumerate(satir, start=1):
            hucre = calisma.cell(row=i, column=j, value=deger)
            if (j - 1) in para_kolonlari and isinstance(deger, (int, float)):
                hucre.number_format = '#,##0.00'
    for j, baslik in enumerate(basliklar, start=1):
        uzunluk = max([len(str(baslik))] + [len(str(s[j-1])) for s in satirlar[:200] if len(s) >= j]) + 2
        calisma.column_dimensions[get_column_letter(j)].width = min(max(uzunluk, 10), 42)
    calisma.freeze_panes = calisma.cell(row=ilk_satir + 1, column=1)
    kitap.save(dosya)
    return dosya


# --------------------------------------------------------------------------- #
# Kayit modeli
# --------------------------------------------------------------------------- #

@dataclass
class Kayit:
    kisi: str
    yil: int
    ay: int
    tarih: str | None
    odeme_turu: str
    eser: str
    kanal: str
    adet: float
    brut: float
    kesinti: float
    net: float
    kaynak: str = ""

    def imza(self) -> str:
        ham = "|".join(str(x) for x in (
            self.kisi.lower(), self.yil, self.ay, self.tarih or "", self.odeme_turu.lower(),
            self.eser.lower(), self.kanal.lower(), round(self.adet, 4),
            round(self.brut, 2), round(self.kesinti, 2), round(self.net, 2)))
        return hashlib.sha256(ham.encode("utf-8")).hexdigest()


def satirlari_donustur(basliklar, satirlar, esleme, kaynak: str = ""):
    """Ham Excel satirlarini Kayit listesine cevirir. (kayitlar, hatalar) doner."""
    eksik = [a for a in ZORUNLU_ALANLAR if a not in esleme]
    if eksik:
        raise ValueError("Zorunlu alan eslenmedi: " + ", ".join(ALANLAR[a][0] for a in eksik))

    def al(satir, alan):
        i = esleme.get(alan)
        if i is None or i >= len(satir):
            return None
        return satir[i]

    kayitlar, hatalar = [], []
    for no, satir in enumerate(satirlar, start=1):
        kisi = str(al(satir, "kisi") or "").strip()
        if not kisi:
            hatalar.append((no, "Kisi bos"))
            continue
        cozulen = tarihe_cevir(al(satir, "tarih"))
        if not cozulen:
            hatalar.append((no, f"Tarih cozulemedi: {al(satir, 'tarih')!r}"))
            continue
        yil, ay, iso = cozulen
        brut = sayiya_cevir(al(satir, "brut"))
        kesinti = sayiya_cevir(al(satir, "kesinti"))
        net_ham = al(satir, "net")
        net = sayiya_cevir(net_ham)
        if "net" not in esleme or (net == 0 and (brut or kesinti)):
            net = brut - kesinti
        if "brut" not in esleme and net and not brut:
            brut = net + kesinti
        kayitlar.append(Kayit(
            kisi=kisi,
            yil=yil,
            ay=ay,
            tarih=iso,
            odeme_turu=str(al(satir, "odeme_turu") or "Belirtilmemis").strip() or "Belirtilmemis",
            eser=str(al(satir, "eser") or "").strip(),
            kanal=str(al(satir, "kanal") or "").strip(),
            adet=sayiya_cevir(al(satir, "adet")) if "adet" in esleme else 0.0,
            brut=brut, kesinti=kesinti, net=net, kaynak=kaynak,
        ))
    return kayitlar, hatalar


# --------------------------------------------------------------------------- #
# Veritabani
# --------------------------------------------------------------------------- #

SEMA = """
CREATE TABLE IF NOT EXISTS kayitlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kisi TEXT NOT NULL,
    yil INTEGER NOT NULL,
    ay INTEGER NOT NULL,
    tarih TEXT,
    odeme_turu TEXT NOT NULL DEFAULT 'Belirtilmemis',
    eser TEXT DEFAULT '',
    kanal TEXT DEFAULT '',
    adet REAL DEFAULT 0,
    brut REAL DEFAULT 0,
    kesinti REAL DEFAULT 0,
    net REAL DEFAULT 0,
    kaynak TEXT DEFAULT '',
    imza TEXT NOT NULL UNIQUE,
    eklenme TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_kayit_donem ON kayitlar (yil, ay);
CREATE INDEX IF NOT EXISTS ix_kayit_kisi ON kayitlar (kisi);
CREATE INDEX IF NOT EXISTS ix_kayit_odeme ON kayitlar (odeme_turu);

CREATE TABLE IF NOT EXISTS profiller (
    ad TEXT PRIMARY KEY,
    esleme TEXT NOT NULL,
    baslik_satiri INTEGER DEFAULT 1,
    guncelleme TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS aktarimlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya TEXT, sayfa TEXT, mod TEXT,
    eklenen INTEGER, atlanan INTEGER, silinen INTEGER, hatali INTEGER,
    zaman TEXT NOT NULL
);
"""


class Veritabani:
    """SQLite uzerinde kayit deposu ve ozet sorgulari."""

    def __init__(self, yol: str = VARSAYILAN_DB):
        self.yol = yol
        klasor = os.path.dirname(os.path.abspath(yol))
        if klasor:
            os.makedirs(klasor, exist_ok=True)
        self.baglanti = sqlite3.connect(yol)
        self.baglanti.row_factory = sqlite3.Row
        self.baglanti.executescript(SEMA)
        self.baglanti.commit()

    def kapat(self):
        self.baglanti.close()

    # -- yazma ------------------------------------------------------------- #

    def aktar(self, kayitlar, mod: str = "atla", dosya: str = "", sayfa: str = "", hatali: int = 0):
        """mod: 'atla' (ayni kayitlari gec) | 'donem_degistir' (dosyadaki donemleri sifirla)."""
        silinen = 0
        imlec = self.baglanti.cursor()
        if mod == "donem_degistir":
            donemler = {(k.yil, k.ay) for k in kayitlar}
            for yil, ay in donemler:
                imlec.execute("DELETE FROM kayitlar WHERE yil=? AND ay=?", (yil, ay))
                silinen += imlec.rowcount
        eklenen = atlanan = 0
        simdi = datetime.now().isoformat(timespec="seconds")
        for kayit in kayitlar:
            veri = asdict(kayit)
            veri["imza"] = kayit.imza()
            veri["eklenme"] = simdi
            try:
                imlec.execute(
                    """INSERT INTO kayitlar
                       (kisi, yil, ay, tarih, odeme_turu, eser, kanal, adet, brut, kesinti, net,
                        kaynak, imza, eklenme)
                       VALUES (:kisi,:yil,:ay,:tarih,:odeme_turu,:eser,:kanal,:adet,:brut,:kesinti,
                               :net,:kaynak,:imza,:eklenme)""", veri)
                eklenen += 1
            except sqlite3.IntegrityError:
                atlanan += 1
        imlec.execute(
            """INSERT INTO aktarimlar (dosya, sayfa, mod, eklenen, atlanan, silinen, hatali, zaman)
               VALUES (?,?,?,?,?,?,?,?)""",
            (dosya, sayfa, mod, eklenen, atlanan, silinen, hatali, simdi))
        self.baglanti.commit()
        return {"eklenen": eklenen, "atlanan": atlanan, "silinen": silinen, "hatali": hatali}

    def donem_sil(self, yil: int, ay: int | None = None) -> int:
        imlec = self.baglanti.cursor()
        if ay:
            imlec.execute("DELETE FROM kayitlar WHERE yil=? AND ay=?", (yil, ay))
        else:
            imlec.execute("DELETE FROM kayitlar WHERE yil=?", (yil,))
        self.baglanti.commit()
        return imlec.rowcount

    def hepsini_sil(self) -> int:
        imlec = self.baglanti.cursor()
        imlec.execute("DELETE FROM kayitlar")
        self.baglanti.commit()
        return imlec.rowcount

    def profil_kaydet(self, ad: str, esleme: dict, baslik_satiri: int = 1):
        import json
        self.baglanti.execute(
            "INSERT OR REPLACE INTO profiller (ad, esleme, baslik_satiri, guncelleme) VALUES (?,?,?,?)",
            (ad, json.dumps(esleme), baslik_satiri, datetime.now().isoformat(timespec="seconds")))
        self.baglanti.commit()

    def profiller(self):
        import json
        satirlar = self.baglanti.execute(
            "SELECT ad, esleme, baslik_satiri FROM profiller ORDER BY ad").fetchall()
        return {s["ad"]: (json.loads(s["esleme"]), s["baslik_satiri"]) for s in satirlar}

    # -- okuma ------------------------------------------------------------- #

    def _kosul(self, yil=None, ay=None, kisi=None, odeme_turu=None, arama=None):
        kosullar, degerler = [], []
        if yil:
            kosullar.append("yil = ?"); degerler.append(int(yil))
        if ay:
            kosullar.append("ay = ?"); degerler.append(int(ay))
        if kisi:
            kosullar.append("kisi = ?"); degerler.append(kisi)
        if odeme_turu:
            kosullar.append("odeme_turu = ?"); degerler.append(odeme_turu)
        if arama:
            kosullar.append("(kisi LIKE ? OR eser LIKE ? OR kanal LIKE ? OR odeme_turu LIKE ?)")
            degerler += [f"%{arama}%"] * 4
        return ("WHERE " + " AND ".join(kosullar) if kosullar else ""), degerler

    def yillar(self):
        return [s[0] for s in self.baglanti.execute(
            "SELECT DISTINCT yil FROM kayitlar ORDER BY yil DESC")]

    def kisiler(self):
        return [s[0] for s in self.baglanti.execute(
            "SELECT DISTINCT kisi FROM kayitlar ORDER BY kisi")]

    def odeme_turleri(self):
        return [s[0] for s in self.baglanti.execute(
            "SELECT DISTINCT odeme_turu FROM kayitlar ORDER BY odeme_turu")]

    def genel_ozet(self, **filtre):
        kosul, degerler = self._kosul(**filtre)
        satir = self.baglanti.execute(
            f"""SELECT COUNT(*) kayit, COUNT(DISTINCT kisi) kisi_sayisi,
                       COALESCE(SUM(adet),0) adet, COALESCE(SUM(brut),0) brut,
                       COALESCE(SUM(kesinti),0) kesinti, COALESCE(SUM(net),0) net
                FROM kayitlar {kosul}""", degerler).fetchone()
        return dict(satir)

    def kisi_ozet(self, **filtre):
        """Kisi bazinda toplamlar (net'e gore azalan)."""
        kosul, degerler = self._kosul(**filtre)
        return [dict(s) for s in self.baglanti.execute(
            f"""SELECT kisi, COUNT(*) kayit, COALESCE(SUM(adet),0) adet,
                       COALESCE(SUM(brut),0) brut, COALESCE(SUM(kesinti),0) kesinti,
                       COALESCE(SUM(net),0) net
                FROM kayitlar {kosul} GROUP BY kisi ORDER BY net DESC""", degerler)]

    def odeme_ozet(self, **filtre):
        kosul, degerler = self._kosul(**filtre)
        return [dict(s) for s in self.baglanti.execute(
            f"""SELECT odeme_turu, COUNT(*) kayit, COUNT(DISTINCT kisi) kisi_sayisi,
                       COALESCE(SUM(adet),0) adet, COALESCE(SUM(brut),0) brut,
                       COALESCE(SUM(kesinti),0) kesinti, COALESCE(SUM(net),0) net
                FROM kayitlar {kosul} GROUP BY odeme_turu ORDER BY net DESC""", degerler)]

    def aylik_seri(self, **filtre):
        """Donem bazinda (yil, ay) toplamlar."""
        kosul, degerler = self._kosul(**filtre)
        return [dict(s) for s in self.baglanti.execute(
            f"""SELECT yil, ay, COUNT(*) kayit, COUNT(DISTINCT kisi) kisi_sayisi,
                       COALESCE(SUM(adet),0) adet, COALESCE(SUM(brut),0) brut,
                       COALESCE(SUM(kesinti),0) kesinti, COALESCE(SUM(net),0) net
                FROM kayitlar {kosul} GROUP BY yil, ay ORDER BY yil, ay""", degerler)]

    def pivot(self, satir_alani: str = "kisi", yil: int | None = None,
              olcu: str = "net", **filtre):
        """Satir = kisi/odeme_turu/kanal, sutun = aylar. (basliklar, satirlar) doner."""
        if satir_alani not in ("kisi", "odeme_turu", "kanal", "eser"):
            raise ValueError("Gecersiz satir alani")
        if olcu not in ("net", "brut", "kesinti", "adet"):
            raise ValueError("Gecersiz olcu")
        filtre.pop("yil", None)
        kosul, degerler = self._kosul(yil=yil, **filtre)
        ham = self.baglanti.execute(
            f"""SELECT {satir_alani} anahtar, yil, ay, COALESCE(SUM({olcu}),0) deger
                FROM kayitlar {kosul} GROUP BY anahtar, yil, ay""", degerler).fetchall()
        if yil:
            sutunlar = list(range(1, 13))
            sutun_basliklari = AY_ADLARI[:]
            anahtarla = lambda s: s["ay"] if 1 <= s["ay"] <= 12 else None
        else:
            donemler = sorted({(s["yil"], s["ay"]) for s in ham})
            sutunlar = donemler
            sutun_basliklari = [donem_etiketi(y, a) for y, a in donemler]
            anahtarla = lambda s: (s["yil"], s["ay"])
        indeks = {s: i for i, s in enumerate(sutunlar)}
        tablo = {}
        for s in ham:
            sutun = anahtarla(s)
            if sutun is None:
                continue
            satir = tablo.setdefault(s["anahtar"], [0.0] * len(sutunlar))
            satir[indeks[sutun]] += float(s["deger"] or 0)
        satirlar = [[ad] + degerler_ + [sum(degerler_)] for ad, degerler_ in tablo.items()]
        satirlar.sort(key=lambda r: r[-1], reverse=True)
        etiket = {"kisi": "Kisi", "odeme_turu": "Odeme turu",
                  "kanal": "Kanal", "eser": "Eser"}[satir_alani]
        return [etiket] + sutun_basliklari + ["Toplam"], satirlar

    def kayitlar(self, limit: int = 2000, **filtre):
        kosul, degerler = self._kosul(**filtre)
        return [dict(s) for s in self.baglanti.execute(
            f"""SELECT id, kisi, yil, ay, tarih, odeme_turu, eser, kanal, adet, brut, kesinti, net,
                       kaynak
                FROM kayitlar {kosul} ORDER BY yil DESC, ay DESC, kisi LIMIT ?""",
            degerler + [limit])]

    def kisi_yillik(self, kisi: str):
        """Bir kisinin yil bazinda ve odeme turu bazinda dokumu."""
        yillik = [dict(s) for s in self.baglanti.execute(
            """SELECT yil, COALESCE(SUM(brut),0) brut, COALESCE(SUM(kesinti),0) kesinti,
                      COALESCE(SUM(net),0) net, COUNT(*) kayit
               FROM kayitlar WHERE kisi=? GROUP BY yil ORDER BY yil DESC""", (kisi,))]
        turler = [dict(s) for s in self.baglanti.execute(
            """SELECT odeme_turu, COALESCE(SUM(net),0) net, COUNT(*) kayit
               FROM kayitlar WHERE kisi=? GROUP BY odeme_turu ORDER BY net DESC""", (kisi,))]
        return yillik, turler

    def son_aktarimlar(self, limit: int = 20):
        return [dict(s) for s in self.baglanti.execute(
            "SELECT * FROM aktarimlar ORDER BY id DESC LIMIT ?", (limit,))]
