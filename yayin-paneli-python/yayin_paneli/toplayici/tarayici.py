"""Playwright ile kalıcı tarayıcı oturumu.

Kurumsal abonelik ağ/oturum üzerinden sağlandığında kullanılan yoldur. Oturum bir kez
elle açılır (`python -m yayin_paneli.toplayici.tarayici giris`), çerezler kalıcı profilde
kalır ve sonraki toplamalar aynı profille başlar.

UYARI: Clarivate ve Elsevier kullanım şartları otomatik erişimi kısıtlar. Bu modül
yalnızca kullanıcının kendi makinesinde, kendi oturumuyla ve kendi sorumluluğunda
çalıştırılmak üzere yazılmıştır; sunucuya kurulmamalıdır. Mümkün olduğunda resmi API
yolu (`toplama_yolu = "api"`) kullanılmalıdır.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

PROFIL_YOLU = Path(os.environ.get("YAYIN_PANELI_PROFIL",
                                  Path.home() / ".yayin-paneli" / "tarayici-profili"))
INDIRME_YOLU = Path(os.environ.get("YAYIN_PANELI_INDIRME",
                                   Path.home() / ".yayin-paneli" / "indirilenler"))


class TarayiciYok(RuntimeError):
    pass


@contextmanager
def oturum(gorunur: bool = False, zaman_asimi_ms: int = 60_000):
    """Kalıcı profille bir sayfa döndürür."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as hata:  # pragma: no cover - ortama bağlı
        raise TarayiciYok(
            "Playwright kurulu değil. Kurulum: python -m pip install playwright && "
            "python -m playwright install chromium") from hata
    PROFIL_YOLU.mkdir(parents=True, exist_ok=True)
    INDIRME_YOLU.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        baglam = p.chromium.launch_persistent_context(
            str(PROFIL_YOLU), headless=not gorunur, accept_downloads=True,
            downloads_path=str(INDIRME_YOLU),
            args=["--disable-blink-features=AutomationControlled"])
        baglam.set_default_timeout(zaman_asimi_ms)
        sayfa = baglam.pages[0] if baglam.pages else baglam.new_page()
        try:
            yield sayfa
        finally:
            baglam.close()


def indirileni_bekle(sayfa, tetikleyici, ad_eki: str = "") -> Path:
    """Bir tıklamanın ürettiği dosyayı indirme klasörüne kaydeder."""
    with sayfa.expect_download() as bilgi:
        tetikleyici()
    indirme = bilgi.value
    hedef = INDIRME_YOLU / f"{ad_eki}{indirme.suggested_filename}"
    indirme.save_as(str(hedef))
    return hedef


def giris_yap(adres: str) -> None:
    """Oturumu elle açmak için görünür tarayıcı başlatır."""
    with oturum(gorunur=True, zaman_asimi_ms=0) as sayfa:
        sayfa.goto(adres)
        input("Giriş yaptıktan sonra bu pencerede Enter'a basın...")


if __name__ == "__main__":  # pragma: no cover
    import sys
    hedef = sys.argv[2] if len(sys.argv) > 2 else "https://www.webofscience.com"
    if len(sys.argv) > 1 and sys.argv[1] == "giris":
        giris_yap(hedef)
    else:
        print(__doc__)
