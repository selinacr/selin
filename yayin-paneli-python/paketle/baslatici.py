"""Tek dosyalık uygulamanın giriş noktası.

PyInstaller ile paketlendiğinde kullanıcı yalnızca uygulamaya çift tıklar: Python
kurulumu, terminal ya da komut gerekmez. Bu betik boş bir port bulur, servisi başlatır
ve varsayılan tarayıcıda paneli açar.

Veritabanı uygulamanın içinde salt okunur durduğu için ilk açılışta kullanıcının veri
klasörüne kopyalanır; sonraki açılışlarda oradaki kopya kullanılır, böylece senkron ve
onaylar kalıcı olur.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def kaynak_klasoru() -> Path:
    """Paketlenmiş dosyaların kök klasörü (geliştirmede proje klasörü)."""
    gomulu = getattr(sys, "_MEIPASS", None)
    return Path(gomulu) if gomulu else Path(__file__).resolve().parent.parent


def veri_klasoru() -> Path:
    """Kullanıcının yazılabilir veri klasörü."""
    if sys.platform == "darwin":
        taban = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        taban = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        taban = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    klasor = taban / "YayinPaneli"
    klasor.mkdir(parents=True, exist_ok=True)
    return klasor


def veritabanini_hazirla() -> Path:
    """Gömülü veritabanını ilk açılışta kullanıcı klasörüne kopyalar."""
    hedef = veri_klasoru() / "panel.db"
    if not hedef.exists():
        gomulu = kaynak_klasoru() / "veri" / "panel.db"
        if gomulu.exists():
            shutil.copy2(gomulu, hedef)
    return hedef


def bos_port(tercih: int = 8787) -> int:
    """Tercih edilen port doluysa işletim sisteminin verdiği boş portu kullanır."""
    for aday in (tercih, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", aday))
                return s.getsockname()[1]
            except OSError:
                continue
    return tercih


def main() -> None:
    os.environ.setdefault("YAYIN_PANELI_DB", str(veritabanini_hazirla()))
    os.environ.setdefault("YAYIN_PANELI_WEB", str(kaynak_klasoru() / "web"))
    os.environ["YAYIN_PANELI_PAKET"] = "1"      # arayüzdeki "Kapat" düğmesini açar

    import uvicorn

    from yayin_paneli.servis import izleyici, uygulama

    izleyici.basla()          # İndirilenler klasörü baştan izlenir

    port = bos_port()
    adres = f"http://127.0.0.1:{port}/"
    sunucu = uvicorn.Server(uvicorn.Config(uygulama, host="127.0.0.1", port=port,
                                           log_level="warning"))

    def tarayiciyi_ac() -> None:
        for _ in range(60):
            if sunucu.started:
                break
            time.sleep(0.25)
        webbrowser.open(adres)

    threading.Thread(target=tarayiciyi_ac, daemon=True).start()
    print(f"Yayın Paneli çalışıyor: {adres}", flush=True)
    print("Tarayıcı kendiliğinden açılmazsa bu adresi kopyalayın.", flush=True)
    print("Kapatmak için paneldeki «Kapat» düğmesini kullanın ya da bu pencereyi kapatın.",
          flush=True)
    sunucu.run()


if __name__ == "__main__":
    main()
