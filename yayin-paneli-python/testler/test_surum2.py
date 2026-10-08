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


def test_goc_yayinlari_tasir_wos_scopus_disi_metrikleri_atar(tmp_path):
    """Yayın kayıtları taşınır; SCImago/OpenAlex kökenli metrikler taşınmaz."""
    yol = tmp_path / "eski.db"
    d = Depo(yol)
    d.yaz("quartiller", {"2025": {"12345678": "Q1"}})
    d.yaz("metrikler", [{"ad": "A B", "kimlik": "A1", "h": 5, "atif": 10}])
    d.yaz("kurum_kayitlari", [kayit(id="a")])
    yeni = Depo(yol)                          # yeniden açmak göçü çalıştırır
    assert len(yeni.kayitlar()) == 1
    assert yeni.dergi_metrikleri() == [] and yeni.kisi_metrikleri() == []
    assert yeni.oku("quartiller") == []


def test_miras_temizle_yalnizca_wos_scopus_birakir(tmp_path):
    d = Depo(tmp_path / "temiz.db")
    d.dergi_metrik_ekle([
        {"kaynak": "WoS", "yil": 2025, "issn": "11112222", "q": "Q1"},
        {"kaynak": "Scopus", "yil": 2025, "issn": "11112222", "q": "Q2"},
        {"kaynak": "SCImago", "yil": 2025, "issn": "11112222", "q": "Q3"},
    ])
    d.kisi_metrik_ekle([{"kaynak": "OpenAlex", "profil_kimlik": "A1", "ad": "X", "h": 9}])
    assert d.miras_temizle() == 2
    assert {s["kaynak"] for s in d.dergi_metrikleri()} == {"WoS", "Scopus"}
    assert d.kisi_metrikleri() == []


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


# --- bildiri sayımı --------------------------------------------------------
def test_bildiriler_istege_bagli_sayilir():
    """`bildiri_dahil` açıkken bildiriler yayın sayısına girer ve ayrı Q satırı olur."""
    from yayin_paneli.analiz import Panel
    kayitlar = [kayit(id="a", doi="10.1/a"),
                kayit(id="b", doi="10.1/b", belge_turu="Proceedings Paper",
                      belge_turu_ham="Proceedings Paper")]

    haric = Panel(kayitlar=kayitlar, bildiri_dahil=False)
    zengin, bildiri = haric.zenginlestir()
    assert len(zengin) == 1 and bildiri == 1
    assert "Bildiri" not in haric.quartile()[0]["Çeyreklik"].tolist()

    dahil = Panel(kayitlar=kayitlar, bildiri_dahil=True)
    zengin, bildiri = dahil.zenginlestir()
    assert len(zengin) == 2 and bildiri == 1
    cerceve = dahil.quartile()[0]
    satir = cerceve[cerceve["Çeyreklik"] == "Bildiri"]
    assert int(satir["A: dahil"].iloc[0]) == 1


def test_servis_bildiri_parametresi(tmp_path):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    import yayin_paneli.servis as servis
    servis.depo = Depo(tmp_path / "bildiri.db")
    servis.depo.kayitlari_ekle([kayit(id="a", doi="10.1/a"),
                                kayit(id="b", doi="10.1/b", belge_turu="Proceedings Paper",
                                      belge_turu_ham="Proceedings Paper")], "WoS")
    istemci = fastapi_testclient.TestClient(servis.uygulama)
    assert istemci.get("/api/analiz?bildiri=true").json()["kutular"]["yayin"] == 2
    assert istemci.get("/api/analiz?bildiri=false").json()["kutular"]["yayin"] == 1


# --- indirilenler izleyicisi ----------------------------------------------
def test_izleyici_dosya_turlerini_tanir():
    from yayin_paneli.izleyici import tur_bul
    assert tur_bul(["Authors", "Article Title", "UT (Unique WOS ID)"]) == "wos"
    assert tur_bul(["Authors", "Publication Year", "Addresses"]) == "wos"
    assert tur_bul(["Authors", "Title", "Year", "Source title", "Document Type"]) == "scopus"
    assert tur_bul(["Journal name", "ISSN", "JIF Quartile"]) == "jcr"
    assert tur_bul(["Source title", "ISSN", "CiteScore"]) == "scopus_kaynak"
    # SCImago dosyasında hem H index hem quartile var; dergi listesi sayılmalı
    assert tur_bul(["Title", "Issn", "SJR Best Quartile", "H index"]) == "scopus_kaynak"
    assert tur_bul(["Author Name", "Scopus Author ID", "h-index"]) == "yazar"
    assert tur_bul(["Ad", "Soyad", "Unvan"]) == "personel"
    assert tur_bul(["Rastgele", "Sütunlar"]) == ""


def test_izleyici_yeni_dosyayi_alir(tmp_path, depo):
    import csv

    from yayin_paneli.izleyici import Izleyici

    klasor = tmp_path / "indirilenler"
    klasor.mkdir()
    izleyici = Izleyici(depo, klasor)
    assert izleyici.bir_tarama() == []            # baştaki klasör boş

    dosya = klasor / "scopus.csv"
    with dosya.open("w", newline="", encoding="utf-8") as f:
        yazici = csv.writer(f)
        yazici.writerow(["Authors", "Title", "Year", "Source title", "Cited by", "DOI",
                         "Document Type", "Open Access", "EID"])
        yazici.writerow(["Minaei S.", "Deneme", "2025", "J X", "3", "10.1/x",
                         "Article", "All Open Access", "2-s2.0-9"])
    (alinan,) = izleyici.bir_tarama()
    assert alinan["tur"] == "scopus" and alinan["adet"] == 1
    assert len(depo.kayitlar("Scopus")) == 1
    assert izleyici.bir_tarama() == []            # aynı dosya ikinci kez alınmaz


def test_izleyici_var_olan_dosyalari_yoksayar(tmp_path, depo):
    from yayin_paneli.izleyici import Izleyici
    klasor = tmp_path / "dolu"
    klasor.mkdir()
    (klasor / "eski.csv").write_text("Authors,Title,Year,Source title,Document Type,EID\n"
                                     "A,B,2025,C,Article,2-s2.0-1\n", encoding="utf-8")
    izleyici = Izleyici(depo, klasor)
    assert izleyici.bir_tarama() == []            # izleme öncesi dosyalar alınmaz
    assert depo.kayitlar() == []


def test_arama_baglantilari_kuruma_gore_uretilir():
    from yayin_paneli.izleyici import arama_baglantilari
    (satir,) = arama_baglantilari({"wos_kurum": "Dogus University",
                                   "scopus_kurum_kimligi": "60021658"}, [2026])
    assert "webofscience.com" in satir["wos"] and "2026" in satir["wos"]
    assert "scopus.com" in satir["scopus"] and "60021658" in satir["scopus"]


# --- veri setinden h-indeksi ----------------------------------------------
def test_veri_setinden_h_indeksi_kaynak_bazinda():
    """Kayıtlardaki atıf sayılarından kişi başına h; WoS ve Scopus ayrı hesaplanır."""
    from yayin_paneli.analiz import Panel
    kayitlar = []
    for i, (wos_atif, scopus_atif) in enumerate([(10, 12), (8, 9), (5, 5), (1, 1)]):
        kayitlar.append(kayit(id=f"w{i}", doi=f"10.1/{i}", atif=wos_atif,
                              kurum_yazarlari=["Minaei, Shahram"]))
        kayitlar.append(kayit(id=f"s{i}", doi=f"10.1/{i}", atif=scopus_atif, kaynak="Scopus",
                              kurum_yazarlari=["Minaei, Shahram"]))
    panel = Panel(kayitlar=kayitlar, personel=PERSONEL)
    (hucre,) = panel.kisi_h_hesapla().values()
    assert hucre["WoS"] == {"h": 3, "atif": 24, "yayin": 4}
    assert hucre["Scopus"] == {"h": 3, "atif": 27, "yayin": 4}

    cerceve, _ = panel.kisi_bazli("A", "tumu")
    satir = cerceve.iloc[0]
    assert satir["h (WoS, veri seti)"] == 3 and satir["Atıf (Scopus, veri seti)"] == 27


def test_metrik_kaynak_baglantilari():
    from yayin_paneli.izleyici import METRIK_KAYNAKLARI, yazar_profili_baglantilari
    turler = {k["tur"] for k in METRIK_KAYNAKLARI}
    assert {"jcr", "scopus_kaynak", "yazar"} <= turler
    assert all(k["adres"].startswith("https://") for k in METRIK_KAYNAKLARI)
    profil = yazar_profili_baglantilari("Şahram Minayi")
    assert "webofscience.com" in profil["wos"] and "scopus.com" in profil["scopus"]


# --- tarayıcı otomasyonu dış süreci ---------------------------------------
def test_playwright_yoksa_kurulum_komutu_doner(monkeypatch):
    from yayin_paneli.toplayici import dis_surec
    monkeypatch.setattr(dis_surec, "playwrightli_python", lambda **k: None)
    sonuc = dis_surec.calistir("cek", "https://ornek", "/tmp/p", "/tmp/i")
    assert sonuc["durum"] == "playwright_yok"
    assert any("pip install playwright" in k for k in sonuc["komutlar"])


def test_baglanti_yillari_her_zaman_2022den_baslar(tmp_path):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    import yayin_paneli.servis as servis
    servis.depo = Depo(tmp_path / "yil.db")
    servis.depo.ayar_yaz({"ilk_yil": 2026})      # ayar listeyi daraltmamalı
    istemci = fastapi_testclient.TestClient(servis.uygulama)
    yillar = [y["yil"] for y in istemci.get("/api/baglantilar").json()["yillar"]]
    assert yillar[0] == 2022 and len(yillar) >= 6


def test_dis_surec_yalitik_mod_kullanmaz():
    """"-I" kullanıcı site-packages'ını kapatır; pip install --user ile kurulan
    Playwright o modda görünmez, bu yüzden kullanılmamalı."""
    from yayin_paneli.toplayici import dis_surec
    kaynak = Path(dis_surec.__file__).read_text(encoding="utf-8")
    calistirma = kaynak[kaynak.index("def calistir("):]
    assert '"-I"' not in calistirma
