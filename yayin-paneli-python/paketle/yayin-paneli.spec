# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller tarifi: tek uygulama, Python kurulumu gerektirmez.

Üretmek için (her işletim sisteminde kendi üzerinde çalıştırılır):
    python -m PyInstaller paketle/yayin-paneli.spec --noconfirm
"""

import sys
from pathlib import Path

KOK = Path(SPECPATH).parent

veriler = [
    (str(KOK / "web"), "web"),
    (str(KOK / "veri" / "panel.db"), "veri"),
]

gizli = [
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    "yayin_paneli.servis", "yayin_paneli.toplayici", "yayin_paneli.toplayici.api",
    "yayin_paneli.toplayici.zamanlayici", "yayin_paneli.eslesme",
]

analiz = Analysis(
    [str(KOK / "paketle" / "baslatici.py")],
    pathex=[str(KOK)],
    datas=veriler,
    hiddenimports=gizli,
    # Paketi şişiren, panelde kullanılmayan bağımlılıklar:
    # cryptography paneldeki hiçbir yol tarafından kullanılmaz (HTTPS için stdlib ssl
    # yeterli) ve bazı ortamlarda paketleme sırasında çöküyor.
    # playwright paket icine girmez (Chromium ~150 MB); kullanici kurarsa panel bulur:
    #   python3 -m pip install playwright && python3 -m playwright install chromium
    excludes=["streamlit", "matplotlib", "tkinter", "PIL", "pytest", "playwright",
              "IPython", "notebook", "cryptography",
              # pyarrow yalnızca Streamlit sürümü için gerekli, servis tarafı kullanmıyor
              "pyarrow"],
    noarchive=False,
)

pyz = PYZ(analiz.pure)

exe = EXE(
    pyz, analiz.scripts, [],
    exclude_binaries=True,
    name="YayinPaneli",
    console=True,          # hata olursa kullanıcı görebilsin
    disable_windowed_traceback=False,
    upx=False,
    # macOS'ta imzasız ikili hiç çalışmaz; ad-hoc imza (-) PyInstaller tarafından
    # her ikiliye tek tek atılır. Sonradan "codesign --deep" ile üzerine yazmak
    # iç imzaları bozduğu için yapılmamalı.
    codesign_identity="-" if sys.platform == "darwin" else None,
    entitlements_file=None,
)

toplama = COLLECT(
    exe, analiz.binaries, analiz.datas,
    strip=False, upx=False, name="YayinPaneli",
)

app = BUNDLE(
    toplama,
    name="Yayin Paneli.app",
    bundle_identifier="edu.dogus.ardes.yayinpaneli",
    info_plist={
        "CFBundleName": "Yayın Paneli",
        "CFBundleDisplayName": "Yayın Paneli",
        "CFBundleShortVersionString": "2.0.0",
        "NSHighResolutionCapable": True,
        "LSBackgroundOnly": False,
    },
)
