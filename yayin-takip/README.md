# Yayin Takip

Aylik yayin Excel'lerini ice aktarip **kisi bazinda** ve **odeme bazinda**
aylik/yillik guncel raporlar veren masaustu uygulamasi (Python + tkinter).
Veriler yerel bir SQLite dosyasinda birikir; her ay yeni Excel'i aktardikca
raporlar guncellenir.

## Kurulum

### Anaconda ile (Windows'ta en kolayi)

Anaconda'da tkinter ve openpyxl zaten kuruludur, ek kurulum gerekmez:

1. Baslat menusunden **Anaconda Prompt**'u ac.
2. Klasore gec ve calistir:

```bat
cd C:\...\selin\yayin-takip
python app.py
```

Modul eksigi cikarsa: `conda install openpyxl`.
`calistir.bat` dosyasini cift tiklamak da ayni isi yapar (Anaconda'yi PATH'e
eklemediysen dosyayi Anaconda Prompt icinden `calistir.bat` diye cagir).

### Diger kurulumlar

```bash
pip install -r requirements.txt      # sadece openpyxl
python app.py
```

Python 3.10+ gerekir. tkinter Windows/macOS kurulumlarinda hazir gelir;
Linux'ta `sudo apt install python3-tk`.

## Her ay ne yapacaksin

Yeni ayin Excel'ini "1) Excel ice aktar" sekmesinden sec → profilini yukle →
"Veritabanina aktar". Eski aylar veritabaninda durdugu icin butun raporlar
(kisi, odeme turu, aylik, yillik) otomatik guncellenir; ayni dosyayi yanlislikla
iki kez aktarirsan mukerrer kayit olusmaz. Bir ayin duzeltilmis surumu gelirse
"Donemleri sil ve yeniden yaz" secenegini kullan.

Denemek icin ornek dosya: `python ornek_veri.py` → `ornek_yayin.xlsx`.

## Kullanim

1. **Excel ice aktar**: dosyayi ve sayfayi sec. Baslik satiri ve kolonlar
   otomatik tahmin edilir (Tarih, Ad Soyad, Odeme Turu, Brut, Kesinti, Net...);
   yanlissa acilir listelerden duzelt, "Eslemeyi kaydet" ile profil olarak sakla —
   sonraki ay tek tikla yuklenir. Onizlemeyi kontrol edip "Veritabanina aktar".
   - *Ayni kayitlari atla*: mukerrer satirlar iki kez yazilmaz (varsayilan).
   - *Donemleri sil ve yeniden yaz*: duzeltilmis bir ay dosyasi geldiginde kullan.
2. **Kisi bazinda**: yil/ay filtresi, kisi toplamlari veya kisi × ay pivotu
   (net/brut/kesinti/adet olcusu secilebilir). Kisiye cift tiklayinca yillik ve
   odeme turu dokumu acilir.
3. **Odeme bazinda**: odeme turu toplamlari, odeme turu × ay pivotu, kanal pivotu.
4. **Aylik / yillik**: donem serisi ve yil toplamlari; kisi ve odeme turu filtreli.
5. **Kayitlar**: ham satirlar, arama, donem silme.

Her sekmedeki tablo "Excel'e aktar" ile bicimli bir rapor dosyasina yazilir.

## Beklenen Excel yapisi

Zorunlu iki alan: **kisi** ve **tarih/donem**. Digerleri (odeme turu, eser,
kanal, adet, brut, kesinti, net) varsa kullanilir. Net bos ise `brut - kesinti`
olarak hesaplanir.

- Tarih bicimleri: `15.03.2026`, `2026-03-15`, `03.2026`, `Mart 2026`, `202603`.
- Tutar bicimleri: `1.234,56 TL`, `1,234.56`, `(120,50)` (negatif).
  Sadece nokta iceren ve son grubu 3 haneli olan degerler (`2.500`) binlik
  ayraci kabul edilir.

## Dosyalar

| Dosya | Icerik |
|---|---|
| `core.py` | Excel okuma, kolon eslestirme, SQLite depo, ozet/pivot sorgulari |
| `app.py` | tkinter arayuzu |
| `ornek_veri.py` | ornek Excel ureteci |
| `test_core.py` | cekirdek testleri (`python test_core.py`) |

Veritabani varsayilan olarak ev dizininde `yayin_takip.db`; ust bardan
degistirilebilir (yedek almak icin bu dosyayi kopyalamak yeterli).
