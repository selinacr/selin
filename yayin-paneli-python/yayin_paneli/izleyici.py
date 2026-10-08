"""İndirilenler klasörünü izleyip WoS/Scopus dosyalarını kendiliğinden içeri alır.

Kullanıcı kendi tarayıcısında kütüphane girişiyle açtığı WoS/Scopus sayfasında yalnızca
"Export" düğmesine basar. Dosya İndirilenler klasörüne düştüğü anda bu modül dosyanın
türünü tanır, çözümler ve veritabanına yazar. Böylece dosya seçme, yükleme, klasör
bulma adımlarının hiçbiri gerekmez.

Giriş bilgileri hiçbir yerde saklanmaz ve kullanılmaz; oturum kullanıcının kendi
tarayıcısındadır.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .ayristirma import (jcr_ayristir, personel_ayristir, satirlari_oku, scopus_ayristir,
                         scopus_kaynak_ayristir, wos_ayristir, yazar_metrik_ayristir)
from .aylik import ay_ayristir
from .eslesme import kuyrugu_tazele
from .metin import sade

gunlukcu = logging.getLogger("yayin_paneli.izleyici")

UZANTILAR = {".xls", ".xlsx", ".csv"}
YOKSAY = {".crdownload", ".part", ".download", ".tmp"}


def varsayilan_klasor() -> Path:
    return Path.home() / "Downloads"


# --- dosya türü tanıma ----------------------------------------------------
def tur_bul(basliklar: list) -> str:
    """Başlık satırından dosya türünü çıkarır."""
    duz = {sade(b) for b in basliklar if b}
    metin = " | ".join(sorted(duz))

    # sade() noktalama işaretlerini düşürür: "UT (Unique WOS ID)" → "ut unique wos id"
    if "ut unique wos id" in duz or ("publication year" in duz and "addresses" in duz):
        return "wos"
    if "eid" in duz or ("source title" in duz and "document type" in duz):
        return "scopus"
    if "jif quartile" in duz or "jcr year" in duz:
        return "jcr"
    # Dergi listeleri yazar listelerinden önce denenir: SCImago dosyasında hem
    # "H index" hem "SJR Best Quartile" sütunu bulunur, bu bir dergi listesidir.
    if "citescore" in metin or "highest percentile" in duz or "quartile" in metin:
        return "scopus_kaynak"
    if {"ad", "soyad"} <= duz or "adi soyadi" in duz:
        return "personel"
    if "h-index" in duz or "h index" in duz:
        return "yazar"
    if "puan" in duz and ("eser adi" in duz or "dergi adi" in metin):
        return "aylik"
    return ""


def dosyayi_al(depo, yol: Path) -> dict:
    """Tek dosyayı tanır, çözümler ve depoya yazar."""
    satirlar = satirlari_oku(str(yol))
    if not satirlar:
        return {"dosya": yol.name, "tur": "", "durum": "bos"}

    # Başlık ilk satırda olmayabilir (puantaj tabloları gibi).
    tur = ""
    for satir in satirlar[:15]:
        tur = tur_bul(satir or [])
        if tur:
            break
    if not tur:
        return {"dosya": yol.name, "tur": "", "durum": "taninmadi"}

    if tur == "wos":
        sonuc = wos_ayristir(satirlar, yol.name)
        adet = len(sonuc["kayitlar"])
        for yil in {k["yil"] for k in sonuc["kayitlar"] if k.get("yil")}:
            depo.kayitlari_ekle([k for k in sonuc["kayitlar"] if k["yil"] == yil], "WoS", yil)
        kuyrugu_tazele(depo)
    elif tur == "scopus":
        sonuc = scopus_ayristir(satirlar, yol.name)
        adet = len(sonuc["kayitlar"])
        for yil in {k["yil"] for k in sonuc["kayitlar"] if k.get("yil")}:
            depo.kayitlari_ekle([k for k in sonuc["kayitlar"] if k["yil"] == yil], "Scopus", yil)
        kuyrugu_tazele(depo)
    elif tur == "jcr":
        satirlar_q = jcr_ayristir(satirlar, _yil_bul(yol.name))
        depo.dergi_metrik_ekle(satirlar_q)
        adet = len(satirlar_q)
    elif tur == "scopus_kaynak":
        satirlar_q = scopus_kaynak_ayristir(satirlar, _yil_bul(yol.name))
        depo.dergi_metrik_ekle(satirlar_q)
        adet = len(satirlar_q)
    elif tur == "yazar":
        kaynak = "Scopus" if "scopus" in sade(yol.name) else "WoS"
        metrikler = yazar_metrik_ayristir(satirlar, kaynak)
        depo.kisi_metrik_ekle(metrikler)
        adet = len(metrikler)
    elif tur == "personel":
        kisiler = personel_ayristir(satirlar)
        depo.yaz("personel", kisiler)
        kuyrugu_tazele(depo)
        adet = len(kisiler)
    else:  # aylık ödeme tablosu
        sonuc = ay_ayristir(satirlar, yol.name)
        depo.ay_ekle(sonuc["donem"], sonuc["kayitlar"])
        adet = len(sonuc["kayitlar"])

    return {"dosya": yol.name, "tur": tur, "adet": adet, "durum": "alindi",
            "zaman": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _yil_bul(ad: str) -> int | None:
    for parca in str(ad).replace(".", " ").replace("_", " ").replace("-", " ").split():
        if parca.isdigit() and len(parca) == 4 and 1990 < int(parca) < 2100:
            return int(parca)
    return None


# --- izleyici --------------------------------------------------------------
@dataclass
class Izleyici:
    depo: object
    klasor: Path = field(default_factory=varsayilan_klasor)
    aralik_sn: float = 3.0
    gecmis: list[dict] = field(default_factory=list)
    _gorulen: dict = field(default_factory=dict)
    _dur: threading.Event = field(default_factory=threading.Event)
    _is: threading.Thread | None = None

    def __post_init__(self) -> None:
        self.klasor = Path(self.klasor)
        # Başlarken var olan dosyalar "görülmüş" sayılır; yalnızca yeni inenler alınır.
        for yol in self._adaylar():
            self._gorulen[str(yol)] = (yol.stat().st_mtime, yol.stat().st_size)

    def _adaylar(self) -> list[Path]:
        if not self.klasor.is_dir():
            return []
        return [y for y in self.klasor.iterdir()
                if y.is_file() and y.suffix.lower() in UZANTILAR
                and not y.name.startswith((".", "~$"))]

    def bir_tarama(self) -> list[dict]:
        """Yeni ve indirmesi bitmiş dosyaları alır."""
        alinanlar = []
        for yol in self._adaylar():
            try:
                bilgi = (yol.stat().st_mtime, yol.stat().st_size)
            except OSError:
                continue
            onceki = self._gorulen.get(str(yol))
            if onceki == bilgi:
                continue
            # Dosya hâlâ iniyor olabilir: boyutu sabitlenene kadar bekle.
            self._gorulen[str(yol)] = bilgi
            if onceki is None and bilgi[1] == 0:
                continue
            if onceki is not None and onceki[1] != bilgi[1]:
                continue
            if any(yol.with_suffix(yol.suffix + e).exists() for e in YOKSAY):
                continue
            try:
                sonuc = dosyayi_al(self.depo, yol)
            except Exception as hata:          # bozuk dosya izlemeyi durdurmasın
                gunlukcu.warning("%s alınamadı: %s", yol.name, hata)
                sonuc = {"dosya": yol.name, "tur": "", "durum": "hata", "mesaj": str(hata)}
            if sonuc["durum"] != "taninmadi":
                self.gecmis.insert(0, sonuc)
                del self.gecmis[20:]
                alinanlar.append(sonuc)
        return alinanlar

    def _dongu(self) -> None:
        while not self._dur.wait(self.aralik_sn):
            try:
                self.bir_tarama()
            except Exception as hata:          # pragma: no cover - döngü ayakta kalmalı
                gunlukcu.exception("İzleme turu başarısız: %s", hata)

    def basla(self) -> None:
        if self.calisiyor:
            return
        self._dur.clear()
        self._is = threading.Thread(target=self._dongu, name="yayin-paneli-izleyici",
                                    daemon=True)
        self._is.start()

    def dur(self) -> None:
        self._dur.set()
        if self._is:
            self._is.join(timeout=5)

    @property
    def calisiyor(self) -> bool:
        return bool(self._is and self._is.is_alive())


# --- hazır arama bağlantıları ---------------------------------------------
# Çeyreklik ve h-indeksi kayıt dışa aktarımlarında yer almaz; bunlar ayrı
# listelerden gelir. Hepsi kütüphane girişiyle açılır ve dosya olarak indirilir.
# Giriş gerektirmeyen, panelin kendi indirebileceği listeler.
ACIK_KAYNAKLAR = [
    {
        "kod": "scopus_kaynak_listesi",
        "ad": "Scopus dergi listesi (CiteScore + yüzdelik + SJR)",
        "adres": "https://www.elsevier.com/products/scopus/content",
        "aciklama": "Scopus'un kendi yayımladığı dergi listesi. Giriş gerektirmez; "
                    "panel doğrudan indirmeyi dener. Adres değişirse aşağıdan "
                    "güncelleyebilirsiniz.",
    },
]

METRIK_KAYNAKLARI = [
    {
        "ad": "JCR — WoS çeyreklikleri",
        "adres": "https://jcr.clarivate.com/jcr/browse-journals",
        "nasil": "Journals sekmesinde filtreyi kaldırın, sağ üstten Export → XLS/CSV. "
                 "Dosyada «JIF Quartile» sütunu bulunmalı.",
        "tur": "jcr",
    },
    {
        "ad": "Scopus Sources — Scopus çeyreklikleri",
        "adres": "https://www.scopus.com/sources.uri",
        "nasil": "Sayfadaki «Download Scopus Source List» bağlantısı tüm dergileri "
                 "CiteScore, yüzdelik dilim ve SJR ile birlikte tek dosyada verir.",
        "tur": "scopus_kaynak",
    },
    {
        "ad": "WoS — yazar h-indeksleri",
        "adres": "https://www.webofscience.com/wos/author/search",
        "nasil": "Kurum adıyla arayıp yazarları seçin, «Export» ile h-index ve "
                 "atıf sütunlarını indirin.",
        "tur": "yazar",
    },
    {
        "ad": "Scopus — yazar h-indeksleri",
        "adres": "https://www.scopus.com/search/form.uri?display=authorLookup",
        "nasil": "Affiliation olarak kurumu seçip yazarları listeleyin, "
                 "«Export refined list» ile h-index ve atıfları indirin.",
        "tur": "yazar",
    },
]


def adresten_indir(adres: str, klasor: Path, ad: str | None = None) -> Path:
    """Verilen adresteki dosyayı izlenen klasöre indirir.

    Giriş gerektiren bir adres verilirse sunucu HTML giriş sayfası döndürür; bu durumda
    dosya tanınmaz ve kullanıcıya açık hata gösterilir.
    """
    import urllib.error
    import urllib.request

    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    istek = urllib.request.Request(adres, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36",
    })
    try:
        with urllib.request.urlopen(istek, timeout=120) as yanit:
            icerik_turu = yanit.headers.get("Content-Type", "")
            if "text/html" in icerik_turu:
                raise RuntimeError(
                    "Adres dosya değil web sayfası döndürdü. Muhtemelen giriş gerekiyor "
                    "ya da indirme bağlantısı sayfanın içinde. Sayfayı tarayıcınızda "
                    "açıp dosyayı elle indirin; panel İndirilenler klasöründen alır.")
            dosya_adi = ad or _indirme_adi(yanit, adres)
            hedef = klasor / dosya_adi
            hedef.write_bytes(yanit.read())
    except urllib.error.HTTPError as hata:
        raise RuntimeError(f"Sunucu {hata.code} döndürdü: {hata.reason}") from hata
    except urllib.error.URLError as hata:
        raise RuntimeError(f"Adrese ulaşılamadı: {hata.reason}") from hata
    return hedef


def _indirme_adi(yanit, adres: str) -> str:
    import re as _re
    import urllib.parse
    tanim = yanit.headers.get("Content-Disposition", "")
    eslesme = _re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', tanim)
    if eslesme:
        return urllib.parse.unquote(eslesme.group(1)).strip()
    yol = urllib.parse.urlparse(adres).path
    ad = Path(yol).name or "indirilen"
    return ad if Path(ad).suffix.lower() in UZANTILAR else ad + ".xlsx"


def yazar_profili_baglantilari(ad: str) -> dict[str, str]:
    """Bir kişinin iki veritabanındaki yazar arama sayfası."""
    import urllib.parse
    q = urllib.parse.quote(ad)
    return {
        "wos": f"https://www.webofscience.com/wos/author/search?authorName={q}",
        "scopus": "https://www.scopus.com/results/authorNamesList.uri?st1="
                  f"{q}&orcidId=&affiliationId=",
    }


def arama_baglantilari(ayarlar: dict, yillar: list[int]) -> list[dict]:
    """Kullanıcının kendi tarayıcısında açacağı, kuruma göre hazırlanmış aramalar."""
    import urllib.parse

    kurum = ayarlar.get("wos_kurum") or ayarlar.get("kurum_sorgusu") or "Dogus University"
    af_id = ayarlar.get("scopus_kurum_kimligi") or ""
    baglantilar = []
    for yil in yillar:
        wos_sorgu = urllib.parse.quote(f'OG=({kurum}) AND PY={yil}')
        scopus_sorgu = urllib.parse.quote(
            (f"AF-ID({af_id})" if af_id else f'AFFIL("{kurum}")') + f" AND PUBYEAR = {yil}")
        baglantilar.append({
            "yil": yil,
            "wos": "https://www.webofscience.com/wos/woscc/basic-search?"
                   f"search_mode=general&query={wos_sorgu}",
            "scopus": f"https://www.scopus.com/results/results.uri?src=s&sot=b&sdt=b&s={scopus_sorgu}",
        })
    return baglantilar
