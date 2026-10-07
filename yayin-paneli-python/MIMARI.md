# Yayın Analiz Paneli — Mimari ve Revizyon Planı

Sürüm 2 hedefi: tek veri kaynağı ikilisi (WoS + Scopus), saat başı otomatik toplama,
kaynak bazlı çeyreklik ve h-indeksi, insan onaylı isim eşleştirme, modern PWA arayüzü.

## 1. Katmanlar

```
yayin_paneli/
  metin.py        isim normalleştirme, fonetik anahtar, eşleşme testleri
  ayristirma.py   WoS / Scopus / personel dosya çözümleyicileri
  analiz.py       tekilleştirme, kişi eşleştirme, tablolar (kaynak bazlı Q ve h)
  eslesme.py      takma ad veritabanı + onay kuyruğu (human-in-the-loop)
  aylik.py        adjunct ödeme dönemleri (değişmedi)
  depo.py         SQLite şeması, göç, okuma/yazma
  toplayici/
    tarayici.py   Playwright kalıcı profil oturumu
    wos.py        WoS kayıt / JCR çeyreklik / yazar h toplayıcı
    scopus.py     Scopus kayıt / CiteScore-SJR çeyreklik / yazar h toplayıcı
    api.py        resmi API istemcileri (WoS Starter, Scopus Search) — tercih edilen yol
    zamanlayici.py saat başı iş döngüsü, senkron günlüğü
  servis.py       FastAPI: JSON API + web/ altındaki PWA'yı sunar
web/              PWA arayüzü (HTML + JS + ECharts, koyu/açık tema, manifest, service worker)
app.py            Streamlit arayüzü (yerel hızlı kullanım için korunur)
```

## 2. Kaldırılanlar

| Kaldırılan | Yerine gelen |
| --- | --- |
| `openalex_ayristir` ve OpenAlex JSON yükleme | WoS ve Scopus yazar profillerinden çekilen `kisi_metrik` satırları |
| `sjr_ayristir` ve SCImago CSV yükleme | `dergi_metrik` tablosu: WoS için JCR, Scopus için CiteScore/SJR |
| `Panel.quartiller` (yıl → ISSN → Q) | `Panel.dergi_metrikleri` (kaynak + yıl + ISSN → Q) |
| `Panel.metrikler` (OpenAlex) | `Panel.kisi_metrikleri` (kaynak bazlı h ve atıf) |

Eski panel veritabanındaki `quartiller` (SCImago SJR) ve `metrikler` (OpenAlex)
anahtarları WoS/Scopus kaynaklı olmadığı için **taşınmaz, silinir**. `dergi_metrik` ve
`kisi_metrik` tablolarında yalnızca `kaynak` alanı `WoS` ya da `Scopus` olan satırlar
tutulur; `Depo.miras_temizle()` diğerlerini siler ve her açılışta çalışır.

## 3. Veri modeli (SQLite)

```sql
kayit(id TEXT PK, kaynak, yil, doi, baslik, dergi, issn, eissn, oa,
      belge_turu, indeksler_json, kurum_yazarlari_json, atif, ham_json,
      ilk_gorulme, son_gorulme)
dergi_metrik(kaynak, yil, issn, dergi, q, kategori, deger, guncelleme,
             PRIMARY KEY (kaynak, yil, issn, kategori))
kisi(id INTEGER PK, ad, soyad, unvan, fakulte, birim, tip, giris, cikis, akademik, adjunct)
kisi_profil(kisi_id, kaynak, profil_kimlik, PRIMARY KEY (kaynak, profil_kimlik))
kisi_metrik(kaynak, profil_kimlik, ad, h, atif, yayin, guncelleme,
            PRIMARY KEY (kaynak, profil_kimlik))
takma_ad(ham_sade PK, hedef, tur, kaynak, karar_veren, tarih)
onay_kuyrugu(id INTEGER PK, ham, kaynak, adaylar_json, benzerlik, durum, tarih)
senk_gunlugu(id INTEGER PK, kaynak, baslangic, bitis, durum, yeni_kayit, mesaj)
```

`veri(anahtar, icerik)` tablosu personel listesi, adjunct listesi, aylık ödeme kayıtları ve
ayarlar için korunur; tablo hâline geçen veriler oradan silinir.

## 4. Çeyreklik mantığı

- WoS kaydı → `dergi_metrik` içinde `kaynak = "WoS"` satırı (JCR, yayın yılına en yakın liste).
- Scopus kaydı → `kaynak = "Scopus"` satırı (CiteScore çeyrekliği, yoksa SJR).
- Her yayın hem `q_wos` hem `q_scopus` taşır. Panelin `q` alanı kaynak seçimine göre çözülür:
  WoS seçiliyse `q_wos`, Scopus seçiliyse `q_scopus`, birleşik görünümde `q_wos` varsa o,
  yoksa `q_scopus`. Bildiriler her durumda "Bildiri" sayılır ve analiz dışında tutulur.
- ISSN eşleşmesi tutmazsa dergi adı normalleştirilerek aranır; o da yoksa
  "Sınıflandırılamayan". Başka hiçbir liste yedek olarak kullanılmaz.

## 5. Otomatik toplama

İki yol var, `ayarlar.toplama_yolu` ile seçilir:

1. **`api`** (önerilen ve varsayılan): WoS Starter/Expanded API ve Scopus Search API,
   anahtarlar `WOS_API_KEY` / `SCOPUS_API_KEY` ortam değişkenlerinden okunur. Kurumsal
   abonelikte anahtar talebi ücretsizdir ve sağlayıcıların kullanım şartlarına uygundur.
2. **`tarayici`**: Playwright kalıcı profiliyle (`~/.yayin-paneli/tarayici-profili`) kurum
   ağından açılmış oturum kullanılarak arayüzden dışa aktarma. Clarivate ve Elsevier
   kullanım şartları otomatik erişimi kısıtladığı için bu yol yalnızca kullanıcının kendi
   makinesinde, kendi oturumuyla ve kendi sorumluluğunda çalışır; sunucuya kurulmaz.

Zamanlayıcı (APScheduler) saat başı çalışır: son senkron zamanından bu yana değişen
kayıtları çeker, `kayit` tablosunu tazeler, eksik dergi ve yazar metriklerini tamamlar,
sonucu `senk_gunlugu`na yazar. Arayüz bu günlükten "son senkron" ve "yeni düşen yayın"
bildirimlerini gösterir.

## 6. İsim eşleştirme ve onay kuyruğu

1. Ham yazar adı normalleştirilir (`sade`, NFD, fonetik anahtar).
2. `takma_ad` tablosunda kayıt varsa doğrudan hedefe bağlanır.
3. `adlar_uyuyor(..., kati=True)` ile kesin eşleşme bulunursa otomatik bağlanır.
4. Kesin değilse (yalnız soyad tutuyor, ilk harf çakışması, fonetik benzerlik) kayıt
   `onay_kuyrugu`na adaylarla birlikte düşer; arayüzde tek tıkla onay/ret yapılır.
5. Onaylanan eşleşme `takma_ad` tablosuna yazılır ve bir daha sorulmaz.
6. Adjunct profillerinde bulunan tüm isim varyasyonları aynı çatı etiket altında
   `takma_ad` olarak saklanır.

## 7. Arayüz

- `web/` altında derleme gerektirmeyen modern arayüz: CSS değişkenleriyle koyu/açık tema,
  kart tabanlı düzen, ECharts ile etkileşimli grafikler, hızlı arama ve filtre çubuğu.
- Kaynak filtresi her ekranda: Yalnız WoS / Yalnız Scopus / Birleşik.
- Modüller: Özet, Yıl bazlı, Çeyreklik (WoS ve Scopus yan yana), İndeks, Fakülte,
  Kişi analizi (h-indeksi ve Q dağılımı kartları), Onay kuyruğu, Senkron durumu.
- PWA: `manifest.webmanifest` + `sw.js`; masaüstü ve mobilde "Uygulamayı yükle" ile
  kurulur. Electron sarmalayıcı yerel servise bağlanacak şekilde korunur.

## 8. Aşamalar

1. OpenAlex/SJR bağımlılıklarının sökülmesi, kaynak bazlı Q ve h alanları.
2. Yeni SQLite şeması ve mevcut veriden göç.
3. `eslesme.py`: takma ad veritabanı ve onay kuyruğu.
4. `toplayici/`: API istemcileri, tarayıcı otomasyonu, saat başı zamanlayıcı.
5. `servis.py` + `web/`: JSON API ve PWA arayüzü.
6. Testler, README, masaüstü paketleme.
