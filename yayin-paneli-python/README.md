# Doğuş Üniversitesi Yayın Analiz Paneli (sürüm 2)

Kurumun WoS ve Scopus yayınlarını tek yerde toplayan, çeyreklik ve h-indeksi
analizlerini iki kaynak için ayrı ayrı üreten panel. Mimari ayrıntılar: `MIMARI.md`.

## Kurulum

Anaconda Prompt (ya da herhangi bir terminal) içinde, bu klasörde:

```
python -m pip install -r requirements.txt
```

## Çalıştırma

**Panel (önerilen — PWA arayüzü):**

```
python -m yayin_paneli.servis
```

Ardından tarayıcıda <http://127.0.0.1:8787/>. Windows'ta `baslat_panel.bat` dosyasına
çift tıklamak da aynı işi yapar.

Adres çubuğundaki **Uygulamayı yükle** düğmesiyle panel masaüstüne ya da telefonun
ana ekranına kurulabilir; çevrimdışı açıldığında son görülen veriler gösterilir.

**Streamlit sürümü (aynı veritabanı, hızlı veri yükleme ekranları):**

```
python -m streamlit run app.py
```

**Komut satırından toplu yükleme:**

```
python araclar/veri_yukle.py --wos savedrecs*.xls --scopus scopus.csv \
    --personel akademik.xlsx --jcr "JCR 2025.csv" --scopus-kaynak citescore_2025.csv \
    --wos-yazar researchers.csv --scopus-yazar authors.csv
python araclar/veri_yukle.py --senk        # WoS + Scopus senkronunu hemen çalıştır
python araclar/veri_yukle.py --kuyruk      # onay kuyruğunu yeniden hesapla
```

## Veri kaynakları

Yalnızca **Web of Science** ve **Scopus** kullanılır. Her veri iki yoldan gelebilir:

| Veri | Otomatik | Elle |
| --- | --- | --- |
| Yayın kayıtları | WoS Starter API / Scopus Search API | WoS Full Record `.xls`, Scopus `.csv` |
| Çeyreklik (Q1–Q4) | JCR ve Scopus CiteScore uç noktaları | JCR dışa aktarımı, Scopus Sources `.csv` |
| h-indeksi, atıf | WoS ve Scopus yazar profilleri | Yazar listesi `.csv` (kaynak seçilerek) |

WoS çeyrekliği **JCR**, Scopus çeyrekliği **CiteScore yüzdelik dilimi** (yoksa SJR)
üzerinden hesaplanır. Her yayın hem `q_wos` hem `q_scopus` taşır; panelin gösterdiği
değer üstteki kaynak filtresine göre çözülür.

Sürüm 1'den devralınan eski çeyreklik listesi `devralınan` etiketiyle saklanır ve
yalnızca iki kaynaktan da değer gelmeyen yayınlarda kullanılır; gerçek değer geldiğinde
otomatik olarak devreye girer.

## Otomatik toplama

`Senkron` sekmesinden iki yoldan biri seçilir:

**`api` (varsayılan, önerilen).** Resmi API anahtarları kullanılır:

```
setx WOS_API_KEY "..."
setx SCOPUS_API_KEY "..."
setx SCOPUS_AF_ID "60021658"     # kurumun Scopus AF-ID'si (boşsa ad ile aranır)
```

Kurumsal abonelikte her iki anahtar da ücretsiz alınır ve sağlayıcıların kullanım
şartlarına uygun yoldur.

**`tarayici`.** Kendi makinenizdeki açık WoS/Scopus oturumu kullanılır:

```
python -m pip install playwright
python -m playwright install chromium
python -m yayin_paneli.toplayici.tarayici giris https://www.webofscience.com
python -m yayin_paneli.toplayici.tarayici giris https://www.scopus.com
```

Oturum kalıcı profilde saklanır, sonraki toplamalar otomatik çalışır.

> **Uyarı.** Clarivate ve Elsevier kullanım şartları otomatik erişimi kısıtlar. Bu yol
> yalnızca kendi makinenizde, kendi oturumunuzla ve kendi sorumluluğunuzda çalıştırılmak
> üzere yazılmıştır; sunucuya kurulmamalı, paylaşılan bir ortamda kullanılmamalıdır.
> Mümkün olan her durumda `api` yolu tercih edilmelidir.

Saatlik toplama `Senkron` sekmesindeki düğmeyle açılır; her tur `senk_gunlugu`
tablosuna yazılır ve üst çubuktaki durum çipinde görünür.

## İsim eşleştirme ve onay kuyruğu

Türkçe–İngilizce yazım farkları (Shahram Minaei ↔ ŞAHRAM MİNAYİ), diyakritikler
(Pamučar, Šimić) ve kısaltmalar normalleştirilerek eşleştirilir.

- Kesin eşleşme otomatik bağlanır.
- Şüpheli eşleşme (yalnız soyad tutuyor, baş harf belirsiz, yalnızca fonetik benzerlik)
  **Onay kuyruğu** sekmesine düşer. Aday seçilip onaylanır ya da «listede yok»
  işaretlenir; karar takma ad tablosuna yazılır ve bir daha sorulmaz.
- Adjunct isimlerinin tüm varyasyonları tek çatı etiket altında birleşir.

## Geçerli analiz kuralları

- Bildiriler (proceedings paper / conference paper) analiz dışıdır; sayıları ayrıca
  raporlanır.
- Tekilleştirme DOI üzerinden; DOI yoksa başlık + yıl.
- Personel sayımında listedeki her akademik kayıt sayılır — yıl içinde ayrılanlar da
  o yıl çalıştığı için paydaya girer.
- Senaryo A adjunct yayınlarını içerir, B içermez; iki sonuç yan yana verilir.
- Açık erişim yalnızca var/yok olarak sayılır.
- Ödeme raporlarında her para birimi ayrı hesaplanır.

## Veritabanı

Tüm veri `veri/panel.db` içinde. Sürüm 1 veritabanı ilk açılışta otomatik göç eder
(eski `kurum_kayitlari`, `quartiller`, `metrikler` anahtarları tablolara taşınır).
Yedek almak için bu tek dosyayı kopyalamak yeterlidir.

## Testler

```
python -m pytest testler -q
```
