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

1. **Ayin Excel'ini yukle**: dosyayi sec, donemi dogrula, onizlemeyi kontrol et,
   "Veritabanina aktar". Ayni ay tekrar yuklenirse o ayin verisi silinip
   yeniden yazilir (mukerrer kayit olusmaz).
2. **Kisi bazinda**: kisi x ay pivotu veya toplam ozet. Olcu secilebilir:
   odeme tutari, USD karsiligi, kayit sayisi, odemeli yayin sayisi. Filtreler:
   yil, ay, para birimi, sadece odemesi olanlar, serbest arama. Kisiye cift
   tiklayinca yillik/aylik dokum ve para birimi kurali acilir.
3. **Odeme bazinda**: para birimi, odeme tutari (500/450/400...), quartile ve
   dergi kirilimlari; quartile x ay pivotu.
4. **Aylik / yillik**: donem serisi ve yil toplamlari, kisi filtresiyle.
5. **Kayitlar**: ham satirlar, arama, secili donemi silme.

Her sekmedeki tablo "Excel'e aktar" ile bicimli bir rapora yazilir.

## Dosyalar

| Dosya | Icerik |
|---|---|
| `core.py` | Excel ayristirma, para birimi cozumu, SQLite depo, ozet/pivot sorgulari |
| `app.py` | tkinter arayuzu |
| `ornek_veri.py` | ayni duzende ornek ay dosyasi ureteci |
| `test_core.py` | cekirdek testleri (`python test_core.py`) |

Veritabani varsayilan olarak ev dizininde `yayin_takip.db`; ust bardan
degistirilebilir, yedek almak icin bu dosyayi kopyalamak yeterli.
