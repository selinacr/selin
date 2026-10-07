"""Sürüm 2 bileşenleri: depo şeması, onay kuyruğu, API çözümleyicileri, servis."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yayin_paneli.ayristirma import (jcr_ayristir, q_coz, scopus_kaynak_ayristir,  # noqa: E402
                                     yazar_metrik_ayristir)
from yayin_paneli.depo import Depo  # noqa: E402
from yayin_paneli.eslesme import kuyruga_hazirla_yardimci  # noqa: E402  (aşağıda tanımlı)
from yayin_paneli.toplayici.api import (h_indeksi, scopus_dergi_coz,  # noqa: E402
                                        scopus_kaydi_coz, wos_kaydi_coz)
from yayin_paneli.toplayici.zamanlayici import sonraki_tam_saat  # noqa: E402


PERSONEL = [
    {"ad": "ŞAHRAM", "soyad": "MİNAYİ", "unvan": "Profesör", "fakulte": "Mühendislik",
     "birim": "Elektrik", "tip": "Akademik", "cikis": ""},
    {"ad": "YEŞİM", "soyad": "ABANOZ", "unvan": "Doçent", "fakulte": "Sanat",
     "birim": "", "tip": "Akademik", "cikis": ""},
]


@pytest.fixture()
def depo(tmp_path):
    d = Depo(tmp_path / "panel.db")
    d.yaz("personel", PERSONEL)
    d.yaz("adjunct", ["M. I. Sayyed = Abualsayed | WoS"])
    return d


def kayit(**alanlar):
    taban = {"id": "x", "baslik": "Başlık", "dergi": "Dergi", "issn": "12345678", "eissn": "",
             "doi": "10.1/x", "yil": 2025, "belge_turu": "Article", "belge_turu_ham": "Article",
             "indeksler": ["SCI-EXPANDED"], "oa": "", "atif": 3, "kurum_yazarlari": [],
             "kaynak": "WoS"}
    return {**taban, **alanlar}


# --- depo ----------------------------------------------------------------
def test_kayitlar_kaynak_bazinda_tazelenir(depo):
    depo.kayitlari_ekle([kayit(id="a", yil=2025)], "WoS")
    depo.kayitlari_ekle([kayit(id="b", yil=2025, kaynak="Scopus")], "Scopus")
    assert len(depo.kayitlar()) == 2
    # WoS 2025 tazelenir, Scopus kaydı korunur
    depo.kayitlari_ekle([kayit(id="c", yil=2025)], "WoS")
    kimlikler = {k["id"] for k in depo.kayitlar()}
    assert kimlikler == {"b", "c"}


def test_ilk_gorulme_korunur_yeni_kayit_isaretlenir(depo):
    depo.kayitlari_ekle([kayit(id="a", yil=2025)], "WoS")
    ilk = depo.kayitlar()[0]["ilk_gorulme"]
    depo.kayitlari_ekle([kayit(id="a", yil=2025, atif=9)], "WoS")
    tazelenen = depo.kayitlar()[0]
    assert tazelenen["ilk_gorulme"] == ilk and tazelenen["atif"] == 9
    assert depo.yeni_kayitlar("1970-01-01T00:00:00+00:00")


def test_goc_eski_quartilleri_miras_olarak_tasir(tmp_path):
    yol = tmp_path / "eski.db"
    d = Depo(yol)
    d.yaz("quartiller", {"2025": {"12345678": "Q1"}})
    d.yaz("metrikler", [{"ad": "A B", "kimlik": "A1", "h": 5, "atif": 10}])
    d.yaz("kurum_kayitlari", [kayit(id="a")])
    Depo(yol)  # yeniden açmak göçü çalıştırır
    yeni = Depo(yol)
    assert [s["kaynak"] for s in yeni.dergi_metrikleri()] == ["miras"]
    assert [s["kaynak"] for s in yeni.kisi_metrikleri()] == ["miras"]
    assert len(yeni.kayitlar()) == 1
    assert yeni.oku("quartiller") == []      # eski anahtar silinmiş olmalı


def test_senk_gunlugu_ve_ayarlar(depo):
    kimlik = depo.senk_basla("WoS")
    depo.senk_bitir(kimlik, "tamam", 4, "4 yeni kayıt")
    assert depo.son_senk("WoS")
    assert depo.senk_gunlugu(1)[0]["yeni_kayit"] == 4
    assert depo.ayar_yaz({"ilk_yil": 2020})["ilk_yil"] == 2020
    assert depo.ayarlar()["toplama_yolu"] == "api"


# --- onay kuyruğu ---------------------------------------------------------
def test_kesin_eslesme_otomatik_supheli_kuyruga(depo):
    sonuc = kuyruga_hazirla_yardimci(depo, ["Minaei, Shahram", "Abanoz, Yasin", "Qqqq, Zzz"])
    assert sonuc.kesin["Minaei, Shahram"] == "ŞAHRAM MİNAYİ"
    assert [k["ham"] for k in sonuc.kuyruk] == ["Abanoz, Yasin"]
    assert sonuc.eslesmeyen == ["Qqqq, Zzz"]


def test_adjunct_takma_adi_kesin_sayilir(depo):
    sonuc = kuyruga_hazirla_yardimci(depo, ["Sayyed, M. I."])
    assert sonuc.kesin["Sayyed, M. I."] == "M. I. Sayyed"


def test_onay_karari_takma_ada_yazilir_ve_tekrar_sorulmaz(depo):
    depo.kuyruga_ekle([{"ham": "Abanoz, Yasin", "kaynak": "WoS",
                        "adaylar": [{"hedef": "YEŞİM ABANOZ", "tur": "personel"}],
                        "benzerlik": 0.7}])
    assert len(depo.kuyruk()) == 1
    depo.kuyruk_karari("Abanoz, Yasin", "onayli", "YEŞİM ABANOZ")
    assert depo.kuyruk() == []
    assert depo.takma_adlar()["abanoz yasin"] == "YEŞİM ABANOZ"


def test_reddedilen_isim_takma_ada_yazilmaz(depo):
    depo.kuyruga_ekle([{"ham": "Qqqq, Zzz", "adaylar": [], "benzerlik": 0.5}])
    depo.kuyruk_karari("Qqqq, Zzz", "reddedildi")
    assert depo.kuyruk() == [] and depo.takma_adlar() == {}


# --- dosya çözümleyicileri ------------------------------------------------
def test_jcr_dosyasi_wos_satirlari_uretir():
    satirlar = jcr_ayristir([
        ["Journal name", "ISSN", "eISSN", "Category", "JIF Quartile", "JIF", "JCR Year"],
        ["NATURE", "0028-0836", "1476-4687", "Multidisciplinary", "Q1", "50.5", "2025"],
    ])
    assert {s["kaynak"] for s in satirlar} == {"WoS"}
    assert {s["issn"] for s in satirlar} == {"00280836", "14764687"}
    assert satirlar[0]["q"] == "Q1" and satirlar[0]["yil"] == 2025


def test_scopus_kaynak_dosyasi_yuzdelikten_q_uretir():
    satirlar = scopus_kaynak_ayristir([
        ["Source title", "ISSN", "Subject area", "Highest percentile", "CiteScore"],
        ["Journal of Nursing", "11112222", "Nursing", "88%", "7.4"],
    ], 2025)
    assert satirlar[0]["kaynak"] == "Scopus" and satirlar[0]["q"] == "Q1"


def test_yazar_metrik_dosyasi():
    satirlar = yazar_metrik_ayristir([
        ["Author Name", "Scopus Author ID", "h-index", "Citations", "Documents"],
        ["Pamucar, D.", "7005", "84", "31122", "700"],
    ], "Scopus")
    assert satirlar[0]["h"] == 84 and satirlar[0]["profil_kimlik"] == "7005"


def test_q_coz():
    assert q_coz("Q2") == "Q2" and q_coz("3") == "Q3" and q_coz("—") is None


# --- API çözümleyicileri --------------------------------------------------
def test_h_indeksi():
    assert h_indeksi([10, 8, 5, 4, 3, 1]) == 4
    assert h_indeksi([]) == 0


def test_wos_kaydi_coz():
    kayit_ = wos_kaydi_coz({
        "uid": "WOS:1", "title": "Deneme", "types": ["Article"],
        "sourceTypes": ["Science Citation Index Expanded"],
        "source": {"publishYear": 2025, "sourceTitle": "J X"},
        "identifiers": {"doi": "10.1/x", "issn": "1234-567x"},
        "names": {"authors": [{"displayName": "Minaei, Shahram", "researcherId": "R1"}]},
        "citations": [{"db": "WOS", "count": 7}],
    })
    assert kayit_["kaynak"] == "WoS" and kayit_["yil"] == 2025
    assert kayit_["issn"] == "1234567X" and kayit_["atif"] == 7
    assert kayit_["indeksler"] == ["SCI-EXPANDED"]
    assert kayit_["yazar_kimlikleri"] == ["R1"]


def test_scopus_kaydi_coz():
    kayit_ = scopus_kaydi_coz({
        "eid": "2-s2.0-1", "dc:title": "Deneme", "prism:coverDate": "2025-03-01",
        "prism:publicationName": "J X", "prism:issn": "1234567X", "citedby-count": "4",
        "openaccessFlag": "true", "subtypeDescription": "Article",
        "author": [{"authname": "Karatana O.", "authid": "55"}],
    })
    assert kayit_["kaynak"] == "Scopus" and kayit_["oa"] and kayit_["atif"] == 4
    assert kayit_["yazar_kimlikleri"] == ["55"]


def test_scopus_dergi_coz_yuzdeligi_ceyreklige_cevirir():
    satirlar = scopus_dergi_coz({
        "dc:title": "J X",
        "citeScoreYearInfoList": {"citeScoreYearInfo": [{
            "@year": "2025",
            "citeScoreInformationList": [{"citeScoreInformation": [{
                "citeScoreSubjectRank": [{"subject": "Nursing", "percentile": "88"},
                                         {"subject": "Other", "percentile": "30"}]}]}]}]},
    }, "1234567X", 2025)
    assert [s["q"] for s in satirlar] == ["Q1", "Q3"]


def test_bos_kayit_atlanir():
    assert wos_kaydi_coz({"uid": "x"}) is None
    assert scopus_kaydi_coz({"eid": "x"}) is None


# --- zamanlayıcı ----------------------------------------------------------
def test_sonraki_tam_saat():
    from datetime import datetime, timezone
    assert sonraki_tam_saat(datetime(2026, 10, 7, 13, 42, tzinfo=timezone.utc)) == \
        datetime(2026, 10, 7, 14, 0, tzinfo=timezone.utc)


# --- servis ----------------------------------------------------------------
def test_servis_uclari(tmp_path, monkeypatch):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    import yayin_paneli.servis as servis
    servis.depo = Depo(tmp_path / "servis.db")
    servis.depo.yaz("personel", PERSONEL)
    servis.depo.kayitlari_ekle(
        [kayit(id="a", kurum_yazarlari=["Minaei, Shahram"])], "WoS")
    istemci = fastapi_testclient.TestClient(servis.uygulama)

    durum = istemci.get("/api/durum").json()
    assert durum["kayit"] == 1 and durum["personel"] == 2

    analiz = istemci.get("/api/analiz").json()
    assert analiz["kutular"]["yayin"] == 1
    assert "Çeyreklik" in analiz["quartile"]["sutunlar"]
    assert "h (WoS)" not in analiz["kisi"]["sutunlar"]   # metrik yoksa kolon da yok

    assert istemci.post("/api/onay/tazele").json()["bekleyen"] == 0
    assert istemci.post("/api/ayarlar", json={"ilk_yil": 2021}).json()["ilk_yil"] == 2021
    assert istemci.post("/api/onay", json={"ham": "x", "durum": "onayli"}).status_code == 400
