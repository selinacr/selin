# Yayın Paneli — Python sürümü

Web panelinin (Claude artifact) Python karşılığı: aynı ayrıştırma ve eşleştirme
kuralları, Streamlit arayüzü ve tek dosyalık SQLite veritabanı.

## Kurulum

```bash
cd yayin-paneli-python
pip install -r requirements.txt
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır. Veriler `veri/panel.db` dosyasında
tutulur; bu dosyayı yedeklemek tüm paneli yedeklemek demektir.

## Neleri okur

| Dosya | Nereden |
| --- | --- |
| WoS "Full Record" (.xls/.xlsx) | Web of Science → Export → Excel |
| Scopus dışa aktarımı (.csv) | Scopus → Export → CSV ("Bibliographical information" seçilirse adres ve ISSN de gelir) |
| Personel listesi (.xlsx) | Kurum akademik personel listesi |
| SCImago SJR (.csv) | scimagojr.com yıllık dergi listesi (dosya adında yıl olmalı) |
| OpenAlex yazar metrikleri (.json) | `api.openalex.org/authors?filter=last_known_institutions.id:I129994210&per-page=200` |
| Adjunct ay dosyası (.xlsx) | Aylık yayın/ödeme tablosu |

## Komut satırından toplu yükleme

```bash
python araclar/veri_yukle.py \
  --wos savedrecs*.xls --scopus scopus_export.csv \
  --personel akademik_personel.xlsx \
  --sjr scimagojr_2025.csv --metrik authors*.json \
  --aylik "Agustos 2026.xlsx" --adjunct adjunct.txt
```

## Analiz kuralları (web paneliyle aynı)

- Bildiriler (proceedings paper / conference paper) analiz dışıdır.
- Aynı yayın hem WoS hem Scopus'ta ise DOI (yoksa başlık) üzerinden tek sayılır;
  WoS kaydı taban alınır, eksik alanlar Scopus'tan tamamlanır.
- Çeyreklik ISSN üzerinden SJR listesiyle eşleşir; o yılın listesi yoksa en yakın
  önceki yıl kullanılır, ISSN yoksa dergi adından tamamlanır.
- Senaryo A adjunct yayınlarını içerir, B çıkarır. Adjunct satırına
  `Dragan Pamucar | Scopus` yazılırsa o kişinin yayınları yalnızca o veritabanından sayılır.
- Ad eşleştirme listesi (`yayındaki yazım = kurumdaki ad`) farklı çeviri yazımları birleştirir;
  Türkçe/İngilizce yazım farkları (Shahram ↔ Şahram, Minaei ↔ Minayi) otomatik çözülür.
- Atıf ve h indeksi OpenAlex yazar profillerinden gelir; aynı kişinin birden çok profili
  varsa atıflar toplanır, h'nin en büyüğü alınır.

## Testler

```bash
python -m pytest testler -q
```

## Web sürümüyle ilişki

İki sürüm bağımsız çalışır: web paneli verisini Claude tarafında, Python sürümü
`veri/panel.db` içinde tutar. Aynı dosyaları ikisine de yükleyebilirsiniz; sayılar
aynı çıkar (karşılaştırma: 2022–2026 için 1.312 tekil yayın, Q1 575, 237 kişi
OpenAlex metriğiyle eşleşir).
