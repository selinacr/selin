"""WoS ve Scopus resmi API istemcileri.

Kurumsal abonelikte her iki sağlayıcı da ücretsiz API anahtarı verir ve otomatik erişimin
kullanım şartlarına uygun yolu budur. Anahtarlar ortam değişkenlerinden okunur:
`WOS_API_KEY` ve `SCOPUS_API_KEY`.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from ..ayristirma import indeksleri_coz, issn_sade
from ..metin import temiz_ad

WOS_TABAN = "https://api.clarivate.com/apis/wos-starter/v1"
SCOPUS_TABAN = "https://api.elsevier.com/content"
BEKLEME = 1.0          # saniye; sağlayıcı hız sınırlarına saygı
DENEME = 3


class ApiHatasi(RuntimeError):
    pass


def _istek(url: str, basliklar: dict, deneme: int = DENEME) -> dict:
    son_hata: Exception | None = None
    for sira in range(deneme):
        try:
            istek = urllib.request.Request(url, headers={"Accept": "application/json", **basliklar})
            with urllib.request.urlopen(istek, timeout=60) as yanit:
                return json.loads(yanit.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as hata:
            govde = hata.read()[:400].decode("utf-8", errors="replace")
            if hata.code in (401, 403):
                raise ApiHatasi(f"Yetki hatası ({hata.code}). API anahtarını kontrol edin: {govde}")
            son_hata = ApiHatasi(f"HTTP {hata.code}: {govde}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as hata:
            son_hata = ApiHatasi(f"Bağlantı hatası: {hata}")
        time.sleep(BEKLEME * (2 ** sira))
    raise son_hata or ApiHatasi("İstek başarısız.")


class WosApi:
    kaynak = "WoS"

    def __init__(self, anahtar: str | None = None, kurum: str = "Dogus University"):
        self.anahtar = anahtar or os.environ.get("WOS_API_KEY", "")
        self.kurum = kurum
        if not self.anahtar:
            raise ApiHatasi("WOS_API_KEY tanımlı değil.")

    @property
    def _basliklar(self) -> dict:
        return {"X-ApiKey": self.anahtar}

    def kayitlar(self, yil: int, sayfa_boyu: int = 50, azami_sayfa: int = 60) -> list[dict]:
        cikti: list[dict] = []
        for sayfa in range(1, azami_sayfa + 1):
            sorgu = urllib.parse.urlencode({
                "q": f'OG=("{self.kurum}") AND PY={yil}',
                "limit": sayfa_boyu, "page": sayfa, "db": "WOS",
            })
            veri = _istek(f"{WOS_TABAN}/documents?{sorgu}", self._basliklar)
            vurus = veri.get("hits") or []
            cikti.extend(wos_kaydi_coz(h) for h in vurus)
            if len(vurus) < sayfa_boyu:
                break
            time.sleep(BEKLEME)
        return [k for k in cikti if k]

    def yazar_metrikleri(self, adlar: list[str]) -> list[dict]:
        """WoS Starter yazar uç noktası yoksa kayıt sayısı ve atıftan h hesaplanır."""
        cikti = []
        for ad in adlar:
            sorgu = urllib.parse.urlencode({"q": f'AU=("{ad}") AND OG=("{self.kurum}")',
                                            "limit": 100, "page": 1, "db": "WOS"})
            try:
                veri = _istek(f"{WOS_TABAN}/documents?{sorgu}", self._basliklar)
            except ApiHatasi:
                continue
            atiflar = sorted((_wos_atif(h) for h in veri.get("hits") or []), reverse=True)
            cikti.append({"kaynak": self.kaynak, "ad": temiz_ad(ad), "profil_kimlik": f"wos:{ad}",
                          "h": h_indeksi(atiflar), "atif": sum(atiflar), "yayin": len(atiflar)})
            time.sleep(BEKLEME)
        return cikti

    def dergi_metrikleri(self, issnler: list[str], yil: int) -> list[dict]:
        """JCR uç noktası aboneliğe bağlıdır; erişilemezse boş döner."""
        cikti = []
        for issn in issnler:
            sorgu = urllib.parse.urlencode({"issn": issn, "year": yil})
            try:
                veri = _istek(f"{WOS_TABAN}/journals?{sorgu}", self._basliklar)
            except ApiHatasi:
                continue
            for satir in veri.get("hits") or []:
                q = str(satir.get("jifQuartile") or satir.get("quartile") or "").upper()
                if q.startswith("Q"):
                    cikti.append({"kaynak": self.kaynak, "yil": yil, "issn": issn_sade(issn),
                                  "dergi": temiz_ad(satir.get("name") or ""),
                                  "kategori": str(satir.get("category") or "")[:120],
                                  "q": q[:2], "deger": satir.get("jif")})
            time.sleep(BEKLEME)
        return cikti


class ScopusApi:
    kaynak = "Scopus"

    def __init__(self, anahtar: str | None = None, kurum_kimligi: str = "",
                 kurum: str = "Dogus University"):
        self.anahtar = anahtar or os.environ.get("SCOPUS_API_KEY", "")
        self.kurum_kimligi = kurum_kimligi or os.environ.get("SCOPUS_AF_ID", "")
        self.kurum = kurum
        if not self.anahtar:
            raise ApiHatasi("SCOPUS_API_KEY tanımlı değil.")

    @property
    def _basliklar(self) -> dict:
        return {"X-ELS-APIKey": self.anahtar}

    def _sorgu(self, yil: int) -> str:
        kurum = (f"AF-ID({self.kurum_kimligi})" if self.kurum_kimligi
                 else f'AFFIL("{self.kurum}")')
        return f"{kurum} AND PUBYEAR = {yil}"

    def kayitlar(self, yil: int, sayfa_boyu: int = 25, azami_sayfa: int = 120) -> list[dict]:
        cikti: list[dict] = []
        for sayfa in range(azami_sayfa):
            sorgu = urllib.parse.urlencode({
                "query": self._sorgu(yil), "count": sayfa_boyu,
                "start": sayfa * sayfa_boyu, "view": "STANDARD",
            })
            veri = _istek(f"{SCOPUS_TABAN}/search/scopus?{sorgu}", self._basliklar)
            girdiler = (veri.get("search-results") or {}).get("entry") or []
            girdiler = [g for g in girdiler if not g.get("error")]
            cikti.extend(scopus_kaydi_coz(g) for g in girdiler)
            if len(girdiler) < sayfa_boyu:
                break
            time.sleep(BEKLEME)
        return [k for k in cikti if k]

    def yazar_metrikleri(self, yazar_kimlikleri: list[str]) -> list[dict]:
        cikti = []
        for kimlik in yazar_kimlikleri:
            sorgu = urllib.parse.urlencode({"author_id": kimlik,
                                            "field": "h-index,citation-count,document-count,"
                                                     "preferred-name"})
            try:
                veri = _istek(f"{SCOPUS_TABAN}/author?{sorgu}", self._basliklar)
            except ApiHatasi:
                continue
            for girdi in (veri.get("author-retrieval-response") or []):
                ad = girdi.get("author-profile", {}).get("preferred-name", {})
                cikti.append({
                    "kaynak": self.kaynak, "profil_kimlik": str(kimlik),
                    "ad": temiz_ad(f"{ad.get('surname', '')}, {ad.get('given-name', '')}"),
                    "h": int(girdi.get("h-index") or 0),
                    "atif": int((girdi.get("coredata") or {}).get("citation-count") or 0),
                    "yayin": int((girdi.get("coredata") or {}).get("document-count") or 0),
                })
            time.sleep(BEKLEME)
        return cikti

    def dergi_metrikleri(self, issnler: list[str], yil: int) -> list[dict]:
        cikti = []
        for issn in issnler:
            sorgu = urllib.parse.urlencode({"issn": issn, "view": "CITESCORE"})
            try:
                veri = _istek(f"{SCOPUS_TABAN}/serial/title?{sorgu}", self._basliklar)
            except ApiHatasi:
                continue
            for girdi in (veri.get("serial-metadata-response") or {}).get("entry", []):
                cikti.extend(scopus_dergi_coz(girdi, issn, yil))
            time.sleep(BEKLEME)
        return cikti


# --- çözümleyiciler (saf fonksiyonlar; testlerde örnek JSON ile doğrulanır) --------
def _wos_atif(vurus: dict) -> int:
    for satir in vurus.get("citations") or []:
        if str(satir.get("db", "")).upper() in ("WOS", "ALL"):
            return int(satir.get("count") or 0)
    return 0


def h_indeksi(atiflar: list[int]) -> int:
    """Azalan atıf listesinden h-indeksi."""
    sirali = sorted((int(a or 0) for a in atiflar), reverse=True)
    h = 0
    for i, atif in enumerate(sirali, start=1):
        if atif >= i:
            h = i
        else:
            break
    return h


def wos_kaydi_coz(vurus: dict) -> dict | None:
    kimlikler = vurus.get("identifiers") or {}
    kaynak_bilgi = vurus.get("source") or {}
    adlar = (vurus.get("names") or {}).get("authors") or []
    turler = vurus.get("types") or []
    indeks_metni = " ".join(str(t) for t in (vurus.get("sourceTypes") or []) + turler)
    baslik = temiz_ad(vurus.get("title") or "")
    if not baslik:
        return None
    return {
        "id": str(vurus.get("uid") or kimlikler.get("doi") or baslik[:80]),
        "kaynak": "WoS",
        "yil": int(kaynak_bilgi.get("publishYear") or 0) or None,
        "doi": str(kimlikler.get("doi") or "").strip(),
        "baslik": baslik,
        "dergi": temiz_ad(kaynak_bilgi.get("sourceTitle") or ""),
        "issn": issn_sade(kimlikler.get("issn")),
        "eissn": issn_sade(kimlikler.get("eissn")),
        "oa": "Açık erişim" if vurus.get("openAccess") or vurus.get("isOpenAccess") else "",
        "belge_turu": ", ".join(str(t) for t in turler),
        "belge_turu_ham": ", ".join(str(t) for t in turler),
        "atif": _wos_atif(vurus),
        "indeksler": indeksleri_coz(indeks_metni) or ["SCI-EXPANDED"],
        "kurum_yazarlari": [temiz_ad(y.get("displayName") or "") for y in adlar
                            if temiz_ad(y.get("displayName") or "")],
        "adres_yok": True,
        "yazar_kimlikleri": [str(y.get("researcherId")) for y in adlar if y.get("researcherId")],
    }


def scopus_kaydi_coz(girdi: dict) -> dict | None:
    baslik = temiz_ad(girdi.get("dc:title") or "")
    if not baslik:
        return None
    tarih = str(girdi.get("prism:coverDate") or "")
    yazarlar = [temiz_ad(y.get("authname") or "") for y in girdi.get("author") or []]
    if not yazarlar and girdi.get("dc:creator"):
        yazarlar = [temiz_ad(girdi["dc:creator"])]
    return {
        "id": str(girdi.get("eid") or girdi.get("prism:doi") or baslik[:80]),
        "kaynak": "Scopus",
        "yil": int(tarih[:4]) if tarih[:4].isdigit() else None,
        "doi": str(girdi.get("prism:doi") or "").strip(),
        "baslik": baslik,
        "dergi": temiz_ad(girdi.get("prism:publicationName") or ""),
        "issn": issn_sade(girdi.get("prism:issn")),
        "eissn": issn_sade(girdi.get("prism:eIssn")),
        "oa": "Açık erişim" if str(girdi.get("openaccessFlag")).lower() == "true" else "",
        "belge_turu": str(girdi.get("subtypeDescription") or ""),
        "belge_turu_ham": str(girdi.get("subtypeDescription") or ""),
        "atif": int(girdi.get("citedby-count") or 0),
        "indeksler": ["Scopus"],
        "kurum_yazarlari": [y for y in yazarlar if y],
        "adres_yok": True,
        "yazar_kimlikleri": [str(y.get("authid")) for y in girdi.get("author") or []
                             if y.get("authid")],
    }


def scopus_dergi_coz(girdi: dict, issn: str, yil: int) -> list[dict]:
    """Scopus serial/title yanıtından CiteScore yüzdelik dilimini çeyrekliğe çevirir."""
    cikti = []
    dergi = temiz_ad(girdi.get("dc:title") or "")
    yillar = ((girdi.get("citeScoreYearInfoList") or {}).get("citeScoreYearInfo") or [])
    for satir in yillar:
        if int(satir.get("@year") or 0) != yil:
            continue
        bilgi = satir.get("citeScoreInformationList") or []
        for blok in bilgi:
            for olcum in blok.get("citeScoreInformation") or []:
                for alan in olcum.get("citeScoreSubjectRank") or []:
                    yuzdelik = alan.get("percentile")
                    if yuzdelik is None:
                        continue
                    yuzdelik = float(yuzdelik)
                    q = ("Q1" if yuzdelik >= 75 else "Q2" if yuzdelik >= 50
                         else "Q3" if yuzdelik >= 25 else "Q4")
                    cikti.append({"kaynak": "Scopus", "yil": yil, "issn": issn_sade(issn),
                                  "dergi": dergi,
                                  "kategori": str(alan.get("subject") or "")[:120],
                                  "q": q, "deger": yuzdelik})
    return cikti
