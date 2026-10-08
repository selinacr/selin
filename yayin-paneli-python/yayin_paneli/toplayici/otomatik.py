"""Kullanıcının kendi makinesinde, kendi oturumuyla tarayıcı otomasyonu.

Panel bir Chromium penceresi açar. Kullanıcı **bir kez** kütüphane girişini yapar;
çerezler kalıcı profilde kalır. Sonraki "Veri çek" tıklamalarında pencere arka planda
açılır, arama yapılır, Export düğmesine basılır ve inen dosya izlenen klasöre düşer —
oradan izleyici devralır.

Giriş bilgileri panelde saklanmaz, istenmez ve görülmez; oturum tarayıcı profilindedir.

UYARI: Clarivate ve Elsevier kullanım şartları otomatik erişimi kısıtlar. Bu modül
yalnızca kullanıcının kendi makinesinde, kendi oturumuyla, kendi sorumluluğunda
çalıştırılmak üzere yazılmıştır.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tarayici import PROFIL_YOLU, TarayiciYok, oturum

# WoS ve Scopus arayüzleri değişebildiği için tüm seçiciler tek yerde toplandı.
# Bir düğme bulunamazsa açık hata verilir, sessizce boş dönülmez.
WOS_ADIMLARI = [
    ("Export menüsü", ["button:has-text('Export')", "[data-ta='export-button']"]),
    ("Excel seçeneği", ["text=Excel", "button:has-text('Excel')"]),
    ("Tüm kayıtlar", ["input[value='allRecords']", "text=Records from:"]),
    ("Full Record", ["select[name='recordContent']", "text=Full Record"]),
    ("İndir", ["button:has-text('Export')", "button:has-text('Download')"]),
]

SCOPUS_ADIMLARI = [
    ("Export menüsü", ["button:has-text('Export')", "#export_results"]),
    ("CSV seçeneği", ["text=CSV", "label:has-text('CSV')"]),
    ("Bibliyografik bilgi", ["label:has-text('Bibliographical information')"]),
    ("İndir", ["button:has-text('Export')", "button:has-text('Download')"]),
]


@dataclass
class Sonuc:
    durum: str                 # "tamam" | "giris_gerekli" | "hata"
    mesaj: str = ""
    dosya: str = ""


def giris_var_mi() -> bool:
    """Kalıcı profilde daha önce giriş yapılmış mı?"""
    return PROFIL_YOLU.is_dir() and any(PROFIL_YOLU.iterdir())


def giris_penceresi(adres: str) -> Sonuc:
    """Görünür bir pencere açar; kullanıcı girişini yapıp pencereyi kapatır."""
    try:
        with oturum(gorunur=True, zaman_asimi_ms=0) as sayfa:
            sayfa.goto(adres)
            sayfa.wait_for_event("close", timeout=0)
    except TarayiciYok as hata:
        return Sonuc("hata", str(hata))
    except Exception as hata:
        # Pencere kapatıldığında da buraya düşülebilir; bu bir hata değil.
        if "closed" in str(hata).lower():
            return Sonuc("tamam", "Oturum kaydedildi.")
        return Sonuc("hata", str(hata))
    return Sonuc("tamam", "Oturum kaydedildi.")


def _tikla(sayfa, ad: str, seciciler: list[str], zorunlu: bool = True) -> bool:
    for secici in seciciler:
        yer = sayfa.locator(secici).first
        if yer.count():
            yer.click()
            sayfa.wait_for_timeout(800)
            return True
    if zorunlu:
        raise RuntimeError(
            f"«{ad}» bulunamadı. Arayüz değişmiş olabilir ya da oturum kapalıdır. "
            "Veri çek sekmesinden sayfayı elle açıp Export'a basın; panel inen dosyayı "
            "yine kendiliğinden alır.")
    return False


def cek(kaynak: str, adres: str, indirme_klasoru: Path, gorunur: bool = False) -> Sonuc:
    """Verilen arama adresini açar, dışa aktarmayı tetikler ve dosyayı indirir."""
    adimlar = WOS_ADIMLARI if kaynak == "WoS" else SCOPUS_ADIMLARI
    if not giris_var_mi():
        return Sonuc("giris_gerekli",
                     f"{kaynak} oturumu yok. Önce «Bir kez giriş yap» düğmesini kullanın.")
    try:
        with oturum(gorunur=gorunur) as sayfa:
            sayfa.goto(adres)
            sayfa.wait_for_load_state("networkidle")
            if sayfa.locator("input[type=password]").count():
                return Sonuc("giris_gerekli",
                             f"{kaynak} giriş sayfası açıldı; oturum süresi dolmuş olabilir.")
            for ad, seciciler in adimlar[:-1]:
                _tikla(sayfa, ad, seciciler, zorunlu=ad in ("Export menüsü",))
            ad, seciciler = adimlar[-1]
            with sayfa.expect_download(timeout=180_000) as bilgi:
                _tikla(sayfa, ad, seciciler)
            indirme = bilgi.value
            hedef = Path(indirme_klasoru) / f"{kaynak.lower()}-{indirme.suggested_filename}"
            indirme.save_as(str(hedef))
            return Sonuc("tamam", f"{hedef.name} indirildi.", str(hedef))
    except TarayiciYok as hata:
        return Sonuc("hata", str(hata))
    except Exception as hata:
        return Sonuc("hata", str(hata))
