"""FastAPI servisi: JSON API + `web/` altındaki PWA.

Çalıştırmak için:
    python -m uvicorn yayin_paneli.servis:uygulama --port 8787
ya da
    python -m yayin_paneli.servis
"""

from __future__ import annotations

import os
import signal
import threading
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .analiz import Panel
from .depo import Depo
from .eslesme import kuyrugu_tazele
from .izleyici import (METRIK_KAYNAKLARI, Izleyici, arama_baglantilari,
                       varsayilan_klasor, yazar_profili_baglantilari)
from .toplayici.zamanlayici import Zamanlayici

# Paketlenmiş uygulamada web dosyaları gömülü klasörden gelir.
WEB = Path(os.environ.get("YAYIN_PANELI_WEB")
           or Path(__file__).resolve().parent.parent / "web")
PAKET = os.environ.get("YAYIN_PANELI_PAKET") == "1"

uygulama = FastAPI(title="Doğuş Üniversitesi Yayın Paneli", version="2.0")
depo = Depo()
zamanlayici = Zamanlayici(depo)
izleyici = Izleyici(depo, Path(depo.ayarlar().get("indirilenler") or varsayilan_klasor()))


def panel_kur(kaynak: str = "hepsi", bildiri: bool = True) -> Panel:
    veri = depo.hepsini_oku()
    panel = Panel(kayitlar=veri["kurum_kayitlari"], personel=veri["personel"],
                  adjunct=veri["adjunct"], ad_esleme=veri["ad_esleme"],
                  takma_adlar=veri["takma_adlar"],
                  dergi_metrikleri=veri["dergi_metrikleri"],
                  kisi_metrikleri=veri["kisi_metrikleri"])
    panel.kaynak_secimi = kaynak if kaynak in ("WoS", "Scopus", "ortak") else "hepsi"
    panel.bildiri_dahil = bildiri
    return panel


def _tablo(cerceve: pd.DataFrame) -> dict:
    if cerceve is None or getattr(cerceve, "empty", True):
        return {"sutunlar": [], "satirlar": []}
    temiz = cerceve.where(pd.notna(cerceve), None)
    return {"sutunlar": list(temiz.columns),
            "satirlar": temiz.to_dict(orient="records")}


@uygulama.get("/api/durum")
def durum() -> dict:
    veri = depo.hepsini_oku()
    gunluk = depo.senk_gunlugu(10)
    son = gunluk[0] if gunluk else None
    return {
        "veritabani": str(depo.yol.resolve()),
        "kayit": len(veri["kurum_kayitlari"]),
        "personel": len(veri["personel"]),
        "adjunct": len(veri["adjunct"]),
        "dergi_metrik": len(veri["dergi_metrikleri"]),
        "kisi_metrik": len(veri["kisi_metrikleri"]),
        "metrik_kaynaklari": {
            kaynak: sum(1 for s in veri["dergi_metrikleri"] if s["kaynak"] == kaynak)
            for kaynak in sorted({s["kaynak"] for s in veri["dergi_metrikleri"]})},
        "yazar_kaynaklari": {
            kaynak: sum(1 for s in veri["kisi_metrikleri"] if s["kaynak"] == kaynak)
            for kaynak in sorted({s["kaynak"] for s in veri["kisi_metrikleri"]})},
        "bekleyen_onay": len(depo.kuyruk()),
        "kaynaklar": sorted({(k.get("kaynak") or "WoS") for k in veri["kurum_kayitlari"]}),
        "ayarlar": depo.ayarlar(),
        "zamanlayici": zamanlayici.calisiyor,
        "paket": PAKET,
        "izleyici": {
            "calisiyor": izleyici.calisiyor,
            "klasor": str(izleyici.klasor),
            "var": izleyici.klasor.is_dir(),
            "gecmis": izleyici.gecmis,
        },
        "son_senk": son,
        "gunluk": gunluk,
    }


@uygulama.get("/api/analiz")
def analiz(kaynak: str = "hepsi", senaryo: str = "A", yil: str = "tumu",
           bildiri: bool = True) -> dict:
    panel = panel_kur(kaynak, bildiri)
    if not panel.kayitlar:
        raise HTTPException(404, f"Veritabanında hiç yayın kaydı yok. Okunan dosya: "
                                 f"{depo.yol.resolve()}")
    zengin, bildiri = panel.zenginlestir()
    secili = panel.suzulmus(senaryo, yil)
    siniflanan = [k for k in secili if k["q"] in ("Q1", "Q2", "Q3", "Q4")]
    personel = panel.personel_sayisi(senaryo)
    quartile, quartile_notu = panel.quartile(yil)
    fakulte, fakulte_notu = panel.fakulte(senaryo, yil)
    kisi, kisi_notu = panel.kisi_bazli(senaryo, yil)
    return {
        "kutular": {
            "yayin": len(secili),
            "personel": personel,
            "kisi_basi": round(len(secili) / personel, 2) if personel else 0,
            "oa_orani": round(100 * sum(1 for k in secili if k["oa_var"]) / len(secili), 1)
            if secili else 0,
            "q1_payi": round(100 * sum(1 for k in siniflanan if k["q"] == "Q1") / len(siniflanan), 1)
            if siniflanan else 0,
            "tekil": len(zengin), "bildiri": bildiri, "bildiri_dahil": panel.bildiri_dahil,
        },
        "yillar": sorted({k["yil"] for k in zengin if k["yil"]}),
        "ozet": _tablo(panel.ozet(yil)),
        "yil_bazli": _tablo(panel.yil_bazli()),
        "quartile": _tablo(quartile), "quartile_notu": quartile_notu,
        "quartile_karsilastirma": _tablo(panel.quartile_karsilastirma(senaryo, yil)),
        "indeks": _tablo(panel.indeks(yil)),
        "acik_erisim": _tablo(panel.acik_erisim()),
        "fakulte": _tablo(fakulte), "fakulte_notu": fakulte_notu,
        "kisi": _tablo(kisi), "kisi_notu": kisi_notu,
        "kisi_q": _tablo(panel.kisi_q_dagilimi(senaryo, yil)),
        "dergi": _tablo(panel.dergi(senaryo, yil).head(200)),
    }


@uygulama.get("/api/kisi/{ad}")
def kisi_detayi(ad: str, kaynak: str = "hepsi", senaryo: str = "A",
                bildiri: bool = True) -> dict:
    """Tek kişinin yıl yıl yayınları, çeyreklik dağılımı ve iki kaynaktaki h-indeksi."""
    panel = panel_kur(kaynak, bildiri)
    cerceve, _ = panel.kisi_bazli(senaryo, "tumu")
    if cerceve.empty:
        raise HTTPException(404, "Kişi bulunamadı.")
    satirlar = cerceve[cerceve["Kişi"].str.casefold() == ad.casefold()]
    if satirlar.empty:
        satirlar = cerceve[cerceve["Kişi"].str.contains(ad, case=False, na=False)]
    if satirlar.empty:
        raise HTTPException(404, "Kişi bulunamadı.")
    q_cerceve = panel.kisi_q_dagilimi(senaryo, "tumu")
    q_satir = q_cerceve[q_cerceve["Kişi"] == satirlar.iloc[0]["Kişi"]] \
        if not q_cerceve.empty else q_cerceve
    return {"ozet": _tablo(satirlar), "quartile": _tablo(q_satir),
            "profiller": yazar_profili_baglantilari(satirlar.iloc[0]["Kişi"])}


@uygulama.get("/api/onay")
def onay_listesi(durum_filtresi: str = "bekliyor") -> dict:
    return {"kayitlar": depo.kuyruk(durum_filtresi)}


class OnayKarari(BaseModel):
    ham: str
    durum: str = "onayli"          # "onayli" | "reddedildi"
    hedef: str = ""
    tur: str = "personel"


@uygulama.post("/api/onay")
def onay_ver(karar: OnayKarari) -> dict:
    if karar.durum not in ("onayli", "reddedildi"):
        raise HTTPException(400, "durum 'onayli' ya da 'reddedildi' olmalı.")
    if karar.durum == "onayli" and not karar.hedef:
        raise HTTPException(400, "Onay için hedef kişi gerekli.")
    depo.kuyruk_karari(karar.ham, karar.durum, karar.hedef, karar.tur)
    return {"bekleyen": len(depo.kuyruk())}


@uygulama.post("/api/onay/tazele")
def onay_tazele() -> dict:
    return kuyrugu_tazele(depo)


class AyarGuncelleme(BaseModel):
    toplama_yolu: str | None = None
    kurum_sorgusu: str | None = None
    wos_kurum: str | None = None
    scopus_kurum_kimligi: str | None = None
    ilk_yil: int | None = None
    senk_aralik_dk: int | None = None


@uygulama.post("/api/ayarlar")
def ayar_guncelle(guncelleme: AyarGuncelleme) -> dict:
    yeniler = {k: v for k, v in guncelleme.model_dump().items() if v is not None}
    return depo.ayar_yaz(yeniler)


@uygulama.get("/api/baglantilar")
def baglantilar() -> dict:
    """Kullanıcının kendi tarayıcısında açacağı hazır WoS/Scopus aramaları."""
    ayarlar = depo.ayarlar()
    ilk = int(ayarlar.get("ilk_yil") or 2022)
    from datetime import datetime
    yillar = list(range(ilk, datetime.now().year + 2))
    return {"yillar": arama_baglantilari(ayarlar, yillar),
            "metrikler": METRIK_KAYNAKLARI,
            "klasor": str(izleyici.klasor)}


class IzleyiciAyari(BaseModel):
    klasor: str | None = None


@uygulama.post("/api/izleyici/{eylem}")
def izleyici_yonet(eylem: str, ayar: IzleyiciAyari | None = None) -> dict:
    global izleyici
    if eylem == "klasor" and ayar and ayar.klasor:
        yeni = Path(ayar.klasor).expanduser()
        if not yeni.is_dir():
            raise HTTPException(400, f"Klasör bulunamadı: {yeni}")
        calisiyordu = izleyici.calisiyor
        izleyici.dur()
        izleyici = Izleyici(depo, yeni)
        depo.ayar_yaz({"indirilenler": str(yeni)})
        if calisiyordu:
            izleyici.basla()
    elif eylem == "basla":
        izleyici.basla()
    elif eylem == "dur":
        izleyici.dur()
    elif eylem == "tara":
        return {"alinan": izleyici.bir_tarama(), "calisiyor": izleyici.calisiyor}
    else:
        raise HTTPException(400, "eylem 'basla', 'dur', 'tara' ya da 'klasor' olmalı.")
    return {"calisiyor": izleyici.calisiyor, "klasor": str(izleyici.klasor)}


@uygulama.post("/api/senk")
def senk_tetikle() -> dict:
    from .toplayici import senkronize
    return {"sonuclar": senkronize(depo)}


@uygulama.post("/api/zamanlayici/{eylem}")
def zamanlayici_yonet(eylem: str) -> dict:
    if eylem == "basla":
        zamanlayici.basla()
    elif eylem == "dur":
        zamanlayici.dur()
    else:
        raise HTTPException(400, "eylem 'basla' ya da 'dur' olmalı.")
    return {"calisiyor": zamanlayici.calisiyor}


@uygulama.get("/api/yeni")
def yeni_kayitlar(esik: str = "") -> dict:
    """Son senkrondan sonra ilk kez görülen yayınlar — arayüzdeki bildirimler için."""
    if not esik:
        esik = depo.son_senk("WoS") or depo.son_senk("Scopus") or ""
    kayitlar = depo.yeni_kayitlar(esik) if esik else []
    return {"esik": esik, "adet": len(kayitlar),
            "kayitlar": [{"baslik": k.get("baslik"), "dergi": k.get("dergi"),
                          "yil": k.get("yil"), "kaynak": k.get("kaynak"),
                          "doi": k.get("doi")} for k in kayitlar[:50]]}


@uygulama.post("/api/kapat")
def kapat() -> dict:
    """Paketlenmiş uygulamada paneli kapatır (terminal penceresi olmadığı için)."""
    if not PAKET:
        raise HTTPException(400, "Bu düğme yalnızca masaüstü uygulamasında çalışır; "
                                 "servisi terminalden Ctrl+C ile durdurun.")
    zamanlayici.dur()
    threading.Timer(0.5, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
    return {"durum": "kapatiliyor"}


@uygulama.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


@uygulama.get("/sw.js")
def hizmet_isi() -> FileResponse:
    return FileResponse(WEB / "sw.js", media_type="application/javascript")


if WEB.is_dir():
    uygulama.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
else:  # pragma: no cover
    @uygulama.get("/")
    def kok() -> JSONResponse:
        return JSONResponse({"uyari": "web/ klasörü bulunamadı; yalnızca API çalışıyor."})


def main() -> None:  # pragma: no cover
    import uvicorn
    izleyici.basla()          # indirilen dosyalar kendiliğinden içeri alınsın
    uvicorn.run(uygulama, host="127.0.0.1", port=8787)


if __name__ == "__main__":  # pragma: no cover
    main()
