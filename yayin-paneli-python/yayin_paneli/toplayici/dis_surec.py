"""Tarayıcı otomasyonunu ayrı bir Python süreci olarak çalıştırır.

Paketlenmiş uygulama kendi gömülü Python'unu kullanır ve kullanıcının sisteme kurduğu
Playwright'ı göremez. Bu modül, kendi kendine yeten küçük bir betik yazıp onu
kullanıcının Playwright kurulu Python'uyla çalıştırır; sonuç JSON olarak okunur.

Böylece paketlenmiş uygulamada da "tek düğmeyle çek" çalışır: tek koşul, makinede
Playwright kurulu bir Python bulunması.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ADAY_PYTHONLAR = [
    os.environ.get("YAYIN_PANELI_PYTHON", ""),
    shutil.which("python3") or "",
    str(Path.home() / "anaconda3" / "bin" / "python"),
    str(Path.home() / "miniconda3" / "bin" / "python"),
    str(Path.home() / "miniforge3" / "bin" / "python"),
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
    "/usr/bin/python3",
]

BETIK = r'''
import json, sys
from pathlib import Path

eylem, adres, profil, indirme, gorunur = sys.argv[1:6]
gorunur = gorunur == "1"

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(json.dumps({"durum": "playwright_yok"}))
    sys.exit(0)

Path(profil).mkdir(parents=True, exist_ok=True)
Path(indirme).mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    try:
        baglam = p.chromium.launch_persistent_context(
            profil, headless=not gorunur, accept_downloads=True,
            downloads_path=indirme,
            args=["--disable-blink-features=AutomationControlled"])
    except Exception as hata:
        print(json.dumps({"durum": "tarayici_yok", "mesaj": str(hata)}))
        sys.exit(0)
    sayfa = baglam.pages[0] if baglam.pages else baglam.new_page()
    sayfa.set_default_timeout(120000)
    try:
        sayfa.goto(adres)
        if eylem == "giris":
            # Kullanıcı girişini yapıp pencereyi kapatana kadar bekle.
            sayfa.wait_for_event("close", timeout=0)
            print(json.dumps({"durum": "tamam", "mesaj": "Oturum kaydedildi."}))
        else:
            sayfa.wait_for_load_state("networkidle")
            if sayfa.locator("input[type=password]").count():
                print(json.dumps({"durum": "giris_gerekli",
                                  "mesaj": "Giris sayfasi acildi; oturum suresi dolmus olabilir."}))
            else:
                acildi = False
                for secici in ["button:has-text('Export')", "[data-ta='export-button']",
                               "#export_results", "button:has-text('Disa aktar')"]:
                    yer = sayfa.locator(secici).first
                    if yer.count():
                        yer.click(); sayfa.wait_for_timeout(1200); acildi = True
                        break
                if not acildi:
                    print(json.dumps({"durum": "hata",
                                      "mesaj": "Export dugmesi bulunamadi; arayuz degismis olabilir."}))
                else:
                    for secici in ["text=Excel", "text=CSV", "label:has-text('Bibliographical information')",
                                   "input[value='allRecords']"]:
                        yer = sayfa.locator(secici).first
                        if yer.count():
                            try: yer.click(); sayfa.wait_for_timeout(600)
                            except Exception: pass
                    try:
                        with sayfa.expect_download(timeout=240000) as bilgi:
                            for secici in ["button:has-text('Export')", "button:has-text('Download')",
                                           "button:has-text('Indir')"]:
                                yer = sayfa.locator(secici).last
                                if yer.count():
                                    yer.click(); break
                        indirilen = bilgi.value
                        hedef = Path(indirme) / indirilen.suggested_filename
                        indirilen.save_as(str(hedef))
                        print(json.dumps({"durum": "tamam", "dosya": str(hedef),
                                          "mesaj": hedef.name + " indirildi."}))
                    except Exception as hata:
                        print(json.dumps({"durum": "hata", "mesaj": str(hata)[:400]}))
    except Exception as hata:
        if eylem == "giris" and "closed" in str(hata).lower():
            print(json.dumps({"durum": "tamam", "mesaj": "Oturum kaydedildi."}))
        else:
            print(json.dumps({"durum": "hata", "mesaj": str(hata)[:400]}))
    finally:
        try: baglam.close()
        except Exception: pass
'''


# Arama her istekte yeniden yapılmasın: her yorumlayıcı için ayrı süreç açmak yavaştır
# ve arayüz beklemede kalır. Sonuç bellekte tutulur, "Kurulumu denetle" ile sıfırlanır.
_BELLEK: dict[str, str | None] = {}


def playwrightli_python(yeniden: bool = False) -> str | None:
    """Playwright kurulu ilk Python yorumlayıcısını bulur (sonuç bellekte tutulur)."""
    if not yeniden and "yorumlayici" in _BELLEK:
        return _BELLEK["yorumlayici"]
    bulunan = None
    gorulen = set()
    for aday in ADAY_PYTHONLAR:
        if not aday or aday in gorulen or not Path(aday).exists():
            continue
        gorulen.add(aday)
        try:
            sonuc = subprocess.run([aday, "-c", "import playwright"],
                                   capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.SubprocessError):
            continue
        if sonuc.returncode == 0:
            bulunan = aday
            break
    _BELLEK["yorumlayici"] = bulunan
    return bulunan


def kurulum_komutu() -> dict:
    """Playwright kurulu değilse kullanıcıya gösterilecek komutlar."""
    yorumlayici = next((a for a in ADAY_PYTHONLAR if a and Path(a).exists()), "python3")
    return {
        "python": yorumlayici,
        "komutlar": [f'"{yorumlayici}" -m pip install playwright',
                     f'"{yorumlayici}" -m playwright install chromium'],
    }


def calistir(eylem: str, adres: str, profil: Path, indirme: Path,
             gorunur: bool = False, zaman_asimi: int = 900) -> dict:
    """Betiği ayrı süreçte çalıştırır ve JSON sonucunu döndürür."""
    yorumlayici = playwrightli_python(yeniden=True)
    if not yorumlayici:
        return {"durum": "playwright_yok", **kurulum_komutu()}
    with tempfile.TemporaryDirectory() as gecici:
        betik = Path(gecici) / "cek.py"
        betik.write_text(BETIK, encoding="utf-8")
        try:
            sonuc = subprocess.run(
                [yorumlayici, "-I", str(betik), eylem, adres, str(profil), str(indirme),
                 "1" if gorunur else "0"],
                capture_output=True, text=True, timeout=zaman_asimi)
        except subprocess.TimeoutExpired:
            return {"durum": "hata", "mesaj": "İşlem zaman aşımına uğradı."}
    cikti = (sonuc.stdout or "").strip().splitlines()
    for satir in reversed(cikti):
        try:
            return json.loads(satir)
        except json.JSONDecodeError:
            continue
    return {"durum": "hata",
            "mesaj": (sonuc.stderr or "Betik çıktı üretmedi.")[-400:]}
