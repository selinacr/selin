"""Scopus arayüzünden tarayıcı ile kayıt dışa aktarma."""

from __future__ import annotations

from pathlib import Path

from ..ayristirma import satirlari_oku, scopus_ayristir
from .tarayici import indirileni_bekle, oturum


def arama_adresi(kurum_kimligi: str, kurum: str, yil: int) -> str:
    sorgu = (f"AF-ID({kurum_kimligi})" if kurum_kimligi else f'AFFIL("{kurum}")')
    return ("https://www.scopus.com/results/results.uri?src=s&sot=b&sdt=b&"
            f"s={sorgu}+AND+PUBYEAR+%3D+{yil}")


def kayitlari_cek(kurum_kimligi: str, kurum: str, yil: int, gorunur: bool = False) -> list[dict]:
    with oturum(gorunur=gorunur) as sayfa:
        sayfa.goto(arama_adresi(kurum_kimligi, kurum, yil))
        sayfa.wait_for_load_state("networkidle")
        if sayfa.locator("text=Sign in").count() and not sayfa.locator("text=documents").count():
            raise RuntimeError("Scopus oturumu açık değil. "
                               "python -m yayin_paneli.toplayici.tarayici giris "
                               "https://www.scopus.com ile giriş yapın.")
        sayfa.click("button:has-text('Export')")
        sayfa.click("text=CSV")
        dosya = indirileni_bekle(sayfa, lambda: sayfa.click("button:has-text('Export')"),
                                 ad_eki=f"scopus-{yil}-")
    return dosyadan_oku(dosya)


def dosyadan_oku(yol: str | Path) -> list[dict]:
    return scopus_ayristir(satirlari_oku(str(yol)))["kayitlar"]
