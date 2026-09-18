"""Doğuş Üniversitesi yayın paneli — Streamlit sürümü.

Çalıştırmak için:  streamlit run app.py
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from yayin_paneli.analiz import Panel
from yayin_paneli.aylik import AdjunctPanel, ay_ayristir, donem_adi
from yayin_paneli.ayristirma import (openalex_ayristir, personel_ayristir, satirlari_oku,
                              scopus_ayristir, sjr_ayristir, wos_ayristir)
from yayin_paneli.depo import Depo

st.set_page_config(page_title="Yayın Paneli", page_icon="📑", layout="wide")


@st.cache_resource
def depo() -> Depo:
    return Depo()


def veriyi_oku() -> dict:
    return depo().hepsini_oku()


def yenile() -> None:
    st.cache_data.clear()
    st.rerun()


def kurum_paneli(veri: dict) -> Panel:
    return Panel(
        kayitlar=veri["kurum_kayitlari"], personel=veri["personel"], adjunct=veri["adjunct"],
        ad_esleme=veri["ad_esleme"],
        quartiller={int(y): h for y, h in veri["quartiller"].items()},
        metrikler=veri["metrikler"],
    )


# --------------------------------------------------------------------------
# Kurum analizi
# --------------------------------------------------------------------------
def kurum_ekrani(veri: dict) -> None:
    panel = kurum_paneli(veri)
    if not panel.kayitlar:
        st.info("Henüz yayın verisi yok. Soldaki **Veri yükle** bölümünden WoS ya da Scopus "
                "dosyası ekleyin.")
        return

    kaynaklar = sorted({(k.get("kaynak") or "WoS") for k in panel.kayitlar})
    ust = st.columns([2, 2, 3])
    with ust[0]:
        senaryo = st.radio("Senaryo", ["A: adjunct dahil", "B: hariç"], horizontal=True,
                           label_visibility="collapsed")
    with ust[1]:
        secim = "hepsi"
        if len(kaynaklar) > 1:
            secim = st.selectbox("Kaynak", ["hepsi", *kaynaklar, "ortak"],
                                 format_func=lambda s: {"hepsi": "WoS + Scopus",
                                                        "ortak": "Ortak yayınlar"}.get(s, f"Yalnız {s}"))
    panel.kaynak_secimi = secim
    senaryo_kodu = "A" if senaryo.startswith("A") else "B"

    zengin, bildiri = panel.zenginlestir()
    yillar = sorted({k["yil"] for k in zengin if k["yil"]})
    with ust[2]:
        yil = st.selectbox("Yıl", ["tumu", *[str(y) for y in yillar]],
                           format_func=lambda y: "Tüm yıllar" if y == "tumu" else y)

    secili = panel.suzulmus(senaryo_kodu, yil)
    siniflanan = [k for k in secili if k["q"] in ("Q1", "Q2", "Q3", "Q4")]
    kutular = st.columns(5)
    kutular[0].metric("Yayın", len(secili))
    kutular[1].metric("Akademik personel", panel.personel_sayisi(senaryo_kodu))
    kutular[2].metric("Yayın / kişi",
                      f"{len(secili) / max(panel.personel_sayisi(senaryo_kodu), 1):.2f}".replace(".", ","))
    kutular[3].metric("Açık erişim %",
                      f"{100 * sum(1 for k in secili if k['oa_var']) / max(len(secili), 1):.1f}".replace(".", ","))
    kutular[4].metric("Q1 payı %",
                      f"{100 * sum(1 for k in siniflanan if k['q'] == 'Q1') / max(len(siniflanan), 1):.1f}"
                      .replace(".", ","))
    st.caption(f"{yillar[0]}–{yillar[-1]} · {len(zengin)} tekil yayın · "
               f"{len(veri['personel'])} personel satırı · {len(veri['adjunct'])} adjunct adı · "
               f"{bildiri} bildiri analiz dışı · "
               f"çeyreklik listeleri: {', '.join(sorted(veri['quartiller'])) or 'yok'}")

    sekmeler = st.tabs(["Özet", "Yıl bazlı", "Çeyreklik", "İndeks", "Açık erişim",
                        "Fakülte", "Kişi bazlı", "Dergi"])
    with sekmeler[0]:
        st.dataframe(panel.ozet(yil), use_container_width=True, hide_index=True)
    with sekmeler[1]:
        st.dataframe(panel.yil_bazli(), use_container_width=True, hide_index=True)
    with sekmeler[2]:
        cerceve, notu = panel.quartile(yil)
        st.dataframe(cerceve, use_container_width=True, hide_index=True)
        st.caption(notu)
    with sekmeler[3]:
        st.dataframe(panel.indeks(yil), use_container_width=True, hide_index=True)
        st.caption("CPCI satırları konferans bildirisi indeksleridir; bildiriler analiz dışıdır.")
    with sekmeler[4]:
        st.dataframe(panel.acik_erisim(), use_container_width=True, hide_index=True)
        st.caption("Açık erişim yalnızca var/yok olarak sayılır (gold, green ayrımı yapılmaz).")
    with sekmeler[5]:
        cerceve, notu = panel.fakulte(senaryo_kodu, yil)
        st.dataframe(cerceve, use_container_width=True, hide_index=True)
        st.caption(notu)
    with sekmeler[6]:
        cerceve, notu = panel.kisi_bazli(senaryo_kodu, yil)
        arama = st.text_input("Kişi ara", "")
        if arama:
            cerceve = cerceve[cerceve["Kişi"].str.contains(arama, case=False, na=False)]
        st.dataframe(cerceve, use_container_width=True, hide_index=True, height=520)
        st.caption(notu)
        st.download_button("CSV indir", cerceve.to_csv(index=False).encode("utf-8-sig"),
                           "kisi_bazli.csv", "text/csv")
    with sekmeler[7]:
        st.dataframe(panel.dergi(senaryo_kodu, yil).head(100), use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------
# Adjunct yayın teşviki
# --------------------------------------------------------------------------
def adjunct_ekrani(veri: dict) -> None:
    kayitlar = veri["aylik_kayitlar"]
    if not kayitlar:
        st.info("Henüz ay yüklenmedi. Soldaki **Veri yükle** bölümünden aylık Excel dosyasını ekleyin.")
        return
    panel = AdjunctPanel(kayitlar=kayitlar, kurallar=veri["kurallar"])
    donemler = panel.donemler()
    secim = st.selectbox("Dönem", ["tumu", *donemler],
                         format_func=lambda d: "Tüm dönemler" if d == "tumu" else donem_adi(d))
    if secim != "tumu":
        panel = AdjunctPanel(kayitlar=[k for k in kayitlar if k["donem"] == secim],
                             kurallar=veri["kurallar"])

    kutular = panel.kutular()
    sutunlar = st.columns(max(len(kutular), 1))
    for sutun, (etiket, deger) in zip(sutunlar, kutular.items()):
        sutun.metric(etiket, deger)
    baslik = donem_adi(secim) if secim != "tumu" else f"{donem_adi(donemler[0])} – {donem_adi(donemler[-1])}"
    st.caption(f"{baslik} · {len(panel.kayitlar)} yayın")

    sekmeler = st.tabs(["Kişi × ay", "Kişi × quartile", "Kişi özeti", "Dergi", "Makaleler"])
    with sekmeler[0]:
        olcu = st.radio("Ölçü", ["Ödeme tutarı", "Yayın sayısı"], horizontal=True)
        st.dataframe(panel.kisi_ay("tutar" if olcu.startswith("Ödeme") else "kayit"),
                     use_container_width=True, hide_index=True)
    with sekmeler[1]:
        st.dataframe(panel.kisi_quartile(), use_container_width=True, hide_index=True)
    with sekmeler[2]:
        st.dataframe(panel.kisi_ozeti(), use_container_width=True, hide_index=True)
    with sekmeler[3]:
        st.dataframe(panel.dergi(), use_container_width=True, hide_index=True)
    with sekmeler[4]:
        cerceve = pd.DataFrame(panel.zengin())[
            ["donem", "kisi", "baslik", "dergi", "doi", "quartile", "tutar", "para_birimi", "kontrol"]]
        cerceve.columns = ["Dönem", "Kişi", "Makale", "Dergi", "DOI", "Q", "Tutar", "Birim", "Kontrol notu"]
        duzenlenmis = st.data_editor(cerceve, use_container_width=True, hide_index=True,
                                     height=520, num_rows="fixed")
        if st.button("Düzeltmeleri kaydet"):
            guncel = []
            for kayit, (_, satir) in zip(panel.kayitlar, duzenlenmis.iterrows()):
                guncel.append({**kayit, "kisi": satir["Kişi"], "baslik": satir["Makale"],
                               "dergi": satir["Dergi"], "doi": satir["DOI"],
                               "quartile": satir["Q"], "tutar": satir["Tutar"],
                               "para_birimi_elle": satir["Birim"], "kontrol": satir["Kontrol notu"]})
            kalanlar = [k for k in veri["aylik_kayitlar"]
                        if secim == "tumu" or k["donem"] != secim]
            depo().yaz("aylik_kayitlar", guncel if secim == "tumu" else [*kalanlar, *guncel])
            st.success("Düzeltmeler kaydedildi.")
            yenile()


# --------------------------------------------------------------------------
# Veri yükleme (kenar çubuğu)
# --------------------------------------------------------------------------
def yukleme_ekrani(veri: dict) -> None:
    st.sidebar.header("Veri yükle")

    wos = st.sidebar.file_uploader("WoS Full Record (.xls/.xlsx)", type=["xls", "xlsx"],
                                   accept_multiple_files=True, key="wos")
    if wos and st.sidebar.button("WoS dosyalarını kaydet"):
        toplam = 0
        for dosya in wos:
            sonuc = wos_ayristir(satirlari_oku(dosya, dosya.name), dosya.name)
            toplam = depo().kayitlari_ekle(sonuc["kayitlar"], "WoS")
            for uyari in sonuc["uyarilar"]:
                st.sidebar.warning(uyari)
        st.sidebar.success(f"{toplam} kayıt saklandı.")
        yenile()

    scopus = st.sidebar.file_uploader("Scopus dışa aktarımı (.csv/.xlsx)", type=["csv", "xls", "xlsx"],
                                      accept_multiple_files=True, key="scopus")
    if scopus and st.sidebar.button("Scopus dosyalarını kaydet"):
        toplam = 0
        for dosya in scopus:
            sonuc = scopus_ayristir(satirlari_oku(dosya, dosya.name), dosya.name)
            toplam = depo().kayitlari_ekle(sonuc["kayitlar"], "Scopus")
            for uyari in sonuc["uyarilar"]:
                st.sidebar.warning(uyari)
        st.sidebar.success(f"{toplam} kayıt saklandı.")
        yenile()

    personel = st.sidebar.file_uploader("Personel listesi (.xlsx)", type=["xls", "xlsx"], key="personel")
    if personel and st.sidebar.button("Personel listesini kaydet"):
        kisiler = personel_ayristir(satirlari_oku(personel, personel.name))
        depo().yaz("personel", kisiler)
        st.sidebar.success(f"{len(kisiler)} personel satırı kaydedildi.")
        yenile()

    sjr = st.sidebar.file_uploader("SCImago SJR (.csv)", type=["csv"], accept_multiple_files=True, key="sjr")
    if sjr and st.sidebar.button("Çeyreklik listelerini kaydet"):
        for dosya in sjr:
            yil = next((int(p) for p in dosya.name.replace(".", " ").split() if p.isdigit()
                        and len(p) == 4), None)
            if not yil:
                st.sidebar.warning(f"{dosya.name}: dosya adında yıl bulunamadı, atlandı.")
                continue
            depo().quartil_ekle(yil, sjr_ayristir(satirlari_oku(dosya, dosya.name)))
            st.sidebar.success(f"{yil} çeyreklik listesi kaydedildi.")
        yenile()

    metrik = st.sidebar.file_uploader("OpenAlex yazar metrikleri (.json)", type=["json"],
                                      accept_multiple_files=True, key="metrik")
    if metrik and st.sidebar.button("Metrikleri kaydet"):
        for dosya in metrik:
            depo().metrik_ekle(openalex_ayristir(dosya.read().decode("utf-8")))
        st.sidebar.success("Yazar metrikleri kaydedildi.")
        yenile()

    aylik = st.sidebar.file_uploader("Adjunct ay dosyası (.xlsx)", type=["xls", "xlsx"],
                                     accept_multiple_files=True, key="aylik")
    if aylik and st.sidebar.button("Ayları kaydet"):
        for dosya in aylik:
            sonuc = ay_ayristir(satirlari_oku(dosya, dosya.name), dosya.name)
            depo().ay_ekle(sonuc["donem"], sonuc["kayitlar"])
            st.sidebar.success(f"{donem_adi(sonuc['donem'])}: {len(sonuc['kayitlar'])} kayıt.")
            for uyari in sonuc["uyarilar"]:
                st.sidebar.warning(uyari)
        yenile()

    st.sidebar.header("Listeler")
    adjunct = st.sidebar.text_area(
        "Adjunct adları — her satıra bir ad. Sözleşmesi tek veritabanına bağlıysa "
        '"Dragan Pamucar | Scopus" yazın.', value="\n".join(veri["adjunct"]), height=140)
    if st.sidebar.button("Adjunct listesini kaydet"):
        depo().yaz("adjunct", [s.strip() for s in adjunct.splitlines() if s.strip()])
        yenile()

    esleme = st.sidebar.text_area(
        "Ad eşleştirme — 'yayındaki yazım = kurumdaki ad'",
        value="\n".join(f"{k} = {v}" for k, v in veri["ad_esleme"].items()), height=120)
    if st.sidebar.button("Ad eşleştirmelerini kaydet"):
        harita = {}
        for satir in esleme.splitlines():
            yazilan, _, gercek = satir.partition("=")
            if yazilan.strip() and gercek.strip():
                harita[yazilan.strip()] = gercek.strip()
        depo().yaz("ad_esleme", harita)
        yenile()

    if veri["aylik_kayitlar"]:
        st.sidebar.header("Yüklü aylar")
        for donem in sorted({k["donem"] for k in veri["aylik_kayitlar"]}, reverse=True):
            adet = sum(1 for k in veri["aylik_kayitlar"] if k["donem"] == donem)
            sutun = st.sidebar.columns([3, 1])
            sutun[0].write(f"{donem_adi(donem)} · {adet}")
            if sutun[1].button("sil", key=f"sil-{donem}"):
                depo().ay_sil(donem)
                yenile()


def main() -> None:
    veri = veriyi_oku()
    st.title("Doğuş Üniversitesi Yayın Paneli")
    mod = st.radio("Panel", ["Kurum analizi", "Adjunct yayın teşviki"], horizontal=True,
                   label_visibility="collapsed")
    yukleme_ekrani(veri)
    if mod == "Kurum analizi":
        kurum_ekrani(veri)
    else:
        adjunct_ekrani(veri)


if __name__ == "__main__":
    main()
