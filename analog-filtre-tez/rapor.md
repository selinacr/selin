# Analog Filtre Tasarımı ve Sensör Sinyal Koşullandırma
### Yüksek Lisans Tezi — Hazırlık Raporu

> Konu ekseni: **Sensör çıkışlarına yönelik (ihtiyaca uygun) analog filtre tasarımı**, klasik (tamsayı dereceli) filtrelerden **kesirli dereceden (fractional-order) filtrelere** uzanan bir çerçeve. Örnek sensör platformu: Hamamatsu fotoçoğaltıcı tüpler (PMT) **R6094/R6095** ve foton sayma kafası **H7711-03**.

---

## 1. Giriş

Bir filtre, bir sinyalin frekans bileşenlerini seçici biçimde geçiren/zayıflatan bir sistemdir. Sensör tabanlı ölçüm zincirinde filtre üç ana görevi üstlenir:

1. **Bant sınırlama / gürültü azaltma** — ilgilenilen bant dışındaki gürültüyü (termal, atış, 1/f, şebeke 50 Hz) bastırmak; SNR'ı artırmak.
2. **Sinyal şekillendirme (pulse shaping)** — özellikle darbe tabanlı sensörlerde (PMT, dedektörler) gürültü-bant genişliği ödünleşimini optimize eden CR-RC / Gauss şekillendirme.
3. **Anti-aliasing** — ADC öncesi örtüşmeyi (aliasing) önleyici alçak geçiren süzme.

Bu tezin özgün açısı: **"ihtiyaca uygun" filtre** kavramını, klasik yaklaşımların (Butterworth, Chebyshev, Bessel) sunamadığı **ara dereceler** ve **esnek roll-off / faz** davranışı üzerinden kesirli dereceden filtrelerle genişletmek; ardından bu filtreleri gerçek bir sensör problemine — PMT / foton sayma okuma elektroniğine — uygulamak.

### 1.1 Sensör köprüsü neden PMT?

PMT çıkışı, anottan gelen çok kısa (ns–µs) **akım darbeleri** dizisidir. Bu sinyal:
- **Transimpedans (akım→gerilim)** dönüşümü,
- **şekillendirme filtresi** (darbe genliğini ölçmek veya saymak için),
- **gürültü filtreleme** ve foton sayma modunda **diskriminatör**

gerektirir. Yani analog filtre tasarımı PMT okuma zincirinin tam kalbindedir — tez için "uygulama" tarafı doğal olarak buradan gelir.

---

## 2. Filtrelerin Sınıflandırılması

**(a) Frekans seçiciliğine göre:** Alçak geçiren (LP), yüksek geçiren (HP), bant geçiren (BP), bant söndüren / çentik (BS/notch), tüm geçiren (all-pass, faz eşitleme).

**(b) Teknolojiye göre:**
- *Pasif* (R, L, C) — güç gerektirmez, yüksek frekans, kazanç < 1.
- *Aktif* (op-amp, OTA, CCII, CFOA tabanlı) — kazanç, indüktörsüz, ayarlanabilir.
- *Anahtarlamalı kapasitör (SC)* — saat frekansıyla ayarlanabilir, entegre.
- *Sayısal (DSP/FPGA)* — esnek ama gecikme + ADC gerektirir.

**(c) Yaklaşım (approximation) ailesine göre:** Butterworth, Chebyshev I/II, Bessel-Thomson, Eliptik (Cauer), ve bu tezin merkezindeki **kesirli dereceden** yaklaşımlar.

Her ailenin ödünleşimi: genlik düzlüğü ↔ geçiş bandı keskinliği ↔ grup gecikmesi düzlüğü (faz lineerliği) ↔ devre karmaşıklığı.

---

## 3. Temel Transfer Fonksiyonları ve Dereceler

Bir filtre, Laplace düzleminde rasyonel bir transfer fonksiyonuyla tanımlanır:
`H(s) = N(s) / D(s)`. **Derece**, paydadaki en yüksek s kuvvetidir ve asimptotik roll-off'u belirler: tamsayı n. derece → **−20·n dB/dekad**.

### 3.1 Birinci derece (n = 1)

Alçak geçiren:
```
H(s) = ω_c / (s + ω_c)        |H(jω)| = 1/√(1+(ω/ω_c)²)
```
Yüksek geçiren:
```
H(s) = s / (s + ω_c)
```
- Kesim frekansı `ω_c = 1/RC`, eğim **−20 dB/dek**, kesimde faz −45°.
- Tek kutup; pasif RC veya tek op-amp ile gerçeklenir.

### 3.2 İkinci derece (n = 2) — "biquad"

Genel alçak geçiren:
```
H(s) = ω_0² / ( s² + (ω_0/Q)·s + ω_0² )
```
- `ω_0`: doğal (köşe) frekans, `Q`: kalite faktörü (sönüm `ζ = 1/(2Q)`).
- `Q = 0.707` → maksimum düz (Butterworth); `Q > 0.707` → tepe (peaking).
- Kutuplar: `s = −ω_0/(2Q) ± jω_0·√(1 − 1/(4Q²))`.

Bant geçiren ve çentik formları:
```
BP:    H(s) = (ω_0/Q)·s / ( s² + (ω_0/Q)s + ω_0² )
Notch: H(s) = (s² + ω_0²) / ( s² + (ω_0/Q)s + ω_0² )
```
Gerçeklemeler: **Sallen-Key**, **çok geri beslemeli (MFB)**, **durum-değişkenli (KHN)**, **Tow-Thomas**, **Åkerberg-Mossberg**.

### 3.3 Üçüncü derece (n = 3)

3. derece = 1 reel kutup + 1 karmaşık eşlenik kutup çifti (bir 1. + bir 2. derece kademe kaskadı):
```
H(s) = [ ω_a/(s+ω_a) ] · [ ω_0² / (s² + (ω_0/Q)s + ω_0²) ]
```
- Eğim **−60 dB/dek**.
- Butterworth (n=3) kutupları birim yarıçaplı çemberde 60°'lik aralıklarla: `s = −1, −0.5 ± j0.866` (normalize, ω_c=1).
- Tek op-amp'lı 3. derece Sallen-Key türevleri veya 1.+2. derece kaskad ile yapılır.

> **Genel kural:** Yüksek dereceler, düşük dereceli (1. ve 2.) **kademelerin kaskadı** olarak gerçeklenir; bu, hassasiyet ve ayarlanabilirlik açısından tek bloktan üstündür.

---

## 4. Yaklaşım (Approximation) Aileleri ve Formülleri

İdeal "tuğla-duvar" filtre fiziksel değildir; aileler ideale farklı kriterlerle yaklaşır.

**Butterworth — maksimum düz genlik:**
```
|H(jω)|² = 1 / ( 1 + (ω/ω_c)^{2n} )
```
Geçiş bandında dalgasız, orta keskinlik, kabul edilebilir faz.

**Chebyshev I — geçiş bandında dalgalı, daha keskin:**
```
|H(jω)|² = 1 / ( 1 + ε²·T_n²(ω/ω_c) )
```
`T_n`: n. derece Chebyshev polinomu, `ε`: dalga genliği. Tip II dalgayı durdurma bandına taşır.

**Bessel-Thomson — maksimum düz grup gecikmesi:** En lineer faz / en iyi darbe (overshoot'suz) tepkisi; genlik geçişi en yumuşak. *Darbe sensörleri (PMT!) için kritik.*

**Eliptik (Cauer):** Hem geçiş hem durdurma bandında dalga; **en keskin geçiş**, en düşük derece — ama en kötü faz.

| Aile | Genlik | Geçiş keskinliği | Grup gecikmesi | PMT şekillendirmeye uygunluk |
|------|--------|------------------|----------------|------------------------------|
| Butterworth | düz | orta | orta | iyi (genel amaç) |
| Chebyshev I | dalgalı | yüksek | kötü | sınırlı |
| Bessel | yumuşak | düşük | **en düz** | **çok iyi (darbe)** |
| Eliptik | dalgalı | **en yüksek** | en kötü | zayıf |

---

## 5. Topolojiler (Gerçekleme Yapıları)

**Pasif:** RC (tek kutup), RLC rezonatör, LC merdiven (ladder) — RF/yüksek frekans, düşük gürültü, indüktör hacmi sorunu.

**Aktif (op-amp tabanlı biquad):**
- **Sallen-Key** — basit, düşük Q için kararlı, az eleman.
- **Çok Geri Beslemeli (MFB / Rauch)** — düşük çıkış empedansı, iyi yüksek-frekans davranışı.
- **Durum-Değişkenli (KHN)** — aynı anda LP/HP/BP çıkışları, yüksek Q, ayarlanabilir; iki entegratör + toplayıcı.
- **Tow-Thomas / Åkerberg-Mossberg** — düşük hassasiyet, sağlam Q-ω ayrımı.

**Aktif eleman alternatifleri (bu tez için önemli):**
- **OTA-C / Gm-C** — `ω_0 ∝ g_m/C`, **gerilimle/akımla elektronik ayar**, entegre, yüksek frekans. Kesirli dereceli filtre gerçeklemenin favori yolu.
- **CCII (ikinci nesil akım taşıyıcı), CFOA, DVCC, VDTA** — akım modlu, geniş bant, düşük gerilim.
- **FPAA (sahada programlanabilir analog dizi)** — donanımda hızlı prototip; kesirli dereceli yaklaşımları deneysel doğrulamak için ideal.
- **Anahtarlamalı kapasitör** — saatle ayarlanabilir köşe frekansı.

---

## 6. Kesirli Dereceden (Fractional-Order) Filtreler

### 6.1 Motivasyon

Tamsayı derecede roll-off yalnızca −20, −40, −60… dB/dek olabilir. **Kesirli derece α ∈ (0,1)** sürekli bir spektrum açar: eğim **−20·(n+α) dB/dek** olarak *ince ayarlanabilir*. Bu, "ihtiyaca uygun" (örn. tam −33 dB/dek isteyen) bir tasarım için ek bir serbestlik derecesidir; ayrıca **daha esnek faz/grup gecikmesi** ve bazı durumlarda **daha düşük eleman sayısıyla istenen şablonu** yakalama imkânı verir.

### 6.2 Matematiksel temel

Kesirli türevin Laplace karşılığı `s^α` (sıfır başlangıç koşullarıyla). Temel yapı taşı **kesirli kapasitör / sabit faz elemanı (CPE)**:
```
Z(s) = 1 / (C_α · s^α),     faz açısı = −α·90°   (sabit, frekanstan bağımsız)
```
α=1 ideal kapasitör, α=0 direnç. Bir **kesirli (1+α). derece** alçak geçiren:
```
H(s) = 1 / ( s^{1+α} + a·s^α + b )      (0 < α < 1)
```
veya en yalın kesirli birinci derece:
```
H(s) = 1 / ( τ·s^α + 1 ),   yüksek frekans eğimi −20α dB/dek
```

**Kararlılık (Matignon teoremi):** `s^α = w` dönüşümüyle W-düzleminde kutuplar için `|arg(w)| > α·π/2` ise sistem kararlıdır — tamsayı durumun genellemesi.

### 6.3 `s^α`'nın rasyonel yaklaşımı (gerçekleme için zorunlu)

`s^α` ideal olarak gerçeklenemez; sonlu bir bantta rasyonel (kutup-sıfır) yaklaşımı kullanılır:
- **Oustaloup özyinelemeli yaklaşımı** — `[ω_b, ω_h]` bandında N kutup/sıfır; kontrol literatüründe standart.
- **Sürekli kesir açılımı (CFE)** — kompakt rasyonel ifadeler.
- **Matsuda**, **Charef (tekillik fonksiyonu)**, **Carlson** yöntemleri.

Bu yaklaşımlar daha sonra **RC merdiven (Foster/Cauer)**, **OTA-C** veya **FPAA** ile devreye dökülür.

### 6.4 Gerçekleme yolları

- **RC merdiven ağları** ile CPE emülasyonu (pasif, sabit).
- **OTA-C / Gm-C** — elektronik ayarlı kesirli filtreler (literatürde en yaygın).
- **FPAA** — programlanabilir, deneysel doğrulamada güçlü.
- **FLF / IFLF** (follow-the-leader / inverse) çok geri beslemeli mimariler.

---

## 7. Literatür Taraması (başlangıç çekirdeği)

**Kesirli dereceli analog filtre/sensör eksenli derlemeler ve anahtar çalışmalar:**
- *A Review of Recent Advances in Fractional-Order Sensing and Filtering Techniques*, Sensors (MDPI), 2021 — tasarım yöntemleri + uygulanabilirlik. (PMC8434365)
- *A review of the state-of-the-art in fractional-order analog filters*, ScienceDirect, 2025 — güncel topoloji ve yaklaşım envanteri.
- *On the Design Flow of the Fractional-Order Analog Filters Between FPAA Implementation and Circuit Realization*, IEEE, 2023 — FPAA ↔ devre gerçekleme akışı.
- *CMOS OTA-Based Filters for Designing Fractional-Order Chaotic Oscillators*, Fractal Fract (MDPI), 2021 — OTA-C kesirli blok.
- Klasik referans: Sedra & Smith, *Microelectronic Circuits* (filtre bölümleri); Schaumann & Van Valkenburg, *Design of Analog Filters*; Podlubny, *Fractional Differential Equations* (matematiksel temel).

**Sensör/PMT okuma elektroniği ve darbe şekillendirme:**
- Hamamatsu, *Photomultiplier Tubes — Basics and Applications* (PMT el kitabı; gürültü, foton sayma, şekillendirme bölümleri).
- Nükleer enstrümantasyonda CR-RC^n ve Gauss şekillendirme literatürü (gürültü-bant ödünleşimi, ENC analizi).

> Öneri: Web of Science / IEEE Xplore'da `fractional-order filter`, `Gm-C fractional`, `fractional-order pulse shaping`, `CPE emulation`, `photomultiplier signal conditioning` anahtarlarıyla son 5 yılı tarayıp 30–40 kaynaklık bir matris (yıl / topoloji / aktif eleman / derece / doğrulama yöntemi) çıkar.

---

## 8. Sensör Künyeleri (Uygulama Tarafı)

### 8.1 Hamamatsu R6094 / R6095 (PMT, tüp)
- 28 mm çap, **head-on**, **bialkali fotokatot**; etkin alan ~25 mm.
- Spektral tepki **300–650 nm**, tepe ~420 nm.
- 14 pinli, ~2000 V'a kadar besleme; tipik 10 dinotlu kazanç eğrisi.
- Çıkış: anot **akım darbeleri** → transimpedans + şekillendirme gerektirir.

### 8.2 Hamamatsu H7711-03 (foton sayma kafası / modül)
- İçinde PMT + **yüksek gerilim kaynağı + amplifikatör + diskriminatör** entegre.
- Çıkış: **TTL darbe** (foton sayma modu) — yani üretici şekillendirme/diskriminasyonu modül içine almış.
- Düşük gerilimli (tipik +5 V besleme sınıfı) çalışır.

**Tez için kıyasın değeri:** R6094/R6095 sana **ham analog zinciri kendin tasarlama** (transimpedans → kesirli/klasik şekillendirme → diskriminatör) imkânı verir; H7711-03 ise **referans/altın standart** (entegre, ticari) olarak kıyas noktası olur. "Kendi tasarladığım kesirli dereceli şekillendirici, ticari modülün performansına ne kadar yaklaşıyor / nerede geçiyor?" sorusu güçlü bir tez sorusudur.

---

## 9. Tez Çalışması İçin Plan ve Öneriler

### 9.1 Önerilen tez sorusu
> *"Sensör (PMT) sinyal koşullandırmada kesirli dereceden analog filtrelerin, klasik tamsayı dereceli şekillendiricilere göre gürültü-bant genişliği, faz/grup gecikmesi ve darbe ayrışımı (pile-up) açısından sağladığı kazanımların tasarlanması, gerçeklenmesi ve deneysel doğrulanması."*

### 9.2 İş paketleri (WP)
1. **WP1 — Literatür & teori:** Klasik + kesirli filtre matematiği, `s^α` yaklaşımları, PMT gürültü/şekillendirme teorisi.
2. **WP2 — Sensör karakterizasyonu:** R6094/R6095 darbe şekli, gürültü tabanı; H7711-03 referans ölçümleri.
3. **WP3 — Tasarım:** (a) Klasik referans şekillendirici (CR-RC, Bessel); (b) Kesirli dereceli (1+α) şekillendirici — Oustaloup/CFE yaklaşımı + OTA-C veya FPAA gerçekleme.
4. **WP4 — Simülasyon:** MATLAB/Python (transfer fonksiyonu, Bode, grup gecikmesi, gürültü) + LTspice/Cadence (devre düzeyi).
5. **WP5 — Donanım & doğrulama:** FPAA (örn. Anadigm) veya ayrık OTA kartı; gerçek PMT sinyaliyle SNR, ENC, sayım doğruluğu kıyası.
6. **WP6 — Değerlendirme & yazım:** Klasik vs. kesirli performans matrisi; tez + makale.

### 9.3 Araç önerileri
- **Modelleme:** MATLAB (FOMCON / Ninteger araç kutuları), Python (`scipy.signal`, `numpy`).
- **Devre:** LTspice (ücretsiz), gerekirse Cadence/ADS.
- **Kesirli yaklaşım:** Oustaloup (FOMCON), CFE scriptleri.
- **Donanım:** FPAA (hızlı prototip) veya ayrık OTA (örn. LM13700) / CCII kartı.

### 9.4 Özgün değer (yüksek lisans seviyesinde savunulabilir)
- Kesirli dereceyi **sensöre-özgü bir ihtiyaca** (PMT darbe ayrışımı / belirli bir roll-off şablonu) bağlamak — salt teorik kesirli filtre çalışmalarından ayrışır.
- Klasik vs. kesirli için **adil, ölçülmüş** kıyas (SNR, ENC, faz, eleman sayısı).

### 9.5 TÜBİTAK ticarileşme köprüsü
Tez "yöntem + doğrulama" üretir; ticarileşme tarafında:
- **1512 BiGG / 1501 / 1507 (TEYDEB):** "Sensörlere uyarlanabilir, elektronik ayarlı (kesirli dereceli) analog şekillendirme/filtre modülü" ürünleştirme.
- **1001:** Bilimsel tarafı derinleştiren araştırma (genellenebilir tasarım metodolojisi).
- **2244 / 2210:** Öğrenci/burs bileşeni.
- Anlatı: *yerli, ayarlanabilir, çok-sensörlü (PMT, titreşim, biyo-potansiyel) analog ön-uç filtre platformu.* (Önceki konuşmadaki titreşim transmitteri de aynı platformun bir uygulaması olarak konumlanabilir.)

---

## 10. Sunum İskeleti (slayt slayt)

1. **Başlık** — Tez konusu, ad, danışman, tarih.
2. **Motivasyon** — Sensör sinyalleri neden filtre ister? (PMT darbesi + gürültü görseli)
3. **Amaç & araştırma sorusu** — Kesirli dereceli filtrelerle "ihtiyaca uygun" tasarım.
4. **Filtre temelleri** — Sınıflandırma + LP/HP/BP/BS.
5. **Dereceler & formüller** — 1./2./3. derece transfer fonksiyonları, roll-off.
6. **Yaklaşım aileleri** — Butterworth/Chebyshev/Bessel/Eliptik kıyas tablosu.
7. **Topolojiler** — Sallen-Key, MFB, KHN, OTA-C, FPAA.
8. **Kesirli dereceli filtreler** — `s^α`, CPE, (1+α) derece, roll-off −20α dB/dek.
9. **`s^α` yaklaşımı** — Oustaloup/CFE + gerçekleme.
10. **Literatür** — Anahtar derlemeler + boşluk (gap) tespiti.
11. **Sensörler** — R6094/R6095 + H7711-03 künyesi ve okuma zinciri.
12. **Tez planı** — İş paketleri, araçlar, takvim (Gantt).
13. **Beklenen katkı & ticarileşme (TÜBİTAK)**.
14. **Kaynaklar.**

---

## Kaynaklar

- Hamamatsu, R6094/R6095 PMT spesifikasyonu (TPMH1382E): https://www.hamamatsu.com/content/dam/hamamatsu-photonics/sites/documents/99_SALES_LIBRARY/etd/R6094_R6095_TPMH1382E.pdf
- Hamamatsu, R6094 ürün sayfası: https://www.hamamatsu.com/us/en/product/optical-sensors/pmt/pmt_tube-alone/head-on-type/R6094.html
- Hamamatsu, Foton sayma kafaları (H7711 ailesi dahil): https://www.hamamatsu.com/us/en/product/optical-sensors/pmt/pmt-module/photon-counting-head.html
- H7711 datasheet (arşiv): https://www.alldatasheet.com/datasheet-pdf/pdf/62589/HAMAMATSU/H7711.html
- A Review of Recent Advances in Fractional-Order Sensing and Filtering Techniques, Sensors 2021: https://pmc.ncbi.nlm.nih.gov/articles/PMC8434365/
- A review of the state-of-the-art in fractional-order analog filters, 2025: https://www.sciencedirect.com/science/article/abs/pii/S143484112500127X
- On the Design Flow of the Fractional-Order Analog Filters Between FPAA Implementation and Circuit Realization, IEEE 2023: https://ieeexplore.ieee.org/document/10077570/
- CMOS OTA-Based Filters for Fractional-Order Chaotic Oscillators, Fractal Fract 2021: https://doi.org/10.3390/fractalfract5030122
