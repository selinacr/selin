# Doğuş Üniversitesi Yayın Analiz Paneli — Devam Promptu

Bu metni yeni bir sohbete olduğu gibi yapıştır; sistemin ne olduğunu, neyi kapsadığını ve
nasıl çalıştığını anlatır.

---

## Kimim, ne yapıyorum

Doğuş Üniversitesi ARDES (Araştırma Destek) ofisinde çalışıyorum. Üniversitenin akademik
yayın performansını izliyor, yayın teşvik (BEDEK) süreçlerini yürütüyor ve adjunct (sözleşmeli
dış) öğretim üyelerinin yayın bazlı ödemelerini takip ediyorum. Rektörlük ve birimler için
yıllık/dönemsel yayın raporları hazırlıyorum.

## Elimdeki panel

İki ayrı uygulama olarak yazıldı, ikisi de aynı mantığı paylaşıyor:

1. **Web paneli** — `yayin-paneli/index.html`. Tek dosyalık HTML/JS uygulaması (Claude
   Artifact olarak yayında, verileri artifact veritabanında saklıyor). Excel/CSV dosyalarını
   tarayıcıda SheetJS ile okuyor.
2. **Python sürümü** — `yayin-paneli-python/`. Streamlit arayüzü + SQLite veritabanı.
   `yayin_paneli/` paketi: `metin.py` (isim normalleştirme), `ayristirma.py` (dosya
   çözümleyiciler), `analiz.py` (tüm analiz mantığı), `aylik.py` (adjunct ödeme dönemleri),
   `depo.py` (SQLite). `testler/test_panel.py` altında 18 test var.
3. **Masaüstü sarmalayıcı** — `yayin-paneli-masaustu/`. Web panelini Electron ile masaüstü
   uygulaması olarak açıyor; GitHub Actions ile Windows .exe üretiliyor.

Windows'ta Anaconda ile çalıştırıyorum (`baslat.bat`). Paket adı bilerek `yayin_paneli`;
Anaconda'nın kendi `panel` paketi ile çakışıyordu.

## Panelin iki modu

**A) Kurum yayın paneli** — üniversitenin tüm yayınları.
Girdi dosyaları:
- WoS "Full Record" Excel dosyaları, yıl yıl (2022–2026).
- Scopus CSV export'ları (Authors, Author full names, Title, Year, Cited by, DOI,
  Document Type, Open Access, EID).
- Personel listesi Excel'i (ad, soyad, unvan, fakülte/birim, giriş–çıkış tarihi, akademik mi).
- SCImago SJR CSV'leri (yıl bazlı, çeyreklik eşleştirmesi için).
- OpenAlex yazar JSON sayfaları (atıf sayısı ve h-indeksi için; kurum id `I129994210`).

**B) Adjunct paneli** — sözleşmeli dış öğretim üyelerinin dönemsel yayın ödemeleri.
Girdi: aylık "Makale Puantaj" Excel'leri. Kayıtları panelden elle de düzenleyebiliyorum.

## Geçerli kurallar (bunlara uy)

- **Proceeding Paper / bildiri analiz dışı.** Sayılmaz ama "analiz dışı bildiri" olarak ayrıca
  raporlanır.
- **Kaynak birleştirme:** WoS esas, Scopus boşlukları doldurur; tekilleştirme DOI üzerinden.
  Kaynak seçimi WoS / Scopus / birleşik olarak filtrelenebilir.
- **İsim eşleştirme:** Türkçe–İngilizce yazım farkları yüzünden aynı kişi ayrı görünebiliyor
  (Shahram Minaei = ŞAHRAM MİNAYİ, M. I. Sayyed = Abualsayed Mohamad Ibrahim,
  Pamučar, Šimić gibi diyakritikler). `sade()` Türkçe + NFD normalleştirme, `fonetik()`
  fonetik anahtar, `adlar_uyuyor()` katı mod, artı elle tanımlı takma ad listesi kullanılıyor.
  Yanlış birleştirmeler oldu (Aydin/Ali Murat ↔ Muhammed Ali Aydın gibi), bu yüzden fonetik
  katman katı modda çalışıyor.
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
