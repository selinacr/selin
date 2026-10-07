# Doğuş Üniversitesi Yayın Analiz Paneli — Devam Promptu

Bu metni yeni bir sohbete olduğu gibi yapıştır; sistemin ne olduğunu, neyi kapsadığını ve
nasıl çalıştığını anlatır.

---

## Kimim, ne yapıyorum

Doğuş Üniversitesi ARDES (Araştırma Destek) ofisinde çalışıyorum. Üniversitenin akademik
yayın performansını izliyor, yayın teşvik (BEDEK) süreçlerini yürütüyor ve adjunct (sözleşmeli
dış) öğretim üyelerinin yayın bazlı ödemelerini takip ediyorum. Rektörlük ve birimler için
yıllık/dönemsel yayın raporları hazırlıyorum.

## Elimdeki panel (sürüm 2)

Tek bir Python çekirdeği, üç arayüz:

1. **PWA arayüzü** — `yayin-paneli-python/web/`. `python -m yayin_paneli.servis` ile
   açılan FastAPI servisi (127.0.0.1:8787) bunu sunar. Koyu/açık tema, bağımlılıksız SVG
   grafikler, hizmet işçisiyle çevrimdışı açılış, masaüstü ve telefona "uygulama olarak
   yükle". Ana arayüz budur.
2. **Streamlit sürümü** — `yayin-paneli-python/app.py`. Aynı veritabanı; dosya yükleme
   ekranları için pratik.
3. **Masaüstü sarmalayıcı** — `yayin-paneli-masaustu/`. Electron, yerel servise bağlanır;
   GitHub Actions ile Windows .exe üretiliyor.

Çekirdek `yayin_paneli/` paketi: `metin.py` (isim normalleştirme), `ayristirma.py` (dosya
çözümleyiciler), `analiz.py` (analiz mantığı), `eslesme.py` (takma ad + onay kuyruğu),
`aylik.py` (adjunct ödemeleri), `depo.py` (SQLite şeması), `toplayici/` (WoS/Scopus
otomatik toplama + saatlik zamanlayıcı), `servis.py` (JSON API). Mimari: `MIMARI.md`.
39 test var (`python -m pytest testler -q`).

`yayin-paneli/index.html` sürüm 1'in tek dosyalık arayüzüdür; arşivde duruyor,
geliştirilmiyor.

Windows'ta Anaconda ile çalıştırıyorum (`baslat_panel.bat`). Paket adı bilerek
`yayin_paneli`; Anaconda'nın kendi `panel` paketi ile çakışıyordu.

## Panelin iki modu

**A) Kurum yayın paneli** — üniversitenin tüm yayınları.
Girdi dosyaları:
- WoS "Full Record" Excel dosyaları, yıl yıl (2022–2026) — ya da WoS Starter API.
- Scopus CSV export'ları (Authors, Author full names, Title, Year, Cited by, DOI,
  Document Type, Open Access, EID) — ya da Scopus Search API.
- Personel listesi Excel'i (ad, soyad, unvan, fakülte/birim, giriş–çıkış tarihi, akademik mi).
- Çeyreklik: WoS için JCR dışa aktarımı, Scopus için Sources/CiteScore dosyası
  (ya da ilgili API uçları). OpenAlex ve SCImago SJR artık kullanılmıyor.
- h-indeksi ve atıf: WoS ve Scopus yazar profilleri, kaynak bazında ayrı saklanır.

**B) Adjunct paneli** — sözleşmeli dış öğretim üyelerinin dönemsel yayın ödemeleri.
Girdi: aylık "Makale Puantaj" Excel'leri. Kayıtları panelden elle de düzenleyebiliyorum.

## Geçerli kurallar (bunlara uy)

- **Proceeding Paper / bildiri analiz dışı.** Sayılmaz ama "analiz dışı bildiri" olarak ayrıca
  raporlanır.
- **Kaynak birleştirme:** WoS esas, Scopus boşlukları doldurur; tekilleştirme DOI üzerinden.
  Kaynak seçimi WoS / Scopus / birleşik olarak filtrelenebilir.
- **İsim eşleştirme:** Türkçe–İngilizce yazım farkları yüzünden aynı kişi ayrı görünebiliyor
  (Shahram Minaei = ŞAHRAM MİNAYİ, M. I. Sayyed = Abualsayed Mohamad Ibrahim,
  Pamučar, Šimić gibi diyakritikler). Kesin eşleşme otomatik bağlanır; şüpheli olanlar
  **onay kuyruğuna** düşer ve panelden tek tıkla onaylanır. Karar takma ad tablosuna
  yazılır, bir daha sorulmaz. Yanlış otomatik birleştirmeler (Abanoz, Yasin ↔ YEŞİM
  ABANOZ gibi) bu yüzden artık otomatik yapılmıyor.
- **Çeyreklik iki kaynakta ayrı:** her yayın hem `q_wos` (JCR) hem `q_scopus`
  (CiteScore/SJR) taşır; panelde yan yana karşılaştırılır. Sürüm 1'den devralınan eski
  liste yalnızca boşluk doldurur.
- **Personel sayımı:** Listede kaydı olan her akademik personel paydaya girer; yıl içinde
  ayrılanlar da o yıl çalıştığı için sayılır. (Toplam 524 akademik kayıt.)
- **Senaryo A / B:** A adjunct yayınlarını dahil eder, B hariç tutar. Her iki sonuç yan yana
  gösterilir.
- **Çeyreklik (Q1–Q4):** ISSN üzerinden SJR eşleşmesi, bulunamazsa dergi adıyla; yayın yılı
  için liste yılı eşlemesi var (2026 → 2025 listesi).
- **Açık erişim:** sadece var/yok. Gold, hybrid vb. ayrımı istemiyorum.
- **Ödeme raporları:** Her para birimi (TRY, EUR, USD, CNY...) ayrı ayrı hesaplanır.
  "USD karşılığı" hesabı istemiyorum. Her adjunct sözleşmesine göre yalnız WoS ya da yalnız
  Scopus üzerinden kontrol edilir.
- **Panelde olmamasını istediğim şeyler:** kişi bazlı atıf kolonları, h-indeksi kolonları,
  "ödenen yayın" alanı, ödeme dağılımı görünümü, "kontrol bekliyor" durumu, üstteki para
  birimi çipleri.
- **İndeks kısaltmaları** açılımlarıyla yazılır (SCI-EXPANDED, SSCI, A&HCI, ESCI, CPCI-S,
  CPCI-SSH, BKCI).

## Panelin ürettiği çıktılar

Yıl bazlı yayın sayıları ve açık erişim oranı; çeyreklik dağılımı (A/B senaryolu); indeks
dağılımı; fakülte/birim tablosu (personel, yayın, yayın/kişi, açık erişim); kişi bazlı tablo
(yıl yıl); dergi bazlı liste; adjunct tarafında kişi × ay ödeme pivotu (her para birimi ayrı).

## Güncel referans rakamlar (doğrulama için)

1312 tekil yayın, 101 analiz dışı bildiri, Q1 575 (senaryo A) / 362 (B), 524 akademik personel,
237 kişide OpenAlex metriği eşleşti.

## Benden gelecek tipik istekler

- "Şu yılın şu bölümü için Q1 sayısı, öğretim elemanı başına yayın, açık erişim oranı."
- "Yeni indirdiğim WoS/Scopus dosyalarını yükle, verileri güncelle."
- "Şu kişi listede yok demişsin ama o adjunct / aynı kişi, birleştir."
- "Şu dönemin puantaj tablosu ve karar yazısı ekte, şu bölümden kaç kişi teşvik almış."
- Panelde kolon/görünüm ekleme, silme, yeniden adlandırma.

## Nasıl çalışmanı istiyorum

- Kısa yaz, birkaç cümleyi geçme. Madde listesi ve başlık kullanma, sorulmadan öneri sıralama.
- Sayıları gerçekten hesapla; tahmin etme. Hem WoS hem Scopus sorulduğunda ikisini ayrı ayrı
  ve birleşik olarak ver.
- Değişiklikleri hem web panelinde hem Python sürümünde aynı şekilde uygula, testleri çalıştır,
  `claude/monthly-broadcast-desktop-app-3w2h9x` dalına commit edip push et.
- Canlı WoS/Scopus API erişimim yok (abonelik yok); veriler elle indirilen dosyalardan geliyor.
  Atıf/h-indeksi için OpenAlex kullanılabilir.
