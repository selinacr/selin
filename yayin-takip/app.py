"""Adjunct Yayin Takip - masaustu panel.

Calistirma:  python app.py   (ya da masaustundeki "Yayin Takip" kisayolu)

Tek ekran: ustte donem ozeti, altinda filtre dugmeleri ve secilen gorunumun
tablosu. Yeni ay dosyasi alt bardaki dugmeden yuklenir.
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import arayuz
import core
from arayuz import RENK

TUM = "Tümü"

OLCU_ETIKETLERI = [
    ("tutar", "Ödeme tutarı"),
    ("usd_karsiligi", "USD karşılığı"),
    ("onayli", "Onaylı yayın"),
    ("yayin", "Tüm kayıtlar"),
]

GORUNUMLER = [
    ("kisi", "Kişi × ay"),
    ("quartile", "Quartile × ay"),
    ("dergi", "Dergi"),
    ("odeme", "Ödeme dağılımı"),
    ("kayitlar", "Kayıtlar"),
]


def bicim(deger):
    """Sayilari 1.234 / 1.234,5 bicimine cevirir; sifir yerine nokta koyar."""
    if deger is None or deger == "":
        return ""
    if isinstance(deger, bool):
        return str(deger)
    if isinstance(deger, (int, float)):
        if float(deger) == 0:
            return "·"
        metin = f"{float(deger):,.2f}".rstrip("0").rstrip(".")
        return metin.replace(",", "#").replace(".", ",").replace("#", ".")
    return str(deger)


class Uygulama(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Adjunct Yayın Takip")
        self.geometry("1320x820")
        self.minsize(1040, 660)
        self.stil = arayuz.stil_kur(self)

        self.db = core.Veritabani(core.VARSAYILAN_DB)
        self.yil = tk.StringVar(value=TUM)
        self.olcu = tk.StringVar(value="tutar")
        self.para = tk.StringVar(value="USD")
        self.gorunum = tk.StringVar(value="kisi")
        self.arama = tk.StringVar()
        self.sadece_onayli = tk.BooleanVar(value=False)
        self._tablo_verisi = ([], [])

        self._baslik_alani()
        self._filtre_alani()
        self._alt_bar()          # once paketlenir ki tablo buyurken kaybolmasin
        self._tablo_alani()
        self.protocol("WM_DELETE_WINDOW", self._kapat)
        self.yenile()

    # ------------------------------------------------------------------ #
    # Ust bolum: baslik + ozet kutulari
    # ------------------------------------------------------------------ #

    def _baslik_alani(self):
        cerceve = ttk.Frame(self)
        cerceve.pack(fill="x", padx=22, pady=(18, 6))
        sol = ttk.Frame(cerceve)
        sol.pack(side="left", anchor="w")
        ttk.Label(sol, text="Adjunct Yayın Takip Paneli", style="Baslik.TLabel").pack(anchor="w")
        self.alt_baslik = ttk.Label(sol, text="", style="AltBaslik.TLabel")
        self.alt_baslik.pack(anchor="w", pady=(2, 0))

        self.kutu_alani = ttk.Frame(cerceve)
        self.kutu_alani.pack(side="right", anchor="e")
        self.ozet_kutulari = {}

    def _ozet_kutulari_ciz(self, degerler):
        """degerler: [(sayi, etiket), ...] - kutu sayisi veriye gore degisir."""
        for cocuk in self.kutu_alani.winfo_children():
            cocuk.destroy()
        for sayi, etiket in degerler:
            kart = ttk.Frame(self.kutu_alani, style="Kart.TFrame", padding=(16, 10))
            kart.pack(side="left", padx=(10, 0))
            ttk.Label(kart, text=sayi, style="Sayi.TLabel").pack(anchor="e")
            ttk.Label(kart, text=etiket, style="SayiEtiket.TLabel").pack(anchor="e")

    # ------------------------------------------------------------------ #
    # Filtreler
    # ------------------------------------------------------------------ #

    def _chip_grubu(self, ana, degisken, secenekler, komut=None):
        kutu = ttk.Frame(ana, style="Kart.TFrame", padding=2)
        for deger, etiket in secenekler:
            ttk.Radiobutton(kutu, text=etiket, value=deger, variable=degisken,
                            style="Chip.Toolbutton",
                            command=komut or self.yenile).pack(side="left", padx=1)
        return kutu

    def _filtre_alani(self):
        ust = ttk.Frame(self)
        ust.pack(fill="x", padx=22, pady=(10, 4))
        self.yil_kutusu = ttk.Frame(ust)
        self.yil_kutusu.pack(side="left")
        self._chip_grubu(ust, self.olcu, OLCU_ETIKETLERI).pack(side="left", padx=(10, 0))
        self.para_kutusu = ttk.Frame(ust)
        self.para_kutusu.pack(side="left", padx=(10, 0))
        ttk.Button(ust, text="Excel'e aktar", command=self.disa_aktar).pack(side="right")

        alt = ttk.Frame(self)
        alt.pack(fill="x", padx=22, pady=(6, 10))
        self._chip_grubu(alt, self.gorunum, GORUNUMLER).pack(side="left")
        ttk.Checkbutton(alt, text="Sadece ödemesi olanlar", variable=self.sadece_onayli,
                        command=self.yenile).pack(side="left", padx=12)
        giris = ttk.Entry(alt, textvariable=self.arama, width=26)
        giris.pack(side="right")
        giris.bind("<Return>", lambda e: self.yenile())
        ttk.Label(alt, text="Ara:").pack(side="right", padx=(0, 6))

    def _yil_chipleri(self):
        for cocuk in self.yil_kutusu.winfo_children():
            cocuk.destroy()
        yillar = [(TUM, TUM)] + [(str(y), str(y)) for y in sorted(self.db.yillar())]
        if self.yil.get() not in [d for d, _ in yillar]:
            self.yil.set(TUM)
        self._chip_grubu(self.yil_kutusu, self.yil, yillar).pack()

    def _para_chipleri(self):
        for cocuk in self.para_kutusu.winfo_children():
            cocuk.destroy()
        birimler = self.db.kullanilan_para_birimleri() or ["USD"]
        secenekler = [(TUM, TUM)] + [(b, b) for b in birimler]
        if self.para.get() not in [d for d, _ in secenekler]:
            self.para.set(birimler[0])
        grup = self._chip_grubu(self.para_kutusu, self.para, secenekler)
        grup.pack()
        # Para birimi yalnizca tutar olculerinde anlamli
        durum = "normal" if self.olcu.get() in ("tutar",) else "disabled"
        for cocuk in grup.winfo_children():
            cocuk.configure(state=durum)

    # ------------------------------------------------------------------ #
    # Tablo
    # ------------------------------------------------------------------ #

    def _tablo_alani(self):
        kutu, self.tablo = arayuz.tablo_olustur(self, yukseklik=16)
        kutu.pack(fill="both", expand=True, padx=22, pady=(0, 8))
        self.tablo.bind("<Double-1>", self.satir_detayi)
        self.aciklama = ttk.Label(self, text="", style="Ipucu.TLabel")
        self.aciklama.pack(side="bottom", anchor="w", padx=24, pady=(0, 4))

    # ------------------------------------------------------------------ #
    # Alt bar
    # ------------------------------------------------------------------ #

    def _alt_bar(self):
        cerceve = ttk.Frame(self, style="Kart.TFrame", padding=(16, 12))
        cerceve.pack(side="bottom", fill="x", padx=22, pady=(8, 16))
        ttk.Button(cerceve, text="Yeni ay dosyası yükle", style="Ana.TButton",
                   command=self.ice_aktar_penceresi).pack(side="left")
        ttk.Label(cerceve, style="Kart.TLabel", foreground=RENK["soluk"],
                  text="Aynı aya ait dosya tekrar yüklenirse o ayın verisi güncellenir.").pack(
            side="left", padx=12)
        self.durum = ttk.Label(cerceve, text="", style="Durum.TLabel",
                               background=RENK["kart"])
        self.durum.pack(side="right")
        ttk.Button(cerceve, text="Veritabanı...", command=self.db_degistir).pack(
            side="right", padx=8)

    def bilgi(self, metin):
        self.durum.config(text=metin)
        self.after(8000, lambda: self.durum.config(text=""))

    def db_degistir(self):
        yol = filedialog.asksaveasfilename(
            title="Veritabanı dosyası", defaultextension=".db",
            filetypes=[("SQLite", "*.db"), ("Tümü", "*.*")],
            initialfile=os.path.basename(self.db.yol))
        if not yol:
            return
        self.db.kapat()
        self.db = core.Veritabani(yol)
        self.yenile()
        self.bilgi(os.path.basename(yol))

    def _kapat(self):
        try:
            self.db.kapat()
        finally:
            self.destroy()

    # ------------------------------------------------------------------ #
    # Veri
    # ------------------------------------------------------------------ #

    def _filtre(self, para_dahil=True) -> dict:
        yil = self.yil.get()
        para = self.para.get()
        filtre = {
            "yil": int(yil) if yil != TUM else None,
            "sadece_onayli": bool(self.sadece_onayli.get()),
            "arama": self.arama.get().strip() or None,
        }
        if para_dahil and para != TUM and self.olcu.get() == "tutar":
            filtre["para_birimi"] = para
        return filtre

    def yenile(self):
        try:
            self._yil_chipleri()
            self._para_chipleri()
            self._ozeti_ciz()
            self._tabloyu_ciz()
        except Exception:
            traceback.print_exc()

    def _ozeti_ciz(self):
        filtre = self._filtre(para_dahil=False)
        ozet = self.db.genel_ozet(**filtre)
        donemler = self.db.donemler()
        if donemler:
            aralik = (f"{core.donem_etiketi(*donemler[0])} – {core.donem_etiketi(*donemler[-1])}"
                      f" · {ozet['kayit']} kayit · {ozet['kisi_sayisi']} kisi")
        else:
            aralik = "Henüz veri yok — alttaki düğmeden ilk ay dosyasını yükleyin."
        self.alt_baslik.config(text=aralik)
        kutular = [(str(ozet["onayli"]), "onaylı yayın")]
        for birim, tutar in list(ozet["para"].items())[:3]:
            kutular.append((bicim(tutar), birim))
        kutular.append((bicim(ozet["usd_karsiligi"]), "USD karşılığı"))
        self._ozet_kutulari_ciz(kutular)

    def _tabloyu_ciz(self):
        gorunum = self.gorunum.get()
        olcu = self.olcu.get()
        filtre = self._filtre()
        vurgulu, toplam_var = (), False

        if gorunum in ("kisi", "quartile"):
            yil = filtre.pop("yil")
            basliklar, satirlar, donem_sayisi = self.db.pivot(
                gorunum, olcu=olcu, yil=yil, **filtre)
            vurgulu = set(range(1 + donem_sayisi, len(basliklar)))
            satirlar = [[s[0]] + [bicim(x) for x in s[1:]] for s in satirlar] or []
            if satirlar:
                ham = self.db.pivot(gorunum, olcu=olcu, yil=yil, **filtre)[1]
                toplamlar = [sum(s[i] for s in ham) for i in range(1, len(basliklar))]
                satirlar.append(["Toplam"] + [bicim(t) for t in toplamlar])
                toplam_var = True
            genis_ilk = 240
            aciklama = self._olcu_aciklamasi()
        elif gorunum in ("dergi", "odeme"):
            alan = "dergi" if gorunum == "dergi" else "tutar"
            veriler = self.db.kirilim(alan, **filtre)
            basliklar = ["Dergi" if alan == "dergi" else "Ödeme tutarı",
                         "Kayıt", "Ödemeli", "Kişi", "Toplam", "USD karşılığı"]
            satirlar = [[v["anahtar"], v["kayit"], v["onayli"], v["kisi_sayisi"],
                         bicim(v["tutar"]), bicim(v["usd_karsiligi"])] for v in veriler]
            genis_ilk = 320
            aciklama = ("Ödeme tutarı kırılımı: hangi standart tutardan kaç yayın ödenmiş."
                        if alan == "tutar" else "Dergi bazında yayın ve ödeme dağılımı.")
        else:
            veriler = self.db.kayitlar(limit=5000, **filtre)
            basliklar = ["Kişi", "Dönem", "Başlık", "Dergi", "Q", "Tarih",
                         "Kontrol notu", "Tutar", "Birim", "USD karşılığı", "DOI"]
            satirlar = [[k["kisi"], core.donem_etiketi(k["yil"], k["ay"]), k["baslik"],
                         k["dergi"], k["quartile"], k["tarih"], k["kontrol"],
                         bicim(k["tutar"]), k["para_birimi"], bicim(k["usd_karsiligi"]),
                         k["doi"]] for k in veriler]
            genis_ilk = 200
            aciklama = f"{len(satirlar)} kayıt listeleniyor (en fazla 5000)."

        arayuz.tabloyu_doldur(self.tablo, basliklar, satirlar, genis_ilk, vurgulu, toplam_var)
        if gorunum == "kayitlar":
            for i, baslik in enumerate(basliklar):
                if baslik in ("Başlık", "Dergi", "Kontrol notu", "DOI"):
                    self.tablo.column(str(i), width=230, anchor="w")
        self._tablo_verisi = (basliklar, satirlar)
        self.aciklama.config(text=aciklama)

    def _olcu_aciklamasi(self) -> str:
        etiket = dict(OLCU_ETIKETLERI)[self.olcu.get()]
        if self.olcu.get() == "tutar":
            birim = self.para.get()
            return (f"{etiket} ({birim if birim != TUM else 'tüm birimler'}). "
                    "Para birimi Kontrol notundan belirlenir; kişiye çift tıklayarak "
                    "kural tanımlayabilirsin.")
        if self.olcu.get() == "usd_karsiligi":
            return ("USD karşılığı: EUR/CNY ödemelerin dosyadaki paritesinden hesaplanan "
                    "standart USD tutarı. Birimleri tek toplamda karşılaştırmak için.")
        return f"{etiket} sayısı."

    def disa_aktar(self):
        basliklar, satirlar = self._tablo_verisi
        if not satirlar:
            messagebox.showinfo("Boş", "Aktarılacak veri yok.")
            return
        yol = filedialog.asksaveasfilename(
            title="Excel olarak kaydet", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"yayin_raporu_{datetime.now():%Y%m%d_%H%M}.xlsx")
        if not yol:
            return
        core.excel_yaz(yol, basliklar, satirlar, self.gorunum.get()[:31],
                       range(1, len(basliklar)),
                       f"{dict(GORUNUMLER)[self.gorunum.get()]} - "
                       f"{dict(OLCU_ETIKETLERI)[self.olcu.get()]} "
                       f"({datetime.now():%d.%m.%Y %H:%M})")
        self.bilgi(f"Kaydedildi: {os.path.basename(yol)}")

    def satir_detayi(self, _olay=None):
        if self.gorunum.get() != "kisi":
            return
        secim = self.tablo.selection()
        if not secim:
            return
        kisi = self.tablo.item(secim[0])["values"][0]
        if kisi == "Toplam":
            return
        KisiPenceresi(self, str(kisi))

    def ice_aktar_penceresi(self):
        IceAktarPenceresi(self)


# --------------------------------------------------------------------------- #
# Ice aktarma penceresi
# --------------------------------------------------------------------------- #

class IceAktarPenceresi(tk.Toplevel):
    def __init__(self, ana: Uygulama):
        super().__init__(ana)
        self.ana = ana
        self.title("Yeni ay dosyası yükle")
        self.geometry("1080x680")
        self.configure(background=RENK["zemin"])
        self.transient(ana)
        self.dosya = tk.StringVar()
        self.sayfa = tk.StringVar()
        self.ay = tk.StringVar()
        self.yil = tk.StringVar()
        self.uzerine_yaz = tk.BooleanVar(value=True)
        self._yayinlar = []

        ust = ttk.Frame(self, padding=(16, 14))
        ust.pack(fill="x")
        ttk.Button(ust, text="Excel seç...", style="Ana.TButton",
                   command=self.dosya_sec).pack(side="left")
        self.dosya_etiketi = ttk.Label(ust, text="", style="AltBaslik.TLabel")
        self.dosya_etiketi.pack(side="left", padx=12)

        secim = ttk.Frame(self, padding=(16, 0))
        secim.pack(fill="x")
        ttk.Label(secim, text="Sayfa:").pack(side="left")
        self.sayfa_kutusu = ttk.Combobox(secim, textvariable=self.sayfa, state="readonly",
                                         width=18)
        self.sayfa_kutusu.pack(side="left", padx=(4, 14))
        self.sayfa_kutusu.bind("<<ComboboxSelected>>", lambda e: self.coz())
        ttk.Label(secim, text="Dönem:").pack(side="left")
        ttk.Combobox(secim, textvariable=self.ay, state="readonly", width=11,
                     values=core.AY_ADLARI).pack(side="left", padx=4)
        ttk.Combobox(secim, textvariable=self.yil, state="readonly", width=7,
                     values=[str(y) for y in range(2020, 2041)]).pack(side="left")
        ttk.Button(secim, text="Yeniden çöz", command=self.coz).pack(side="left", padx=10)
        ttk.Checkbutton(secim, text="Bu ay zaten varsa üzerine yaz",
                        variable=self.uzerine_yaz).pack(side="left", padx=10)

        self.ozet = ttk.Label(self, text="Dosya seçilmedi.", style="Bolum.TLabel")
        self.ozet.pack(anchor="w", padx=16, pady=(12, 4))
        kutu, self.onizleme = arayuz.tablo_olustur(self, yukseklik=13)
        kutu.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        alt = ttk.Frame(self, padding=(16, 12))
        alt.pack(side="bottom", fill="x")
        ttk.Button(alt, text="Veritabanına aktar", style="Ana.TButton",
                   command=self.aktar).pack(side="right")
        ttk.Button(alt, text="Kapat", command=self.destroy).pack(side="right", padx=8)
        self.gunluk = tk.Text(self, height=5, wrap="word", relief="flat",
                              background=RENK["kart"], foreground=RENK["yazi"])
        self.gunluk.pack(side="bottom", fill="x", padx=16)

    def yaz(self, metin):
        self.gunluk.insert("end", metin + "\n")
        self.gunluk.see("end")

    def dosya_sec(self):
        yol = filedialog.askopenfilename(
            title="Ayın yayın dosyası",
            filetypes=[("Excel", "*.xlsx *.xlsm *.xltx"), ("Tümü", "*.*")])
        if not yol:
            return
        self.dosya.set(yol)
        self.dosya_etiketi.config(text=os.path.basename(yol))
        try:
            sayfalar = core.sayfa_adlari(yol)
        except Exception as hata:
            messagebox.showerror("Hata", f"Dosya açılamadı:\n{hata}", parent=self)
            return
        self.sayfa_kutusu["values"] = sayfalar
        self.sayfa.set(sayfalar[0] if sayfalar else "")
        self.ay.set("")
        self.yil.set("")
        self.coz()

    def _donem(self):
        if self.ay.get() in core.AY_ADLARI and self.yil.get().isdigit():
            return int(self.yil.get()), core.AY_ADLARI.index(self.ay.get()) + 1
        return None

    def coz(self):
        if not self.dosya.get():
            return
        try:
            donem, yayinlar, _, uyarilar = core.dosyayi_ayristir(
                self.dosya.get(), self.sayfa.get() or None, self._donem(),
                self.ana.db.kurallar())
        except Exception as hata:
            self.yaz(f"HATA: {hata}")
            messagebox.showerror("Çözümlenemedi", str(hata), parent=self)
            return
        yil, ay = donem
        self.ay.set(core.AY_ADLARI[ay - 1])
        self.yil.set(str(yil))
        self._yayinlar = yayinlar
        arayuz.tabloyu_doldur(
            self.onizleme,
            ["Kişi", "Sıra", "Başlık", "Dergi", "Q", "Tarih", "Kontrol notu",
             "Tutar", "Birim", "USD karşılığı"],
            [[y.kisi, y.sira, y.baslik, y.dergi, y.quartile, y.tarih, y.kontrol,
              bicim(y.tutar), y.para_birimi, bicim(y.usd_karsiligi)] for y in yayinlar],
            genis_ilk=190)
        for i in (2, 3, 6):
            self.onizleme.column(str(i), width=240, anchor="w")
        toplamlar = {}
        for y in yayinlar:
            if y.tutar:
                toplamlar[y.para_birimi] = toplamlar.get(y.para_birimi, 0) + y.tutar
        para = "  ".join(f"{bicim(v)} {b}" for b, v in sorted(toplamlar.items()))
        self.ozet.config(
            text=f"{core.donem_etiketi(yil, ay)} · {len(yayinlar)} kayit · "
                 f"{sum(y.onayli for y in yayinlar)} ödemeli · "
                 f"{len({y.kisi for y in yayinlar})} kişi · {para}")
        self.yaz(f"{os.path.basename(self.dosya.get())} çözüldü.")
        for uyari in uyarilar:
            self.yaz("  ! " + uyari)

    def aktar(self):
        if not self._yayinlar:
            messagebox.showinfo("Bilgi", "Önce bir dosya seçin.", parent=self)
            return
        donem = self._donem()
        if not donem:
            messagebox.showerror("Dönem", "Ay ve yıl seçilmeli.", parent=self)
            return
        yil, ay = donem
        for yayin in self._yayinlar:
            yayin.yil, yayin.ay = yil, ay
        sonuc = self.ana.db.aktar(self._yayinlar, yil, ay, self.dosya.get(),
                                  self.sayfa.get(), self.uzerine_yaz.get())
        self.yaz(f"{core.donem_etiketi(yil, ay)}: {sonuc['eklenen']} kayıt yazıldı, "
                 f"{sonuc['silinen']} eski kayıt silindi, {sonuc['atlanan']} atlandı.")
        self.ana.yenile()
        self.ana.bilgi(f"{core.donem_etiketi(yil, ay)} güncellendi.")


# --------------------------------------------------------------------------- #
# Kisi detay penceresi
# --------------------------------------------------------------------------- #

class KisiPenceresi(tk.Toplevel):
    def __init__(self, ana: Uygulama, kisi: str):
        super().__init__(ana)
        self.ana = ana
        self.kisi = kisi
        self.title(kisi)
        self.geometry("860x620")
        self.configure(background=RENK["zemin"])
        self.transient(ana)

        ttk.Label(self, text=kisi, style="Baslik.TLabel").pack(anchor="w", padx=16, pady=(16, 2))
        yillik, aylik = ana.db.kisi_detay(kisi)
        toplam = {}
        for satir in aylik:
            if satir["tutar"]:
                toplam[satir["para_birimi"]] = toplam.get(satir["para_birimi"], 0) + satir["tutar"]
        ttk.Label(self, style="AltBaslik.TLabel",
                  text=f"{sum(y['kayit'] for y in yillik)} kayıt · "
                       f"{sum(y['onayli'] for y in yillik)} ödemeli · "
                       + "  ".join(f"{bicim(v)} {b}" for b, v in sorted(toplam.items()))
                  ).pack(anchor="w", padx=16)

        alt = ttk.Frame(self, style="Kart.TFrame", padding=(14, 12))
        alt.pack(side="bottom", fill="x", padx=16, pady=14)
        ttk.Label(alt, style="Kart.TLabel",
                  text="Bu kişinin ödemeleri her zaman:").pack(side="left")
        self.kural = ttk.Combobox(alt, state="readonly", width=8,
                                  values=["(kural yok)"] + core.PARA_BIRIMLERI)
        self.kural.set(ana.db.kurallar().get(core.temiz_ad(kisi), "(kural yok)"))
        self.kural.pack(side="left", padx=8)
        ttk.Button(alt, text="Kaydet", command=self.kural_kaydet).pack(side="left")
        ttk.Button(alt, text="Kapat", command=self.destroy).pack(side="right")

        ttk.Label(self, text="Yıllık", style="Bolum.TLabel").pack(anchor="w", padx=16, pady=(14, 4))
        kutu1, tablo1 = arayuz.tablo_olustur(self, yukseklik=5)
        kutu1.pack(fill="both", expand=True, padx=16)
        arayuz.tabloyu_doldur(tablo1, ["Yıl", "Kayıt", "Ödemeli", "USD karşılığı"],
                              [[y["yil"], y["kayit"], y["onayli"], bicim(y["usd_karsiligi"])]
                               for y in yillik], genis_ilk=110)

        ttk.Label(self, text="Aylık", style="Bolum.TLabel").pack(anchor="w", padx=16, pady=(14, 4))
        kutu2, tablo2 = arayuz.tablo_olustur(self, yukseklik=9)
        kutu2.pack(fill="both", expand=True, padx=16)
        arayuz.tabloyu_doldur(
            tablo2, ["Dönem", "Birim", "Tutar", "Kayıt", "Ödemeli"],
            [[core.donem_etiketi(a["yil"], a["ay"]), a["para_birimi"], bicim(a["tutar"]),
              a["kayit"], a["onayli"]] for a in aylik], genis_ilk=150)

    def kural_kaydet(self):
        secim = self.kural.get()
        birim = None if secim == "(kural yok)" else secim
        self.ana.db.kural_kaydet(self.kisi, birim)
        if birim and messagebox.askyesno(
                "Geçmiş kayıtlar", "Mevcut kayıtların para birimi de güncellensin mi?",
                parent=self):
            adet = self.ana.db.kural_uygula(core.temiz_ad(self.kisi), birim)
            self.ana.bilgi(f"{adet} kayıt güncellendi.")
        self.ana.yenile()
        self.destroy()


def main():
    Uygulama().mainloop()


if __name__ == "__main__":
    main()
