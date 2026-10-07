"""WoS arayüzünden tarayıcı ile kayıt dışa aktarma."""

from __future__ import annotations

from pathlib import Path

from ..ayristirma import satirlari_oku, wos_ayristir
from .tarayici import indirileni_bekle, oturum

def arama_adresi(kurum: str, yil: int) -> str:
    sorgu = f"OG=({kurum}) AND PY={yil}"
    return ("https://www.webofscience.com/wos/woscc/basic-search?"
            f"search_mode=general&query={sorgu}")


def kayitlari_cek(kurum: str, yil: int, gorunur: bool = False) -> list[dict]:
    """Arama sonucunu "Full Record" Excel olarak indirip çözümler.

    Arayüz düzeni Clarivate tarafından değiştirilebilir; seçiciler bu yüzden tek yerde
    toplandı ve hata durumunda açık mesaj verilir.
    """
    with oturum(gorunur=gorunur) as sayfa:
        sayfa.goto(arama_adresi(kurum, yil))
        sayfa.wait_for_load_state("networkidle")
        if sayfa.locator("text=Sign in").count() and not sayfa.locator("text=Results").count():
            raise RuntimeError("WoS oturumu açık değil. "
                               "python -m yayin_paneli.toplayici.tarayici giris "
                               "https://www.webofscience.com ile giriş yapın.")
        sayfa.click("button:has-text('Export')")
        sayfa.click("text=Excel")
        if sayfa.locator("input[value='allRecords']").count():
            sayfa.check("input[value='allRecords']")
        if sayfa.locator("select[name='recordContent']").count():
            sayfa.select_option("select[name='recordContent']", label="Full Record")
        dosya = indirileni_bekle(sayfa, lambda: sayfa.click("button:has-text('Export')"),
                                 ad_eki=f"wos-{yil}-")
    return dosyadan_oku(dosya)


def dosyadan_oku(yol: str | Path) -> list[dict]:
    """Elle indirilmiş WoS dosyasını da aynı yoldan okur."""
    return wos_ayristir(satirlari_oku(str(yol)), Path(yol).name)["kayitlar"]
