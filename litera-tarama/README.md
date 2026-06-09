# litera-tarama

Çok kaynaklı **akademik literatür tarama ve özet** sistemi. Bir anahtar kelime /
konu verirsin; sistem **her seferinde sıfırdan** birden çok bilimsel veritabanını
tarar, sonuçları tekilleştirir ve sana özet bir rapor + filtrelenebilir bir
matris çıkarır.

Her çalışma için: **başlık, yazarlar, yıl, tür** (makale / bildiri / tez /
önbaskı / kitap / derleme), **yayın yeri, atıf sayısı, DOI/bağlantı ve özet**
toplanır. Toplam çalışma sayısı, türlere ve yıllara göre dağılım, öne çıkan ve en
güncel çalışmalar, sık geçen kavramlar ve üretken yazarlar raporlanır.

## Kaynaklar (bu sürüm: ücretsiz / anahtarsız çekirdek)

| Kaynak | Kapsam | Anahtar |
|--------|--------|---------|
| **OpenAlex** | En geniş; IEEE/Scopus/WoS içeriğinin büyük kısmını indeksler | gerekmez |
| **Crossref** | DOI'li yayınların metadatası | gerekmez |
| **Semantic Scholar** | Hazır **TLDR** özetleri | gerekmez (hız sınırlı) |
| **arXiv** | Önbaskılar (preprint) | gerekmez |

> **Neden Google Scholar / IEEE / Scopus / WoS yok?** Google Scholar'ın resmî
> API'si yoktur (kazıma engellenir; güvenilir erişim için ücretli SerpAPI gerekir).
> IEEE Xplore / Scopus / WoS kendi API'leri için anahtar/kurumsal abonelik ister.
> Mimari eklenti tabanlı: bu kaynaklar `litera/sources/` altına aynı arayüzle
> eklenebilir (bkz. *Yeni kaynak ekleme*). Pratikte OpenAlex bu veritabanlarının
> içeriğinin çoğunu zaten kapsar.

## Kurulum

```bash
cd litera-tarama
python3 -m pip install -r requirements.txt
```

## Kullanım

### Web arayüzü (Streamlit)

```bash
streamlit run app.py
```

Tarayıcıda: anahtar kelimeyi yaz, kaynakları ve yıl aralığını seç, **Tara**'ya bas.
Sonuç: üst metrikler, tür/yıl grafikleri, çalışma matrisi tablosu ve
**Markdown / CSV / Excel** indirme butonları.

### Komut satırı (CLI)

```bash
python3 cli.py "fractional-order analog filter pulse shaping" \
    --from 2018 --to 2025 --out rapor.md --csv matris.csv
```

## Ağ erişimi notu (önemli)

Bu araç çalışırken `api.openalex.org`, `api.crossref.org`,
`api.semanticscholar.org` ve `export.arxiv.org` adreslerine **giden internet
erişimi** ister.

- **Kendi bilgisayarında / üniversite ağında:** doğrudan çalışır.
- **Claude Code web ortamında:** varsayılan ağ politikası dış API'leri
  engelleyebilir. Bu durumda ortamın ağ politikasını bu domainlere izin verecek
  şekilde ayarla — bkz. https://code.claude.com/docs/en/claude-code-on-the-web

## Çıktılar

- **Markdown rapor** — okunabilir özet (sayılar, dağılımlar, öne çıkanlar).
- **CSV / Excel matris** — `Başlık · Yazarlar · Yıl · Tür · Yayın Yeri · Atıf ·
  Kaynak DB · DOI · URL · Anahtar Kavramlar · Özet` sütunlu, tez taraması için
  filtrelenebilir tablo.

## Mimari

```
app.py            Streamlit arayüzü
cli.py            Komut satırı arayüzü
litera/
  search.py       Orkestrasyon: kaynakları eşzamanlı + sıfırdan sorgular
  sources/        Kaynak eklentileri (openalex, crossref, semantic_scholar, arxiv)
  aggregate.py    Tekilleştirme (DOI / normalize başlık) + alan birleştirme
  summarize.py    Anahtarsız özet (sayım + TLDR/abstract derlemesi)
  report.py       Markdown rapor üretimi
  export.py       CSV / Excel matris
  models.py       Paper modeli + yayın türü normalizasyonu
  http_util.py    Nazik HTTP + üstel geri çekilmeli yeniden deneme
tests/            Çevrimdışı testler (ağ gerektirmez)
```

### Yeni kaynak ekleme (örn. IEEE / Scopus / SerpAPI)

1. `litera/sources/` altında `SourceAdapter`'dan türeyen bir sınıf yaz; `search()`
   metodunda kaynağın API'sini çağırıp sonuçları `Paper`'a çevir.
2. Anahtar gerekiyorsa `requires_key = True` yap ve `available()` ile anahtarın
   tanımlı olup olmadığını kontrol et (örn. ortam değişkeni).
3. Sınıfı `litera/sources/__init__.py` içindeki `REGISTRY`'ye ekle.

Tekilleştirme, özetleme, raporlama ve arayüz otomatik olarak yeni kaynağı kullanır.

## Test

```bash
python3 -m pytest tests/ -q
```

Testler ağ gerektirmez; ayrıştırma, tür normalizasyonu, birleştirme, özet ve
rapor mantığını sabit örneklerle doğrular.
