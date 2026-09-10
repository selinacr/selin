# Adjunct Yayin Takip

Her ay gelen "AGUSTOS 2026 Yayinlari" bicimindeki Excel dosyasini okuyup
**kisi bazinda** ve **odeme bazinda** aylik/yillik raporlari guncel tutan
masaustu uygulamasi (Python + tkinter). Veriler yerel bir SQLite dosyasinda
birikir; yeni ayi yukledikce butun tablolar kendiliginden guncellenir.

## Kurulum (Anaconda)

Anaconda'da tkinter ve openpyxl hazir gelir:

```bat
cd C:\...\yayin-takip
python app.py
```

Modul eksigi cikarsa `conda install openpyxl`. Anaconda disinda:
`pip install -r requirements.txt` (Linux'ta ayrica `sudo apt install python3-tk`).

### Masaustu kisayolu (Anaconda Prompt ile ugrasmamak icin)

Anaconda Prompt'ta klasordeyken bir kez:

```bat
python kisayol_olustur.py
```

Masaustunde **Yayin Takip** kisayolu olusur; cift tiklayinca uygulama dogrudan
acilir, konsol penceresi cikmaz. Klasoru baska yere tasirsan betigi yeni
yerinde tekrar calistir.

Ornek ay dosyasi uretmek icin: `python ornek_veri.py`.

## Beklenen dosya duzeni

```
AGUSTOS 2026 Yayinlari                              <- donem buradan okunur
<Kisi Adi>                                          <- bolum basligi
Sıra | Article Title | Journal / Conference | Authors | DOI | Quartile |
       Date | Index Link | Kontrol | Payments
1    | ...                                                     |  431
                                        Toplam |     |  1293   <- kontrol amacli
...
OZET / SUMMARY                                      <- kisi bazinda toplamlar
```

- **Donem** baslik satirindan (yoksa dosya adindan) okunur; arayuzde ay/yil
  acilir listesinden degistirilebilir. Tum kayitlar dosyanin ayina yazilir;
  `Date` sutunu yayinin kendi tarihidir, sadece bilgi olarak saklanir.
- **Kisi**, tek hucreli bolum basligi satirlarindan alinir (basindaki satir
  sonu, fazla bosluk temizlenir).
- **Payments** bos ise kayit "odemesi yok" sayilir; sayilar ve odemeli kayit
  sayisi ayri ayri raporlanir.
- **Para birimi**, `Kontrol` notundan belirlenir: `500/1.1595 (EUR/USD
  Paritesi)` gibi bir not varsa tutar **EUR**'dur ve notun payi (500) USD
  karsiligi olarak saklanir; not "Cin Yuani/CNY" diyorsa **CNY**; not yoksa
  **USD**. Bir kisi her zaman ayni birimde odeniyorsa kisi detay penceresinden
  kural tanimlanabilir (istege bagli olarak gecmis kayitlara da uygulanir).
- Bolumlerdeki `Toplam` ve `OZET` satirlari hesaba katilmaz; satirlardan
  hesaplanan toplam dosyadakinden farkliysa aktarim gunlugunde uyari cikar
  (Agustos 2026 dosyasinda Vladimir Simic satirinda oldugu gibi).

## Kullanim

Uygulama tek ekrandir:

- **Ust satir**: donem araligi ve ozet kutulari (onayli yayin sayisi, para birimi
  bazinda toplamlar, USD karsiligi). Kutular secili filtrelere gore guncellenir.
- **Filtre dugmeleri**: yil (Tumu / 2025 / 2026...), olcu (Odeme tutari,
  USD karsiligi, Onayli yayin, Tum kayitlar) ve para birimi (USD / EUR / CNY).
  Para birimi yalnizca "Odeme tutari" olcusunde etkindir.
- **Gorunumler**: Kisi x ay, Quartile x ay, Dergi, Odeme dagilimi, Kayitlar.
  Pivot tablolarda ay sutunlarindan sonra yil toplamlari ve genel toplam,
  en altta da "Toplam" satiri gelir.
- **Kisiye cift tiklamak** yillik/aylik dokumu ve para birimi kuralini acar.
- **Ara** kutusu kisi, baslik, dergi, DOI, yazar ve Kontrol notunda arar;
  "Sadece odemesi olanlar" kutusu odemesiz kayitlari gizler.
- **Excel'e aktar** o an ekranda gorunen tabloyu bicimli olarak kaydeder.
- **Yeni ay dosyasi yukle** (alt bar) dosyayi cozer, onizleme ve uyarilari
  gosterir, onaylayinca veritabanina yazar. Ayni ay tekrar yuklenirse o ayin
  verisi silinip yeniden yazilir.

## Dosyalar

| Dosya | Icerik |
|---|---|
| `core.py` | Excel ayristirma, para birimi cozumu, SQLite depo, ozet/pivot sorgulari |
| `app.py` | panel arayuzu (ana ekran, ice aktarma ve kisi detay pencereleri) |
| `arayuz.py` | renk paleti, ttk stilleri ve tablo yardimcilari |
| `kisayol_olustur.py` | masaustu kisayolu olusturur (Windows) |
| `ornek_veri.py` | ayni duzende ornek ay dosyasi ureteci |
| `test_core.py` | cekirdek testleri (`python test_core.py`) |

Veritabani varsayilan olarak ev dizininde `yayin_takip.db`; ust bardan
degistirilebilir, yedek almak icin bu dosyayi kopyalamak yeterli.
