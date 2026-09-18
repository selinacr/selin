"""Panel mantığının temel kuralları — dosya gerektirmeyen testler."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yayin_paneli.analiz import Panel, adjunct_satiri_coz, bildiri_mi  # noqa: E402
from yayin_paneli.aylik import AdjunctPanel, donem_coz, kimlik_uret, quartile_coz  # noqa: E402
from yayin_paneli.metin import (ad_eslesiyor_mu, fonetik, sade, sayiya_cevir,  # noqa: E402
                         yazar_adi_coz)


def kayit(**alanlar):
    taban = {"id": "x", "baslik": "Başlık", "dergi": "Dergi", "issn": "12345678", "eissn": "",
             "doi": "", "yil": 2025, "belge_turu": "Article", "belge_turu_ham": "Article",
             "indeksler": ["SCI-EXPANDED"], "oa": "", "atif": 0, "kurum_yazarlari": [],
             "kurum_var": True, "adres_yok": False, "kaynak": "WoS", "tum_yazarlar": ""}
    return {**taban, **alanlar}


def test_sade_turkce_ve_yabanci_aksanlari_kokler():
    assert sade("ŞAHRAM MİNAYİ") == "sahram minayi"
    assert sade("Dragan Pamučar") == "dragan pamucar"
    assert sade("Vladimir Šimić") == "vladimir simic"


def test_fonetik_turkce_ingilizce_yazimi_birlestirir():
    assert fonetik("Shahram") == fonetik("Şahram")
    assert fonetik("Minaei") == fonetik("Minayi")


def test_ad_eslesmesi_dogru_kisiyi_bulur():
    assert ad_eslesiyor_mu(yazar_adi_coz("Minaei, Shahram"), yazar_adi_coz("MİNAYİ, ŞAHRAM"))
    assert ad_eslesiyor_mu(yazar_adi_coz("Kilic, H. H."), yazar_adi_coz("KILIÇ, HASAN HÜSEYİN"))
    assert ad_eslesiyor_mu(yazar_adi_coz("Alan, Alev Kocak"), yazar_adi_coz("KOÇAK ALAN, ALEV"))


def test_ad_eslesmesi_farkli_kisileri_ayirir():
    assert not ad_eslesiyor_mu(yazar_adi_coz("Aydin, Ali Murat"), yazar_adi_coz("AYDIN, MUHAMMED ALİ"))
    assert not ad_eslesiyor_mu(yazar_adi_coz("Abanoz, Yasin"), yazar_adi_coz("ABANOZ, YEŞİM"))


def test_turkce_binlik_ayraci():
    assert sayiya_cevir("2.500") == 2500
    assert sayiya_cevir("1.724,50") == 1724.5
    assert sayiya_cevir("431 EUR") == 431


def test_bildiri_analiz_disi():
    assert bildiri_mi(kayit(belge_turu_ham="Article; Proceedings Paper"))
    assert bildiri_mi(kayit(belge_turu="Conference paper"))
    assert not bildiri_mi(kayit())


def test_ayni_yayin_doi_ile_tek_sayilir():
    panel = Panel(kayitlar=[
        kayit(id="w1", doi="10.1/abc", kaynak="WoS"),
        kayit(id="s1", doi="10.1/ABC", kaynak="Scopus", indeksler=["Scopus"], atif=5),
    ])
    zengin, _ = panel.zenginlestir()
    assert len(zengin) == 1
    assert sorted(zengin[0]["kaynaklar"]) == ["Scopus", "WoS"]
    assert zengin[0]["atif"] == 5


def test_kaynak_secimi_kesisim_ve_tekil():
    kayitlar = [
        kayit(id="w1", doi="10.1/a", kaynak="WoS"),
        kayit(id="s1", doi="10.1/a", kaynak="Scopus"),
        kayit(id="s2", doi="10.1/b", kaynak="Scopus"),
    ]
    panel = Panel(kayitlar=kayitlar)
    assert len(panel.zenginlestir()[0]) == 2
    panel.kaynak_secimi = "ortak"
    assert len(panel.zenginlestir()[0]) == 1
    panel.kaynak_secimi = "WoS"
    assert len(panel.zenginlestir()[0]) == 1


def test_adjunct_sozlesme_kaynagi():
    kayitlar = [
        kayit(id="w1", doi="10.1/a", kaynak="WoS", kurum_yazarlari=["Sayyed, M. I."]),
        kayit(id="s2", doi="10.1/b", kaynak="Scopus", kurum_yazarlari=["Sayyed, M. I."]),
    ]
    panel = Panel(kayitlar=kayitlar, adjunct=["M. I. Sayyed | WoS"])
    zengin, _ = panel.zenginlestir()
    adjunctlu = [k for k in zengin if k["adjunct_var"]]
    assert len(adjunctlu) == 1 and adjunctlu[0]["doi"] == "10.1/a"


def test_adjunct_takma_adi():
    cozum = adjunct_satiri_coz("M. I. Sayyed = Abualsayed, Mohamad Ibrahim | Scopus")
    assert cozum.etiket == "M. I. Sayyed"
    assert cozum.kaynak == "Scopus"
    assert cozum.takmalar == ["Abualsayed, Mohamad Ibrahim"]


def test_ad_eslestirmesi_farkli_yazimi_birlestirir():
    panel = Panel(
        kayitlar=[kayit(id="w1", kurum_yazarlari=["Abualsayed, Mohammad I."])],
        adjunct=["M. I. Sayyed"], ad_esleme={"Abualsayed, Mohamad Ibrahim": "M. I. Sayyed"},
    )
    zengin, _ = panel.zenginlestir()
    assert zengin[0]["adjunct_var"]


def test_ceyreklik_yil_yedegi():
    panel = Panel(kayitlar=[kayit(yil=2026, issn="11112222")],
                  quartiller={2024: {"11112222": "Q2"}, 2025: {"11112222": "Q1"}})
    zengin, _ = panel.zenginlestir()
    assert zengin[0]["q"] == "Q1"          # 2026 için en yakın önceki liste 2025
    assert panel.quartile_yili(2026) == 2025


def test_issn_yoksa_dergi_adindan_ceyreklik():
    panel = Panel(kayitlar=[
        kayit(id="a", doi="10.1/a", issn="11112222", dergi="Nature"),
        kayit(id="b", doi="10.1/b", issn="", dergi="Nature", kaynak="Scopus"),
    ], quartiller={2025: {"11112222": "Q1"}})
    zengin, _ = panel.zenginlestir()
    assert {k["q"] for k in zengin} == {"Q1"}


def test_senaryo_b_adjunct_yayinlarini_cikarir():
    panel = Panel(kayitlar=[
        kayit(id="a", doi="10.1/a", kurum_yazarlari=["Pamucar, Dragan"]),
        kayit(id="b", doi="10.1/b", kurum_yazarlari=["Azizi, K."]),
    ], adjunct=["Dragan Pamucar"])
    assert len(panel.suzulmus("A")) == 2
    assert len(panel.suzulmus("B")) == 1


def test_metrikler_ayni_kisiyi_birlestirir():
    panel = Panel(kayitlar=[kayit(kurum_yazarlari=["Pamucar, Dragan"])], adjunct=["Dragan Pamucar"],
                  metrikler=[{"ad": "Dragan Pamučar", "kimlik": "A1", "atif": 30000, "yayin": 700, "h": 84},
                             {"ad": "Dragan Pamucar", "kimlik": "A2", "atif": 700, "yayin": 70, "h": 16}])
    metrik = panel.metrik_dizini()
    (tek,) = metrik.values()
    assert tek["atif"] == 30700 and tek["h"] == 84 and tek["profil"] == 2


def test_aylik_donem_ve_quartile_cozumu():
    assert donem_coz("AĞUSTOS 2026 Yayınları") == (2026, 8)
    assert donem_coz("Haziran-Temmuz 2025") == (2025, 6)
    assert quartile_coz("q3") == "Q3" and quartile_coz("3") == "Q3" and quartile_coz("-") == ""


def test_kimlik_ayni_girdi_icin_sabit():
    a = kimlik_uret("2026-08", "Dragan Pamucar", "10.1/x", "Başlık")
    b = kimlik_uret("2026-08", "Dragan Pamucar", "10.1/x", "Başlık")
    assert a == b and a.startswith("2026-08-")


def test_adjunct_panel_para_birimlerini_ayri_toplar():
    panel = AdjunctPanel(kayitlar=[
        {"id": "1", "donem": "2026-08", "kisi": "A", "baslik": "x", "dergi": "d", "doi": "",
         "quartile": "Q1", "tarih": "", "kontrol": "EUR parite", "tutar": 431, "odeme_metni": "431"},
        {"id": "2", "donem": "2026-08", "kisi": "B", "baslik": "y", "dergi": "d", "doi": "",
         "quartile": "Q2", "tarih": "", "kontrol": "", "tutar": 500, "odeme_metni": "500 USD"},
    ])
    kutular = panel.kutular()
    assert kutular["EUR ödeme"] == "431" and kutular["USD ödeme"] == "500"
    ozet = panel.kisi_ozeti()
    assert set(ozet.columns) >= {"Kişi", "Yayın", "EUR ödeme", "USD ödeme"}
