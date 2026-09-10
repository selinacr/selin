"""Adjunct Yayin Takip - masaustu arayuz (tkinter).

Calistirma:  python app.py
Her ay gelen "... Yayinlari" Excel dosyasi ice aktarilir; kisi bazinda ve
odeme bazinda aylik/yillik raporlar guncel tutulur.
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import core

TUM = "(Tumu)"


def bicim(deger):
    """Sayilari 1.234 / 1.234,5 bicimine cevirir."""
    if deger is None or deger == "":
        return ""
    if isinstance(deger, (int, float)):
        if float(deger) == 0:
            return "·"
        metin = f"{float(deger):,.2f}".rstrip("0").rstrip(".")
        return metin.replace(",", "#").replace(".", ",").replace("#", ".")
    return str(deger)


class Uygulama(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Adjunct Yayin Takip")
        self.geometry("1240x780")
        self.minsize(960, 620)

        self.db = core.Veritabani(core.VARSAYILAN_DB)
        self.dosya_yolu = tk.StringVar()
        self.sayfa_secimi = tk.StringVar()
        self.donem_yil = tk.StringVar()
        self.donem_ay = tk.StringVar()
        self.donemi_degistir = tk.BooleanVar(value=True)
        self._cozulen = []

        self._ust_bar()
        self.defter = ttk.Notebook(self)
        self.defter.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._sekme_aktar()
        self._sekme_kisi()
        self._sekme_odeme()
        self._sekme_donem()
        self._sekme_kayitlar()
        self.protocol("WM_DELETE_WINDOW", self._kapat)
        self.yenile()

    # ------------------------------------------------------------------ #
    # Ortak parcalar
    # ------------------------------------------------------------------ #

    def _ust_bar(self):
        cerceve = ttk.Frame(self)
        cerceve.pack(fill="x", padx=8, pady=6)
        ttk.Label(cerceve, text="Veritabani:").pack(side="left")
        self.db_etiketi = ttk.Label(cerceve, text=self.db.yol, foreground="#26496b")
        self.db_etiketi.pack(side="left", padx=(4, 10))
        ttk.Button(cerceve, text="Degistir...", command=self.db_degistir).pack(side="left")
        self.durum = ttk.Label(cerceve, text="", foreground="#2f6b2f")
        self.durum.pack(side="right")

    def _tablo(self, ana, yukseklik=18):
        kutu = ttk.Frame(ana)
        agac = ttk.Treeview(kutu, columns=("bos",), show="headings", height=yukseklik)
        dikey = ttk.Scrollbar(kutu, orient="vertical", command=agac.yview)
        yatay = ttk.Scrollbar(kutu, orient="horizontal", command=agac.xview)
        agac.configure(yscrollcommand=dikey.set, xscrollcommand=yatay.set)
        agac.grid(row=0, column=0, sticky="nsew")
        dikey.grid(row=0, column=1, sticky="ns")
        yatay.grid(row=1, column=0, sticky="ew")
        kutu.rowconfigure(0, weight=1)
        kutu.columnconfigure(0, weight=1)
        return kutu, agac

    @staticmethod
    def doldur(agac, basliklar, satirlar, genis_ilk=240):
        agac.delete(*agac.get_children())
        agac["columns"] = [str(i) for i in range(len(basliklar))]
        for i, baslik in enumerate(basliklar):
            agac.heading(str(i), text=baslik)
            agac.column(str(i), width=110, anchor="e", stretch=True)
        if basliklar:
            agac.column("0", width=genis_ilk, anchor="w")
        for satir in satirlar:
            agac.insert("", "end", values=[bicim(h) for h in satir])

    def bilgi(self, metin):
        self.durum.config(text=metin)
        self.after(7000, lambda: self.durum.config(text=""))

    def db_degistir(self):
        yol = filedialog.asksaveasfilename(
            title="Veritabani dosyasi", defaultextension=".db",
            filetypes=[("SQLite", "*.db"), ("Tumu", "*.*")],
            initialfile=os.path.basename(self.db.yol))
        if not yol:
            return
        self.db.kapat()
        self.db = core.Veritabani(yol)
        self.db_etiketi.config(text=yol)
        self.yenile()

    def _kapat(self):
        try:
            self.db.kapat()
        finally:
            self.destroy()

    def _disa_aktar(self, basliklar, satirlar, ad, not_metni=""):
        if not satirlar:
            messagebox.showinfo("Bos", "Aktarilacak veri yok.")
            return
        yol = filedialog.asksaveasfilename(
            title="Excel olarak kaydet", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"{ad}_{datetime.now():%Y%m%d_%H%M}.xlsx")
        if not yol:
            return
        core.excel_yaz(yol, basliklar, satirlar, ad[:31],
                       range(1, len(basliklar)), not_metni)
        self.bilgi(f"Kaydedildi: {os.path.basename(yol)}")

    def _filtre_cubugu(self, ana, komut, arama=False, olcu=False, onayli=True):
        """Yil / ay / para birimi / olcu filtreleri. Degiskenleri sozluk olarak doner."""
        cerceve = ttk.Frame(ana)
        cerceve.pack(fill="x", padx=8, pady=6)
        alanlar = {}
        ttk.Label(cerceve, text="Yil:").pack(side="left")
        alanlar["yil"] = ttk.Combobox(cerceve, state="readonly", width=8, values=[TUM])
        alanlar["yil"].set(TUM)
        alanlar["yil"].pack(side="left", padx=(2, 8))
        ttk.Label(cerceve, text="Ay:").pack(side="left")
        alanlar["ay"] = ttk.Combobox(cerceve, state="readonly", width=11,
                                     values=[TUM] + core.AY_ADLARI)
        alanlar["ay"].set(TUM)
        alanlar["ay"].pack(side="left", padx=(2, 8))
        ttk.Label(cerceve, text="Para birimi:").pack(side="left")
        alanlar["para"] = ttk.Combobox(cerceve, state="readonly", width=8, values=[TUM])
        alanlar["para"].set(TUM)
        alanlar["para"].pack(side="left", padx=(2, 8))
        if olcu:
            ttk.Label(cerceve, text="Olcu:").pack(side="left")
            alanlar["olcu"] = ttk.Combobox(cerceve, state="readonly", width=20,
                                           values=list(core.OLCULER.values()))
            alanlar["olcu"].set(core.OLCULER["tutar"])
            alanlar["olcu"].pack(side="left", padx=(2, 8))
            alanlar["olcu"].bind("<<ComboboxSelected>>", lambda e: komut())
        if onayli:
            alanlar["onayli"] = tk.BooleanVar(value=False)
            ttk.Checkbutton(cerceve, text="Sadece odemesi olanlar",
                            variable=alanlar["onayli"], command=komut).pack(side="left", padx=6)
        if arama:
            alanlar["arama"] = tk.StringVar()
            ttk.Label(cerceve, text="Ara:").pack(side="left")
            giris = ttk.Entry(cerceve, textvariable=alanlar["arama"], width=20)
            giris.pack(side="left", padx=2)
            giris.bind("<Return>", lambda e: komut())
        ttk.Button(cerceve, text="Uygula", command=komut).pack(side="left", padx=6)
        for anahtar in ("yil", "ay", "para"):
            alanlar[anahtar].bind("<<ComboboxSelected>>", lambda e: komut())
        alanlar["_cerceve"] = cerceve
        return alanlar

    @staticmethod
    def _filtre(alanlar) -> dict:
        yil = alanlar["yil"].get()
        ay = alanlar["ay"].get()
        para = alanlar["para"].get()
        filtre = {
            "yil": int(yil) if yil and yil != TUM else None,
            "ay": core.AY_ADLARI.index(ay) + 1 if ay and ay != TUM else None,
            "para_birimi": para if para and para != TUM else None,
        }
        if "onayli" in alanlar:
            filtre["sadece_onayli"] = bool(alanlar["onayli"].get())
        if "arama" in alanlar:
            filtre["arama"] = alanlar["arama"].get().strip() or None
        return filtre

    @staticmethod
    def _olcu_anahtari(alanlar) -> str:
        secim = alanlar["olcu"].get() if "olcu" in alanlar else core.OLCULER["tutar"]
        for anahtar, etiket in core.OLCULER.items():
            if etiket == secim:
                return anahtar
        return "tutar"

    # ------------------------------------------------------------------ #
    # 1) Ice aktarma
    # ------------------------------------------------------------------ #

    def _sekme_aktar(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="1) Ayin Excel'ini yukle")

        ust = ttk.LabelFrame(sekme, text="Dosya ve donem")
        ust.pack(fill="x", padx=8, pady=6)
        ttk.Button(ust, text="Excel sec...", command=self.dosya_sec).grid(
            row=0, column=0, padx=6, pady=6)
        ttk.Label(ust, textvariable=self.dosya_yolu, foreground="#26496b").grid(
            row=0, column=1, columnspan=6, sticky="w")
        ttk.Label(ust, text="Sayfa:").grid(row=1, column=0, sticky="e", padx=6)
        self.sayfa_kutusu = ttk.Combobox(ust, textvariable=self.sayfa_secimi,
                                         state="readonly", width=22)
        self.sayfa_kutusu.grid(row=1, column=1, sticky="w")
        self.sayfa_kutusu.bind("<<ComboboxSelected>>", lambda e: self.dosyayi_coz())
        ttk.Label(ust, text="Donem:").grid(row=1, column=2, sticky="e", padx=6)
        self.ay_kutusu = ttk.Combobox(ust, textvariable=self.donem_ay, state="readonly",
                                      width=11, values=core.AY_ADLARI)
        self.ay_kutusu.grid(row=1, column=3, sticky="w")
        self.yil_kutusu = ttk.Combobox(ust, textvariable=self.donem_yil, state="readonly",
                                       width=7,
                                       values=[str(y) for y in range(2020, 2041)])
        self.yil_kutusu.grid(row=1, column=4, sticky="w", padx=4)
        ttk.Checkbutton(ust, text="Bu donem daha once yuklendiyse uzerine yaz",
                        variable=self.donemi_degistir).grid(row=1, column=5, padx=10)
        ttk.Button(ust, text="Yeniden coz", command=self.dosyayi_coz).grid(row=1, column=6, padx=6)

        orta = ttk.LabelFrame(sekme, text="Onizleme")
        orta.pack(fill="both", expand=True, padx=8, pady=6)
        dugmeler = ttk.Frame(orta)
        dugmeler.pack(fill="x")
        self.onizleme_ozeti = ttk.Label(dugmeler, text="Henuz dosya secilmedi.",
                                        font=("", 10, "bold"))
        self.onizleme_ozeti.pack(side="left", padx=6, pady=4)
        ttk.Button(dugmeler, text="Veritabanina aktar", command=self.aktar).pack(
            side="right", padx=6, pady=4)
        kutu, self.onizleme = self._tablo(orta, yukseklik=12)
        kutu.pack(fill="both", expand=True, padx=4, pady=4)

        self.gunluk = tk.Text(sekme, height=8, wrap="word")
        self.gunluk.pack(fill="x", padx=8, pady=(0, 8))

    def _gunluk(self, metin):
        self.gunluk.insert("end", f"[{datetime.now():%H:%M:%S}] {metin}\n")
        self.gunluk.see("end")

    def dosya_sec(self):
        yol = filedialog.askopenfilename(
            title="Ayin yayin dosyasi",
            filetypes=[("Excel", "*.xlsx *.xlsm *.xltx"), ("Tumu", "*.*")])
        if not yol:
            return
        self.dosya_yolu.set(yol)
        try:
            sayfalar = core.sayfa_adlari(yol)
        except Exception as hata:
            messagebox.showerror("Hata", f"Dosya acilamadi:\n{hata}")
            return
        self.sayfa_kutusu["values"] = sayfalar
        self.sayfa_secimi.set(sayfalar[0] if sayfalar else "")
        self.donem_ay.set("")
        self.donem_yil.set("")
        self.dosyayi_coz()

    def _secili_donem(self):
        ay, yil = self.donem_ay.get(), self.donem_yil.get()
        if ay in core.AY_ADLARI and yil.isdigit():
            return int(yil), core.AY_ADLARI.index(ay) + 1
        return None

    def dosyayi_coz(self):
        yol = self.dosya_yolu.get()
        if not yol:
            return
        try:
            donem, yayinlar, ozet, uyarilar = core.dosyayi_ayristir(
                yol, self.sayfa_secimi.get() or None, self._secili_donem(),
                self.db.kurallar())
        except Exception as hata:
            self._gunluk(f"HATA: {hata}")
            messagebox.showerror("Cozumlenemedi", str(hata))
            return
        yil, ay = donem
        self.donem_ay.set(core.AY_ADLARI[ay - 1])
        self.donem_yil.set(str(yil))
        self._cozulen = yayinlar

        basliklar = ["Kisi", "Sira", "Baslik", "Dergi", "Quartile", "Tarih",
                     "Kontrol notu", "Tutar", "Birim", "USD karsiligi"]
        satirlar = [[y.kisi, y.sira, y.baslik[:70], y.dergi[:40], y.quartile, y.tarih,
                     y.kontrol[:40], y.tutar, y.para_birimi, y.usd_karsiligi]
                    for y in yayinlar]
        self.doldur(self.onizleme, basliklar, satirlar, genis_ilk=190)

        toplamlar = {}
        for y in yayinlar:
            if y.tutar:
                toplamlar[y.para_birimi] = toplamlar.get(y.para_birimi, 0) + y.tutar
        onayli = sum(y.onayli for y in yayinlar)
        para_metni = "  ".join(f"{bicim(v)} {b}" for b, v in sorted(toplamlar.items()))
        self.onizleme_ozeti.config(
            text=f"{core.donem_etiketi(yil, ay)} · {len(yayinlar)} kayit · "
                 f"{onayli} odemeli · {len({y.kisi for y in yayinlar})} kisi · {para_metni}")
        self._gunluk(f"{os.path.basename(yol)} cozuldu: {core.donem_etiketi(yil, ay)}, "
                     f"{len(yayinlar)} kayit, {onayli} odemeli. {para_metni}")
        for uyari in uyarilar:
            self._gunluk("  ! " + uyari)

    def aktar(self):
        if not self._cozulen:
            messagebox.showinfo("Bilgi", "Once bir Excel dosyasi secin.")
            return
        donem = self._secili_donem()
        if not donem:
            messagebox.showerror("Donem", "Ay ve yil secilmeli.")
            return
        yil, ay = donem
        for yayin in self._cozulen:
            yayin.yil, yayin.ay = yil, ay
        mevcut = self.db.genel_ozet(yil=yil, ay=ay)["kayit"]
        if mevcut and not self.donemi_degistir.get():
            if not messagebox.askyesno(
                    "Uyari", f"{core.donem_etiketi(yil, ay)} icin zaten {mevcut} kayit var.\n"
                             "Uzerine yazma kapali; ayni kayitlar atlanacak. Devam?"):
                return
        sonuc = self.db.aktar(self._cozulen, yil, ay, self.dosya_yolu.get(),
                              self.sayfa_secimi.get(), self.donemi_degistir.get())
        self._gunluk(f"{core.donem_etiketi(yil, ay)} aktarildi - eklenen: {sonuc['eklenen']}, "
                     f"silinen (eski): {sonuc['silinen']}, atlanan: {sonuc['atlanan']}")
        self.bilgi(f"{sonuc['eklenen']} kayit yazildi.")
        self.yenile()

    # ------------------------------------------------------------------ #
    # 2) Kisi bazinda
    # ------------------------------------------------------------------ #

    def _sekme_kisi(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="2) Kisi bazinda")
        self.kisi_filtre = self._filtre_cubugu(sekme, self.kisi_yenile, arama=True, olcu=True)
        self.kisi_gorunum = tk.StringVar(value="pivot")
        secim = ttk.Frame(sekme)
        secim.pack(fill="x", padx=8)
        ttk.Radiobutton(secim, text="Kisi x ay pivotu", variable=self.kisi_gorunum,
                        value="pivot", command=self.kisi_yenile).pack(side="left")
        ttk.Radiobutton(secim, text="Toplam ozet", variable=self.kisi_gorunum,
                        value="ozet", command=self.kisi_yenile).pack(side="left", padx=8)
        ttk.Button(secim, text="Excel'e aktar", command=self.kisi_disa).pack(side="right")
        ttk.Label(secim, text="(kisiye cift tikla: detay ve para birimi kurali)").pack(
            side="right", padx=10)
        kutu, self.kisi_tablo = self._tablo(sekme)
        kutu.pack(fill="both", expand=True, padx=8, pady=6)
        self.kisi_tablo.bind("<Double-1>", self.kisi_detay)
        self.kisi_toplam = ttk.Label(sekme, text="", font=("", 10, "bold"))
        self.kisi_toplam.pack(anchor="w", padx=12, pady=(0, 8))
        self._kisi_veri = ([], [])

    def kisi_yenile(self):
        filtre = self._filtre(self.kisi_filtre)
        if self.kisi_gorunum.get() == "pivot":
            olcu = self._olcu_anahtari(self.kisi_filtre)
            yil = filtre.pop("yil")
            basliklar, satirlar, _ = self.db.pivot("kisi", olcu=olcu, yil=yil, **filtre)
            filtre["yil"] = yil
        else:
            birimler, veriler = self.db.kisi_ozet(**filtre)
            basliklar = ["Kisi", "Kayit", "Odemeli"] + birimler + ["USD karsiligi"]
            satirlar = [[v["kisi"], v["kayit"], v["onayli"]] + [v[b] for b in birimler]
                        + [v["usd_karsiligi"]] for v in veriler]
        self.doldur(self.kisi_tablo, basliklar, satirlar)
        self._kisi_veri = (basliklar, satirlar)
        self.kisi_toplam.config(text=self._ozet_metni(filtre))

    def _ozet_metni(self, filtre):
        ozet = self.db.genel_ozet(**filtre)
        para = "  ".join(f"{bicim(v)} {b}" for b, v in ozet["para"].items() if v)
        return (f"{ozet['kisi_sayisi']} kisi | {ozet['kayit']} kayit | "
                f"{ozet['onayli']} odemeli | {para or 'odeme yok'}")

    def kisi_disa(self):
        basliklar, satirlar = self._kisi_veri
        self._disa_aktar(basliklar, satirlar, "kisi_bazinda",
                         f"Kisi bazinda rapor ({datetime.now():%d.%m.%Y %H:%M})")

    def kisi_detay(self, _olay=None):
        secim = self.kisi_tablo.selection()
        if not secim:
            return
        kisi = self.kisi_tablo.item(secim[0])["values"][0]
        yillik, aylik = self.db.kisi_detay(kisi)
        pencere = tk.Toplevel(self)
        pencere.title(f"{kisi}")
        pencere.geometry("780x560")
        ttk.Label(pencere, text=str(kisi), font=("", 12, "bold")).pack(anchor="w", padx=10, pady=8)

        ttk.Label(pencere, text="Yillik").pack(anchor="w", padx=10)
        kutu1, tablo1 = self._tablo(pencere, yukseklik=5)
        kutu1.pack(fill="both", expand=True, padx=10, pady=4)
        self.doldur(tablo1, ["Yil", "Kayit", "Odemeli", "USD karsiligi"],
                    [[y["yil"], y["kayit"], y["onayli"], y["usd_karsiligi"]] for y in yillik],
                    genis_ilk=90)

        ttk.Label(pencere, text="Aylik (para birimi kirilimli)").pack(anchor="w", padx=10)
        kutu2, tablo2 = self._tablo(pencere, yukseklik=9)
        kutu2.pack(fill="both", expand=True, padx=10, pady=4)
        self.doldur(tablo2, ["Donem", "Birim", "Tutar", "Kayit", "Odemeli"],
                    [[core.donem_etiketi(a["yil"], a["ay"]), a["para_birimi"], a["tutar"],
                      a["kayit"], a["onayli"]] for a in aylik], genis_ilk=140)

        alt = ttk.LabelFrame(pencere, text="Para birimi kurali")
        alt.pack(fill="x", padx=10, pady=8)
        ttk.Label(alt, text="Bu kisinin odemeleri her zaman:").pack(side="left", padx=6)
        kural = ttk.Combobox(alt, state="readonly", width=8,
                             values=[TUM] + core.PARA_BIRIMLERI)
        kural.set(self.db.kurallar().get(core.temiz_ad(kisi), TUM))
        kural.pack(side="left", padx=4)

        def kaydet():
            secilen = kural.get()
            birim = None if secilen == TUM else secilen
            self.db.kural_kaydet(kisi, birim)
            if birim and messagebox.askyesno(
                    "Gecmis kayitlar", "Mevcut kayitlarin para birimi de guncellensin mi?"):
                adet = self.db.kural_uygula(core.temiz_ad(kisi), birim)
                self.bilgi(f"{adet} kayit guncellendi.")
            self.yenile()
            pencere.destroy()

        ttk.Button(alt, text="Kaydet", command=kaydet).pack(side="left", padx=8)
        ttk.Button(pencere, text="Yillik ozeti Excel'e aktar",
                   command=lambda: self._disa_aktar(
                       ["Yil", "Kayit", "Odemeli", "USD karsiligi"],
                       [[y["yil"], y["kayit"], y["onayli"], y["usd_karsiligi"]] for y in yillik],
                       f"kisi_{core.sadelestir(kisi).replace(' ', '_')[:24]}",
                       f"{kisi} - yillik ozet")).pack(pady=6)

    # ------------------------------------------------------------------ #
    # 3) Odeme bazinda
    # ------------------------------------------------------------------ #

    def _sekme_odeme(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="3) Odeme bazinda")
        self.odeme_filtre = self._filtre_cubugu(sekme, self.odeme_yenile, arama=True, olcu=True)
        self.odeme_gorunum = tk.StringVar(value="para_birimi")
        secim = ttk.Frame(sekme)
        secim.pack(fill="x", padx=8)
        for etiket, deger in (("Para birimi", "para_birimi"), ("Odeme tutari", "tutar"),
                              ("Quartile", "quartile"), ("Dergi", "dergi"),
                              ("Quartile x ay pivotu", "pivot")):
            ttk.Radiobutton(secim, text=etiket, variable=self.odeme_gorunum, value=deger,
                            command=self.odeme_yenile).pack(side="left", padx=4)
        ttk.Button(secim, text="Excel'e aktar", command=self.odeme_disa).pack(side="right")
        kutu, self.odeme_tablo = self._tablo(sekme)
        kutu.pack(fill="both", expand=True, padx=8, pady=6)
        self.odeme_toplam = ttk.Label(sekme, text="", font=("", 10, "bold"))
        self.odeme_toplam.pack(anchor="w", padx=12, pady=(0, 8))
        self._odeme_veri = ([], [])

    def odeme_yenile(self):
        filtre = self._filtre(self.odeme_filtre)
        gorunum = self.odeme_gorunum.get()
        if gorunum == "pivot":
            olcu = self._olcu_anahtari(self.odeme_filtre)
            yil = filtre.pop("yil")
            basliklar, satirlar, _ = self.db.pivot("quartile", olcu=olcu, yil=yil, **filtre)
            filtre["yil"] = yil
        else:
            veriler = self.db.kirilim(gorunum, **filtre)
            etiket = {"para_birimi": "Para birimi", "tutar": "Odeme tutari",
                      "quartile": "Quartile", "dergi": "Dergi"}[gorunum]
            basliklar = [etiket, "Kayit", "Odemeli", "Kisi sayisi", "Toplam", "USD karsiligi"]
            satirlar = [[v["anahtar"], v["kayit"], v["onayli"], v["kisi_sayisi"],
                         v["tutar"], v["usd_karsiligi"]] for v in veriler]
        self.doldur(self.odeme_tablo, basliklar, satirlar)
        self._odeme_veri = (basliklar, satirlar)
        self.odeme_toplam.config(text=self._ozet_metni(filtre))

    def odeme_disa(self):
        basliklar, satirlar = self._odeme_veri
        self._disa_aktar(basliklar, satirlar, "odeme_bazinda",
                         f"Odeme bazinda rapor ({datetime.now():%d.%m.%Y %H:%M})")

    # ------------------------------------------------------------------ #
    # 4) Aylik / yillik
    # ------------------------------------------------------------------ #

    def _sekme_donem(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="4) Aylik / yillik")
        cerceve = ttk.Frame(sekme)
        cerceve.pack(fill="x", padx=8, pady=6)
        ttk.Label(cerceve, text="Kisi:").pack(side="left")
        self.donem_kisi = ttk.Combobox(cerceve, state="readonly", width=30, values=[TUM])
        self.donem_kisi.set(TUM)
        self.donem_kisi.pack(side="left", padx=4)
        self.donem_kisi.bind("<<ComboboxSelected>>", lambda e: self.donem_yenile())
        self.donem_onayli = tk.BooleanVar(value=False)
        ttk.Checkbutton(cerceve, text="Sadece odemesi olanlar", variable=self.donem_onayli,
                        command=self.donem_yenile).pack(side="left", padx=8)
        ttk.Button(cerceve, text="Yenile", command=self.donem_yenile).pack(side="left", padx=4)
        ttk.Button(cerceve, text="Excel'e aktar", command=self.donem_disa).pack(side="right")

        ttk.Label(sekme, text="Aylik").pack(anchor="w", padx=10)
        kutu1, self.donem_tablo = self._tablo(sekme, yukseklik=12)
        kutu1.pack(fill="both", expand=True, padx=8, pady=4)
        ttk.Label(sekme, text="Yillik").pack(anchor="w", padx=10)
        kutu2, self.yil_tablo = self._tablo(sekme, yukseklik=6)
        kutu2.pack(fill="both", expand=True, padx=8, pady=4)
        self._donem_veri = ([], [])

    def donem_yenile(self):
        kisi = self.donem_kisi.get()
        filtre = {"sadece_onayli": bool(self.donem_onayli.get())}
        if kisi and kisi != TUM:
            filtre["kisi"] = kisi
        birimler, aylik = self.db.donem_ozet(**filtre)
        basliklar = ["Donem", "Kisi", "Kayit", "Odemeli"] + birimler + ["USD karsiligi"]
        satirlar = [[core.donem_etiketi(a["yil"], a["ay"]), a["kisi_sayisi"], a["kayit"],
                     a["onayli"]] + [a[b] for b in birimler] + [a["usd_karsiligi"]]
                    for a in aylik]
        self.doldur(self.donem_tablo, basliklar, satirlar, genis_ilk=150)
        self._donem_veri = (basliklar, satirlar)

        yil_satirlari = []
        for yil in sorted({a["yil"] for a in aylik}, reverse=True):
            ozet = self.db.genel_ozet(yil=yil, **filtre)
            yil_satirlari.append([yil, ozet["kisi_sayisi"], ozet["kayit"], ozet["onayli"]]
                                 + [ozet["para"].get(b, 0) for b in birimler]
                                 + [ozet["usd_karsiligi"]])
        self.doldur(self.yil_tablo, ["Yil", "Kisi", "Kayit", "Odemeli"] + birimler
                    + ["USD karsiligi"], yil_satirlari, genis_ilk=90)

    def donem_disa(self):
        basliklar, satirlar = self._donem_veri
        self._disa_aktar(basliklar, satirlar, "aylik_dokum",
                         f"Aylik dokum ({datetime.now():%d.%m.%Y %H:%M})")

    # ------------------------------------------------------------------ #
    # 5) Kayitlar
    # ------------------------------------------------------------------ #

    def _sekme_kayitlar(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="5) Kayitlar")
        self.kayit_filtre = self._filtre_cubugu(sekme, self.kayit_yenile, arama=True)
        cerceve = self.kayit_filtre["_cerceve"]
        ttk.Button(cerceve, text="Excel'e aktar", command=self.kayit_disa).pack(side="right")
        ttk.Button(cerceve, text="Secili donemi sil", command=self.donem_sil).pack(
            side="right", padx=6)
        kutu, self.kayit_tablo = self._tablo(sekme)
        kutu.pack(fill="both", expand=True, padx=8, pady=6)
        self.kayit_bilgi = ttk.Label(sekme, text="")
        self.kayit_bilgi.pack(anchor="w", padx=12, pady=(0, 8))
        self._kayit_veri = ([], [])

    def kayit_yenile(self):
        filtre = self._filtre(self.kayit_filtre)
        veriler = self.db.kayitlar(limit=5000, **filtre)
        basliklar = ["Kisi", "Donem", "Sira", "Baslik", "Dergi", "Quartile", "Tarih",
                     "Kontrol notu", "Tutar", "Birim", "USD karsiligi", "DOI", "Kaynak"]
        satirlar = [[k["kisi"], core.donem_etiketi(k["yil"], k["ay"]), k["sira"], k["baslik"],
                     k["dergi"], k["quartile"], k["tarih"], k["kontrol"], k["tutar"],
                     k["para_birimi"], k["usd_karsiligi"], k["doi"], k["kaynak"]]
                    for k in veriler]
        self.doldur(self.kayit_tablo, basliklar, satirlar, genis_ilk=180)
        self._kayit_veri = (basliklar, satirlar)
        self.kayit_bilgi.config(text=f"{len(satirlar)} kayit (en fazla 5000) | "
                                     + self._ozet_metni(filtre))

    def kayit_disa(self):
        basliklar, satirlar = self._kayit_veri
        self._disa_aktar(basliklar, satirlar, "kayitlar", "Ham kayitlar")

    def donem_sil(self):
        filtre = self._filtre(self.kayit_filtre)
        yil, ay = filtre["yil"], filtre["ay"]
        if not yil:
            messagebox.showinfo("Bilgi", "Once silinecek yili secin.")
            return
        etiket = core.donem_etiketi(yil, ay or 0)
        if messagebox.askyesno("Onay", f"{etiket} kayitlari silinsin mi?"):
            adet = self.db.donem_sil(yil, ay)
            self.bilgi(f"{adet} kayit silindi.")
            self.yenile()

    # ------------------------------------------------------------------ #

    def yenile(self):
        try:
            yillar = [TUM] + [str(y) for y in self.db.yillar()]
            birimler = [TUM] + self.db.kullanilan_para_birimleri()
            for alanlar in (self.kisi_filtre, self.odeme_filtre, self.kayit_filtre):
                for anahtar, degerler in (("yil", yillar), ("para", birimler)):
                    eski = alanlar[anahtar].get()
                    alanlar[anahtar]["values"] = degerler
                    alanlar[anahtar].set(eski if eski in degerler else TUM)
            kisiler = [TUM] + self.db.kisiler()
            eski = self.donem_kisi.get()
            self.donem_kisi["values"] = kisiler
            self.donem_kisi.set(eski if eski in kisiler else TUM)
            self.kisi_yenile()
            self.odeme_yenile()
            self.donem_yenile()
            self.kayit_yenile()
        except Exception:
            traceback.print_exc()


def main():
    Uygulama().mainloop()


if __name__ == "__main__":
    main()
