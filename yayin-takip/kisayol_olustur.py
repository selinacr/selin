"""Masaustune 'Yayin Takip' kisayolu olusturur (Windows).

Bir kez calistir:  python kisayol_olustur.py
Sonrasinda masaustundeki kisayola cift tiklamak yeterlidir; Anaconda Prompt
gerekmez, siyah konsol penceresi acilmaz (pythonw.exe kullanilir).
Klasoru tasirsan betigi yeni yerinde tekrar calistir.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

KISAYOL_ADI = "Yayin Takip"


def yorumlayici() -> str:
    """Konsolsuz calistiran pythonw.exe; yoksa mevcut python."""
    klasor = os.path.dirname(sys.executable)
    for ad in ("pythonw.exe", "python.exe"):
        aday = os.path.join(klasor, ad)
        if os.path.exists(aday):
            return aday
    return sys.executable


def simge(exe: str) -> str:
    """Kisayol simgesi: varsa python.exe'nin kendi simgesi."""
    aday = os.path.join(os.path.dirname(exe), "python.exe")
    return f"{aday},0" if os.path.exists(aday) else f"{exe},0"


def vbs_metni(exe: str, uygulama: str, klasor: str) -> str:
    return "\n".join([
        'Set ws = CreateObject("WScript.Shell")',
        'masaustu = ws.SpecialFolders("Desktop")',
        f'Set k = ws.CreateShortcut(masaustu & "\\{KISAYOL_ADI}.lnk")',
        f'k.TargetPath = "{exe}"',
        f'k.Arguments = """{uygulama}"""',
        f'k.WorkingDirectory = "{klasor}"',
        f'k.IconLocation = "{simge(exe)}"',
        'k.Description = "Adjunct Yayin Takip"',
        'k.Save',
        'WScript.Echo masaustu',
    ])


def olustur() -> str:
    if os.name != "nt":
        raise SystemExit("Bu betik yalnizca Windows icindir. "
                         "Linux/macOS'ta uygulamayi 'python app.py' ile acabilirsin.")
    klasor = os.path.dirname(os.path.abspath(__file__))
    uygulama = os.path.join(klasor, "app.py")
    if not os.path.exists(uygulama):
        raise SystemExit(f"app.py bulunamadi: {uygulama}")
    exe = yorumlayici()
    with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False,
                                     encoding="utf-8") as gecici:
        gecici.write(vbs_metni(exe, uygulama, klasor))
        vbs = gecici.name
    try:
        sonuc = subprocess.run(["cscript", "//nologo", vbs],
                               capture_output=True, text=True)
    finally:
        os.unlink(vbs)
    if sonuc.returncode != 0:
        raise SystemExit("Kisayol olusturulamadi:\n" + (sonuc.stderr or sonuc.stdout))
    masaustu = (sonuc.stdout or "").strip().splitlines()[-1] if sonuc.stdout.strip() else ""
    return os.path.join(masaustu, f"{KISAYOL_ADI}.lnk") if masaustu else KISAYOL_ADI


if __name__ == "__main__":
    print("Kisayol olusturuldu:", olustur())
    print("Masaustundeki 'Yayin Takip' kisayoluna cift tiklayarak acabilirsin.")
