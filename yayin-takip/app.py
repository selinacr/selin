"""Yayin Takip - masaustu arayuz (tkinter).

Calistirma:  python app.py
Excel dosyalarini ice aktarir, kisi ve odeme turu bazinda aylik/yillik
ozetleri guncel olarak gosterir, istenen tabloyu Excel'e aktarir.
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import core

TUM = "(Tumu)"


def para(deger) -> str:
    try:
        return f"{float(deger):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    except (TypeError, ValueError):
        return str(deger)


class Uygulama(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Yayin Takip - aylik/yillik kisi ve odeme raporlari")
        self.geometry("1180x740")
        self.minsize(900, 600)

        self.db = core.Veritabani(core.VARSAYILAN_DB)
        self.basliklar, self.satirlar, self.esleme_kutulari = [], [], {}
        self.secili_dosya = tk.StringVar(value="")
        self.sayfa_secimi = tk.StringVar(value="")
        self.baslik_satiri = tk.IntVar(value=1)
        self.aktarim_modu = tk.StringVar(value="atla")

        self._ust_bar()
        self.defter = ttk.Notebook(self)
        self.defter.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._sekme_aktar()
        self._sekme_kisi()
        self._sekme_odeme()
        self._sekme_donem()
        self._sekme_kayitlar()
        self.defter.bind("<<NotebookTabChanged>>", lambda e: self.yenile())
        self.protocol("WM_DELETE_WINDOW", self._kapat)
        self.yenile()

    # -- iskelet ----------------------------------------------------------- #

    def _ust_bar(self):
        cerceve = ttk.Frame(self)
        cerceve.pack(fill="x", padx=8, pady=6)
        ttk.Label(cerceve, text="Veritabani:").pack(side="left")
        self.db_etiketi = ttk.Label(cerceve, text=self.db.yol, foreground="#26496b")
        self.db_etiketi.pack(side="left", padx=(4, 10))
        ttk.Button(cerceve, text="Degistir...", command=self.db_degistir).pack(side="left")
        self.durum = ttk.Label(cerceve, text="", foreground="#2f6b2f")
        self.durum.pack(side="right")

    def _tablo(self, ana, kolonlar, yukseklik=18):
        kutu = ttk.Frame(ana)
        agac = ttk.Treeview(kutu, columns=kolonlar, show="headings", height=yukseklik)
        dikey = ttk.Scrollbar(kutu, orient="vertical", command=agac.yview)
        yatay = ttk.Scrollbar(kutu, orient="horizontal", command=agac.xview)
        agac.configure(yscrollcommand=dikey.set, xscrollcommand=yatay.set)
        agac.grid(row=0, column=0, sticky="nsew")
        dikey.grid(row=0, column=1, sticky="ns")
        yatay.grid(row=1, column=0, sticky="ew")
        kutu.rowconfigure(0, weight=1)
        kutu.columnconfigure(0, weight=1)
        for kolon in kolonlar:
            agac.heading(kolon, text=kolon)
            agac.column(kolon, width=120, anchor="center", stretch=True)
        if kolonlar:
            agac.column(kolonlar[0], width=220, anchor="w")
        return kutu, agac

    @staticmethod
    def _tabloyu_doldur(agac, kolonlar, satirlar):
        agac.delete(*agac.get_children())
        agac["columns"] = kolonlar
        for kolon in kolonlar:
            agac.heading(kolon, text=kolon)
            agac.column(kolon, width=120, anchor="e", stretch=True)
        if kolonlar:
            agac.column(kolonlar[0], width=230, anchor="w")
        for satir in satirlar:
            agac.insert("", "end", values=satir)

    def bilgi(self, metin: str):
        self.durum.config(text=metin)
        self.after(6000, lambda: self.durum.config(text=""))

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

    # ------------------------------------------------------------------ #
    # 1) Ice aktarma sekmesi
    # ------------------------------------------------------------------ #

    def _sekme_aktar(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="1) Excel ice aktar")

        ust = ttk.LabelFrame(sekme, text="Dosya")
        ust.pack(fill="x", padx=8, pady=6)
        ttk.Button(ust, text="Excel sec...", command=self.dosya_sec).grid(row=0, column=0, padx=6, pady=6)
        ttk.Label(ust, textvariable=self.secili_dosya, foreground="#26496b").grid(
            row=0, column=1, columnspan=5, sticky="w")
        ttk.Label(ust, text="Sayfa:").grid(row=1, column=0, sticky="e", padx=6)
        self.sayfa_kutusu = ttk.Combobox(ust, textvariable=self.sayfa_secimi,
                                         state="readonly", width=24)
        self.sayfa_kutusu.grid(row=1, column=1, sticky="w")
        self.sayfa_kutusu.bind("<<ComboboxSelected>>", lambda e: self.dosyayi_oku())
        ttk.Label(ust, text="Baslik satiri:").grid(row=1, column=2, sticky="e", padx=6)
        ttk.Spinbox(ust, from_=1, to=50, width=5, textvariable=self.baslik_satiri,
                    command=self.dosyayi_oku).grid(row=1, column=3, sticky="w")
        ttk.Button(ust, text="Yeniden oku", command=self.dosyayi_oku).grid(row=1, column=4, padx=6, pady=4)

        orta = ttk.LabelFrame(sekme, text="Kolon eslestirme (Excel basliklarini alanlara bagla)")
        orta.pack(fill="x", padx=8, pady=6)
        for i, (alan, (etiket, zorunlu, _)) in enumerate(core.ALANLAR.items()):
            satir, sutun = divmod(i, 3)
            hucre = ttk.Frame(orta)
            hucre.grid(row=satir, column=sutun, sticky="w", padx=8, pady=4)
            ttk.Label(hucre, text=etiket + (" *" if zorunlu else ""),
                      width=22, foreground="#a03030" if zorunlu else "#333").pack(side="left")
            kutu = ttk.Combobox(hucre, state="readonly", width=26, values=[TUM])
            kutu.pack(side="left")
            self.esleme_kutulari[alan] = kutu
        profil = ttk.Frame(orta)
        profil.grid(row=99, column=0, columnspan=3, sticky="w", padx=8, pady=6)
        ttk.Label(profil, text="Profil:").pack(side="left")
        self.profil_kutusu = ttk.Combobox(profil, state="readonly", width=22, values=[])
        self.profil_kutusu.pack(side="left", padx=4)
        ttk.Button(profil, text="Profili yukle", command=self.profil_yukle).pack(side="left", padx=2)
        ttk.Button(profil, text="Eslemeyi kaydet", command=self.profil_kaydet).pack(side="left", padx=2)

        alt = ttk.LabelFrame(sekme, text="Onizleme ve aktarim")
        alt.pack(fill="both", expand=True, padx=8, pady=6)
        secim = ttk.Frame(alt)
        secim.pack(fill="x", pady=4)
        ttk.Radiobutton(secim, text="Ayni kayitlari atla (varsayilan)",
                        variable=self.aktarim_modu, value="atla").pack(side="left", padx=6)
        ttk.Radiobutton(secim, text="Dosyadaki donemleri sil ve yeniden yaz",
                        variable=self.aktarim_modu, value="donem_degistir").pack(side="left", padx=6)
        ttk.Button(secim, text="Onizle", command=self.onizle).pack(side="right", padx=6)
        ttk.Button(secim, text="Veritabanina aktar", command=self.aktar).pack(side="right", padx=6)

        kolonlar = ("Kisi", "Yil", "Ay", "Odeme turu", "Eser", "Kanal", "Adet", "Brut", "Kesinti", "Net")
        kutu, self.onizleme = self._tablo(alt, kolonlar, yukseklik=10)
        kutu.pack(fill="both", expand=True, padx=4, pady=4)
        self.gunluk = tk.Text(alt, height=6, wrap="word")
        self.gunluk.pack(fill="x", padx=4, pady=4)

    def dosya_sec(self):
        yol = filedialog.askopenfilename(
            title="Aylik yayin dosyasi",
            filetypes=[("Excel", "*.xlsx *.xlsm *.xltx"), ("Tumu", "*.*")])
        if not yol:
            return
        self.secili_dosya.set(yol)
        try:
            sayfalar = core.sayfa_adlari(yol)
        except Exception as hata:
            messagebox.showerror("Hata", f"Dosya acilamadi:\n{hata}")
            return
        self.sayfa_kutusu["values"] = sayfalar
        self.sayfa_secimi.set(sayfalar[0] if sayfalar else "")
        try:
            self.baslik_satiri.set(core.baslik_satiri_bul(yol, self.sayfa_secimi.get()))
        except Exception:
            self.baslik_satiri.set(1)
        self.dosyayi_oku()

    def dosyayi_oku(self):
        yol = self.secili_dosya.get()
        if not yol:
            return
        try:
            self.basliklar, self.satirlar = core.excel_oku(
                yol, self.sayfa_secimi.get() or None, self.baslik_satiri.get())
        except Exception as hata:
            messagebox.showerror("Hata", f"Sayfa okunamadi:\n{hata}")
            return
        secenekler = [TUM] + [f"{i+1}. {b or '(bos)'}" for i, b in enumerate(self.basliklar)]
        oneri = core.otomatik_esle(self.basliklar)
        for alan, kutu in self.esleme_kutulari.items():
            kutu["values"] = secenekler
            kutu.set(secenekler[oneri[alan] + 1] if alan in oneri else TUM)
        self.profil_kutusu["values"] = list(self.db.profiller().keys())
        self._gunluk(f"{os.path.basename(yol)} / {self.sayfa_secimi.get()}: "
                     f"{len(self.satirlar)} veri satiri, {len(self.basliklar)} kolon okundu.")
        self.onizle()

    def _mevcut_esleme(self) -> dict:
        esleme = {}
        for alan, kutu in self.esleme_kutulari.items():
            deger = kutu.get()
            if deger and deger != TUM:
                esleme[alan] = int(deger.split(".", 1)[0]) - 1
        return esleme

    def _gunluk(self, metin: str):
        self.gunluk.insert("end", f"[{datetime.now():%H:%M:%S}] {metin}\n")
        self.gunluk.see("end")

    def _donustur(self):
        esleme = self._mevcut_esleme()
        return core.satirlari_donustur(
            self.basliklar, self.satirlar, esleme,
            kaynak=os.path.basename(self.secili_dosya.get()))

    def onizle(self):
        if not self.satirlar:
            return
        try:
            kayitlar, hatalar = self._donustur()
        except ValueError as hata:
            self._gunluk(f"UYARI: {hata}")
            return
        veriler = [(k.kisi, k.yil, k.ay, k.odeme_turu, k.eser, k.kanal,
                    k.adet, para(k.brut), para(k.kesinti), para(k.net)) for k in kayitlar[:200]]
        self.onizleme.delete(*self.onizleme.get_children())
        for satir in veriler:
            self.onizleme.insert("", "end", values=satir)
        self._gunluk(f"Onizleme: {len(kayitlar)} gecerli satir, {len(hatalar)} hatali satir.")
        for no, sebep in hatalar[:5]:
            self._gunluk(f"  - satir {no}: {sebep}")

    def aktar(self):
        if not self.satirlar:
            messagebox.showinfo("Bilgi", "Once bir Excel dosyasi secin.")
            return
        try:
            kayitlar, hatalar = self._donustur()
        except ValueError as hata:
            messagebox.showerror("Eksik eslestirme", str(hata))
            return
        if not kayitlar:
            messagebox.showwarning("Bos", "Aktarilacak gecerli satir bulunamadi.")
            return
        if self.aktarim_modu.get() == "donem_degistir":
            donemler = sorted({core.donem_etiketi(k.yil, k.ay) for k in kayitlar})
            if not messagebox.askyesno(
                    "Onay", "Su donemlerdeki mevcut kayitlar silinip yeniden yazilacak:\n\n"
                            + ", ".join(donemler) + "\n\nDevam edilsin mi?"):
                return
        sonuc = self.db.aktar(kayitlar, self.aktarim_modu.get(),
                              dosya=self.secili_dosya.get(), sayfa=self.sayfa_secimi.get(),
                              hatali=len(hatalar))
        self._gunluk(f"Aktarim tamam - eklenen: {sonuc['eklenen']}, "
                     f"atlanan (mukerrer): {sonuc['atlanan']}, silinen: {sonuc['silinen']}, "
                     f"hatali: {sonuc['hatali']}")
        self.bilgi(f"{sonuc['eklenen']} kayit eklendi.")
        self.yenile()

    def profil_kaydet(self):
        esleme = self._mevcut_esleme()
        eksik = [a for a in core.ZORUNLU_ALANLAR if a not in esleme]
        if eksik:
            messagebox.showerror("Eksik", "Zorunlu alanlar eslenmeden profil kaydedilemez.")
            return
        pencere = tk.Toplevel(self)
        pencere.title("Profil adi")
        pencere.transient(self)
        pencere.grab_set()
        ttk.Label(pencere, text="Profil adi:").pack(padx=10, pady=(10, 2))
        deger = tk.StringVar(value=os.path.splitext(os.path.basename(self.secili_dosya.get()))[0][:30])
        giris = ttk.Entry(pencere, textvariable=deger, width=32)
        giris.pack(padx=10, pady=4)
        giris.focus_set()

        def kaydet():
            ad = deger.get().strip()
            if ad:
                self.db.profil_kaydet(ad, esleme, self.baslik_satiri.get())
                self.profil_kutusu["values"] = list(self.db.profiller().keys())
                self.profil_kutusu.set(ad)
                self._gunluk(f"'{ad}' profili kaydedildi.")
            pencere.destroy()

        ttk.Button(pencere, text="Kaydet", command=kaydet).pack(pady=(4, 10))

    def profil_yukle(self):
        ad = self.profil_kutusu.get()
        profiller = self.db.profiller()
        if ad not in profiller:
            return
        esleme, baslik = profiller[ad]
        self.baslik_satiri.set(baslik or 1)
        self.dosyayi_oku()
        secenekler = list(self.esleme_kutulari["kisi"]["values"])
        for alan, kutu in self.esleme_kutulari.items():
            i = esleme.get(alan)
            kutu.set(secenekler[i + 1] if i is not None and i + 1 < len(secenekler) else TUM)
        self._gunluk(f"'{ad}' profili yuklendi.")
        self.onizle()

    # ------------------------------------------------------------------ #
    # Ortak filtre serisi
    # ------------------------------------------------------------------ #

    def _filtre_cubugu(self, ana, komut, arama_var=None, olcu=False):
        cerceve = ttk.Frame(ana)
        cerceve.pack(fill="x", padx=8, pady=6)
        ttk.Label(cerceve, text="Yil:").pack(side="left")
        yil = ttk.Combobox(cerceve, state="readonly", width=8, values=[TUM])
        yil.set(TUM)
        yil.pack(side="left", padx=(2, 10))
        ttk.Label(cerceve, text="Ay:").pack(side="left")
        ay = ttk.Combobox(cerceve, state="readonly", width=12,
                          values=[TUM] + core.AY_ADLARI)
        ay.set(TUM)
        ay.pack(side="left", padx=(2, 10))
        olcu_kutusu = None
        if olcu:
            ttk.Label(cerceve, text="Olcu:").pack(side="left")
            olcu_kutusu = ttk.Combobox(cerceve, state="readonly", width=10,
                                       values=["net", "brut", "kesinti", "adet"])
            olcu_kutusu.set("net")
            olcu_kutusu.pack(side="left", padx=(2, 10))
            olcu_kutusu.bind("<<ComboboxSelected>>", lambda e: komut())
        if arama_var is not None:
            ttk.Label(cerceve, text="Ara:").pack(side="left")
            giris = ttk.Entry(cerceve, textvariable=arama_var, width=22)
            giris.pack(side="left", padx=2)
            giris.bind("<Return>", lambda e: komut())
        ttk.Button(cerceve, text="Uygula", command=komut).pack(side="left", padx=6)
        yil.bind("<<ComboboxSelected>>", lambda e: komut())
        ay.bind("<<ComboboxSelected>>", lambda e: komut())
        return cerceve, yil, ay, olcu_kutusu

    @staticmethod
    def _filtre_degerleri(yil_kutusu, ay_kutusu):
        yil = yil_kutusu.get()
        ay = ay_kutusu.get()
        return (int(yil) if yil and yil != TUM else None,
                core.AY_ADLARI.index(ay) + 1 if ay and ay != TUM else None)

    def _yillari_tazele(self, *kutular):
        yillar = [TUM] + [str(y) for y in self.db.yillar()]
        for kutu in kutular:
            eski = kutu.get()
            kutu["values"] = yillar
            kutu.set(eski if eski in yillar else TUM)

    def _disa_aktar(self, kolonlar, satirlar, ad: str, not_metni: str = ""):
        if not satirlar:
            messagebox.showinfo("Bos", "Aktarilacak veri yok.")
            return
        yol = filedialog.asksaveasfilename(
            title="Excel olarak kaydet", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"{ad}_{datetime.now():%Y%m%d_%H%M}.xlsx")
        if not yol:
            return
        para_kolonlari = [i for i, k in enumerate(kolonlar)
                          if i > 0 and str(k).lower() not in ("kayit", "kisi sayisi", "yil", "ay")]
        core.excel_yaz(yol, kolonlar, satirlar, ad[:31], para_kolonlari, not_metni)
        self.bilgi(f"Kaydedildi: {os.path.basename(yol)}")
        if messagebox.askyesno("Tamam", f"Rapor kaydedildi:\n{yol}\n\nKlasoru acmak ister misiniz?"):
            self._klasor_ac(yol)

    @staticmethod
    def _klasor_ac(yol):
        klasor = os.path.dirname(os.path.abspath(yol))
        try:
            if os.name == "nt":
                os.startfile(klasor)  # noqa: S606
            elif os.uname().sysname == "Darwin":
                os.system(f'open "{klasor}"')
            else:
                os.system(f'xdg-open "{klasor}"')
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # 2) Kisi bazinda
    # ------------------------------------------------------------------ #

    def _sekme_kisi(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="2) Kisi bazinda")
        self.kisi_arama = tk.StringVar()
        _, self.kisi_yil, self.kisi_ay, self.kisi_olcu = self._filtre_cubugu(
            sekme, self.kisi_yenile, self.kisi_arama, olcu=True)

        self.kisi_gorunum = tk.StringVar(value="ozet")
        secim = ttk.Frame(sekme)
        secim.pack(fill="x", padx=8)
        ttk.Radiobutton(secim, text="Ozet (toplamlar)", variable=self.kisi_gorunum,
                        value="ozet", command=self.kisi_yenile).pack(side="left")
        ttk.Radiobutton(secim, text="Aylik pivot (kisi x ay)", variable=self.kisi_gorunum,
                        value="pivot", command=self.kisi_yenile).pack(side="left", padx=8)
        ttk.Button(secim, text="Excel'e aktar", command=self.kisi_disa).pack(side="right")
        ttk.Label(secim, text="(kisiye cift tiklayin: detay)").pack(side="right", padx=10)

        kutu, self.kisi_tablo = self._tablo(sekme, ("Kisi",))
        kutu.pack(fill="both", expand=True, padx=8, pady=6)
        self.kisi_tablo.bind("<Double-1>", self.kisi_detay)
        self.kisi_toplam = ttk.Label(sekme, text="", font=("", 10, "bold"))
        self.kisi_toplam.pack(anchor="w", padx=12, pady=(0, 8))
        self._kisi_veri = ([], [])

    def kisi_yenile(self):
        yil, ay = self._filtre_degerleri(self.kisi_yil, self.kisi_ay)
        arama = self.kisi_arama.get().strip() or None
        if self.kisi_gorunum.get() == "pivot":
            olcu = self.kisi_olcu.get() if self.kisi_olcu else "net"
            kolonlar, satirlar = self.db.pivot("kisi", yil=yil, olcu=olcu, ay=ay, arama=arama)
            gosterim = [[s[0]] + [para(x) for x in s[1:]] for s in satirlar]
        else:
            kolonlar = ["Kisi", "Kayit", "Adet", "Brut", "Kesinti", "Net"]
            veriler = self.db.kisi_ozet(yil=yil, ay=ay, arama=arama)
            satirlar = [[v["kisi"], v["kayit"], v["adet"], v["brut"], v["kesinti"], v["net"]]
                        for v in veriler]
            gosterim = [[s[0], s[1], f"{s[2]:g}", para(s[3]), para(s[4]), para(s[5])] for s in satirlar]
        self._tabloyu_doldur(self.kisi_tablo, kolonlar, gosterim)
        self._kisi_veri = (kolonlar, satirlar)
        ozet = self.db.genel_ozet(yil=yil, ay=ay, arama=arama)
        self.kisi_toplam.config(
            text=f"{ozet['kisi_sayisi']} kisi | {ozet['kayit']} kayit | "
                 f"Brut {para(ozet['brut'])} | Kesinti {para(ozet['kesinti'])} | "
                 f"Net {para(ozet['net'])}")

    def kisi_disa(self):
        kolonlar, satirlar = self._kisi_veri
        yil, ay = self._filtre_degerleri(self.kisi_yil, self.kisi_ay)
        etiket = f"{yil or 'Tum yillar'}{'/' + core.AY_ADLARI[ay-1] if ay else ''}"
        self._disa_aktar(kolonlar, satirlar, "kisi_bazinda",
                         f"Kisi bazinda rapor - {etiket} ({datetime.now():%d.%m.%Y %H:%M})")

    def kisi_detay(self, _olay=None):
        secim = self.kisi_tablo.selection()
        if not secim:
            return
        kisi = self.kisi_tablo.item(secim[0])["values"][0]
        yillik, turler = self.db.kisi_yillik(kisi)
        pencere = tk.Toplevel(self)
        pencere.title(f"{kisi} - detay")
        pencere.geometry("760x520")
        ttk.Label(pencere, text=str(kisi), font=("", 12, "bold")).pack(anchor="w", padx=10, pady=8)

        ttk.Label(pencere, text="Yillik ozet").pack(anchor="w", padx=10)
        kutu1, tablo1 = self._tablo(pencere, ("Yil", "Kayit", "Brut", "Kesinti", "Net"), yukseklik=6)
        kutu1.pack(fill="both", expand=True, padx=10, pady=4)
        self._tabloyu_doldur(tablo1, ["Yil", "Kayit", "Brut", "Kesinti", "Net"],
                             [[y["yil"], y["kayit"], para(y["brut"]), para(y["kesinti"]), para(y["net"])]
                              for y in yillik])

        ttk.Label(pencere, text="Odeme turu dagilimi").pack(anchor="w", padx=10)
        kutu2, tablo2 = self._tablo(pencere, ("Odeme turu", "Kayit", "Net"), yukseklik=6)
        kutu2.pack(fill="both", expand=True, padx=10, pady=4)
        self._tabloyu_doldur(tablo2, ["Odeme turu", "Kayit", "Net"],
                             [[t["odeme_turu"], t["kayit"], para(t["net"])] for t in turler])

        ttk.Button(pencere, text="Bu kisiyi Excel'e aktar",
                   command=lambda: self._disa_aktar(
                       ["Yil", "Kayit", "Brut", "Kesinti", "Net"],
                       [[y["yil"], y["kayit"], y["brut"], y["kesinti"], y["net"]] for y in yillik],
                       f"kisi_{str(kisi)[:20]}", f"{kisi} - yillik ozet")).pack(pady=8)

    # ------------------------------------------------------------------ #
    # 3) Odeme bazinda
    # ------------------------------------------------------------------ #

    def _sekme_odeme(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="3) Odeme bazinda")
        self.odeme_arama = tk.StringVar()
        _, self.odeme_yil, self.odeme_ay, self.odeme_olcu = self._filtre_cubugu(
            sekme, self.odeme_yenile, self.odeme_arama, olcu=True)

        self.odeme_gorunum = tk.StringVar(value="ozet")
        secim = ttk.Frame(sekme)
        secim.pack(fill="x", padx=8)
        ttk.Radiobutton(secim, text="Ozet (toplamlar)", variable=self.odeme_gorunum,
                        value="ozet", command=self.odeme_yenile).pack(side="left")
        ttk.Radiobutton(secim, text="Aylik pivot (odeme turu x ay)", variable=self.odeme_gorunum,
                        value="pivot", command=self.odeme_yenile).pack(side="left", padx=8)
        ttk.Radiobutton(secim, text="Kanal/platform pivotu", variable=self.odeme_gorunum,
                        value="kanal", command=self.odeme_yenile).pack(side="left", padx=8)
        ttk.Button(secim, text="Excel'e aktar", command=self.odeme_disa).pack(side="right")

        kutu, self.odeme_tablo = self._tablo(sekme, ("Odeme turu",))
        kutu.pack(fill="both", expand=True, padx=8, pady=6)
        self.odeme_toplam = ttk.Label(sekme, text="", font=("", 10, "bold"))
        self.odeme_toplam.pack(anchor="w", padx=12, pady=(0, 8))
        self._odeme_veri = ([], [])

    def odeme_yenile(self):
        yil, ay = self._filtre_degerleri(self.odeme_yil, self.odeme_ay)
        arama = self.odeme_arama.get().strip() or None
        gorunum = self.odeme_gorunum.get()
        olcu = self.odeme_olcu.get() if self.odeme_olcu else "net"
        if gorunum in ("pivot", "kanal"):
            alan = "odeme_turu" if gorunum == "pivot" else "kanal"
            kolonlar, satirlar = self.db.pivot(alan, yil=yil, olcu=olcu, ay=ay, arama=arama)
            gosterim = [[s[0]] + [para(x) for x in s[1:]] for s in satirlar]
        else:
            kolonlar = ["Odeme turu", "Kayit", "Kisi sayisi", "Adet", "Brut", "Kesinti", "Net"]
            veriler = self.db.odeme_ozet(yil=yil, ay=ay, arama=arama)
            satirlar = [[v["odeme_turu"], v["kayit"], v["kisi_sayisi"], v["adet"],
                         v["brut"], v["kesinti"], v["net"]] for v in veriler]
            gosterim = [[s[0], s[1], s[2], f"{s[3]:g}", para(s[4]), para(s[5]), para(s[6])]
                        for s in satirlar]
        self._tabloyu_doldur(self.odeme_tablo, kolonlar, gosterim)
        self._odeme_veri = (kolonlar, satirlar)
        ozet = self.db.genel_ozet(yil=yil, ay=ay, arama=arama)
        self.odeme_toplam.config(text=f"Toplam net: {para(ozet['net'])} | "
                                      f"Brut: {para(ozet['brut'])} | Kayit: {ozet['kayit']}")

    def odeme_disa(self):
        kolonlar, satirlar = self._odeme_veri
        self._disa_aktar(kolonlar, satirlar, "odeme_bazinda",
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
        self.donem_kisi = ttk.Combobox(cerceve, state="readonly", width=28, values=[TUM])
        self.donem_kisi.set(TUM)
        self.donem_kisi.pack(side="left", padx=4)
        self.donem_kisi.bind("<<ComboboxSelected>>", lambda e: self.donem_yenile())
        ttk.Label(cerceve, text="Odeme turu:").pack(side="left", padx=(10, 0))
        self.donem_tur = ttk.Combobox(cerceve, state="readonly", width=22, values=[TUM])
        self.donem_tur.set(TUM)
        self.donem_tur.pack(side="left", padx=4)
        self.donem_tur.bind("<<ComboboxSelected>>", lambda e: self.donem_yenile())
        ttk.Button(cerceve, text="Yenile", command=self.donem_yenile).pack(side="left", padx=6)
        ttk.Button(cerceve, text="Excel'e aktar", command=self.donem_disa).pack(side="right")

        ttk.Label(sekme, text="Aylik dokum").pack(anchor="w", padx=10)
        kutu1, self.donem_tablo = self._tablo(
            sekme, ("Donem", "Kisi sayisi", "Kayit", "Adet", "Brut", "Kesinti", "Net"), yukseklik=12)
        kutu1.pack(fill="both", expand=True, padx=8, pady=4)
        ttk.Label(sekme, text="Yillik toplam").pack(anchor="w", padx=10)
        kutu2, self.yil_tablo = self._tablo(
            sekme, ("Yil", "Kisi sayisi", "Kayit", "Brut", "Kesinti", "Net"), yukseklik=6)
        kutu2.pack(fill="both", expand=True, padx=8, pady=4)
        self._donem_veri = ([], [])

    def donem_yenile(self):
        kisi = self.donem_kisi.get()
        tur = self.donem_tur.get()
        filtre = {}
        if kisi and kisi != TUM:
            filtre["kisi"] = kisi
        if tur and tur != TUM:
            filtre["odeme_turu"] = tur
        aylik = self.db.aylik_seri(**filtre)
        kolonlar = ["Donem", "Kisi sayisi", "Kayit", "Adet", "Brut", "Kesinti", "Net"]
        satirlar = [[core.donem_etiketi(a["yil"], a["ay"]), a["kisi_sayisi"], a["kayit"],
                     a["adet"], a["brut"], a["kesinti"], a["net"]] for a in aylik]
        self._tabloyu_doldur(self.donem_tablo, kolonlar,
                             [[s[0], s[1], s[2], f"{s[3]:g}", para(s[4]), para(s[5]), para(s[6])]
                              for s in satirlar])
        self._donem_veri = (kolonlar, satirlar)

        yillik = {}
        for a in aylik:
            hedef = yillik.setdefault(a["yil"], {"kayit": 0, "brut": 0.0, "kesinti": 0.0, "net": 0.0})
            hedef["kayit"] += a["kayit"]
            for alan in ("brut", "kesinti", "net"):
                hedef[alan] += a[alan]
        yil_kolonlari = ["Yil", "Kisi sayisi", "Kayit", "Brut", "Kesinti", "Net"]
        yil_satirlari = []
        for yil in sorted(yillik, reverse=True):
            ozet = self.db.genel_ozet(yil=yil, **filtre)
            v = yillik[yil]
            yil_satirlari.append([yil, ozet["kisi_sayisi"], v["kayit"],
                                  para(v["brut"]), para(v["kesinti"]), para(v["net"])])
        self._tabloyu_doldur(self.yil_tablo, yil_kolonlari, yil_satirlari)

    def donem_disa(self):
        kolonlar, satirlar = self._donem_veri
        self._disa_aktar(kolonlar, satirlar, "donem_dokumu",
                         f"Aylik dokum ({datetime.now():%d.%m.%Y %H:%M})")

    # ------------------------------------------------------------------ #
    # 5) Kayitlar
    # ------------------------------------------------------------------ #

    def _sekme_kayitlar(self):
        sekme = ttk.Frame(self.defter)
        self.defter.add(sekme, text="5) Kayitlar")
        self.kayit_arama = tk.StringVar()
        cerceve, self.kayit_yil, self.kayit_ay, _ = self._filtre_cubugu(
            sekme, self.kayit_yenile, self.kayit_arama)
        ttk.Button(cerceve, text="Excel'e aktar", command=self.kayit_disa).pack(side="right")
        ttk.Button(cerceve, text="Secili donemi sil", command=self.donem_sil).pack(side="right", padx=6)

        kolonlar = ("Kisi", "Donem", "Tarih", "Odeme turu", "Eser", "Kanal",
                    "Adet", "Brut", "Kesinti", "Net", "Kaynak")
        kutu, self.kayit_tablo = self._tablo(sekme, kolonlar)
        kutu.pack(fill="both", expand=True, padx=8, pady=6)
        self.kayit_bilgi = ttk.Label(sekme, text="")
        self.kayit_bilgi.pack(anchor="w", padx=12, pady=(0, 8))
        self._kayit_veri = ([], [])

    def kayit_yenile(self):
        yil, ay = self._filtre_degerleri(self.kayit_yil, self.kayit_ay)
        arama = self.kayit_arama.get().strip() or None
        veriler = self.db.kayitlar(limit=5000, yil=yil, ay=ay, arama=arama)
        kolonlar = ["Kisi", "Donem", "Tarih", "Odeme turu", "Eser", "Kanal",
                    "Adet", "Brut", "Kesinti", "Net", "Kaynak"]
        satirlar = [[k["kisi"], core.donem_etiketi(k["yil"], k["ay"]), k["tarih"] or "",
                     k["odeme_turu"], k["eser"], k["kanal"], k["adet"],
                     k["brut"], k["kesinti"], k["net"], k["kaynak"]] for k in veriler]
        self._tabloyu_doldur(self.kayit_tablo, kolonlar,
                             [s[:6] + [f"{s[6]:g}", para(s[7]), para(s[8]), para(s[9]), s[10]]
                              for s in satirlar])
        self._kayit_veri = (kolonlar, satirlar)
        self.kayit_bilgi.config(text=f"{len(satirlar)} kayit gosteriliyor (en fazla 5000).")

    def kayit_disa(self):
        kolonlar, satirlar = self._kayit_veri
        self._disa_aktar(kolonlar, satirlar, "kayitlar", "Ham kayitlar")

    def donem_sil(self):
        yil, ay = self._filtre_degerleri(self.kayit_yil, self.kayit_ay)
        if not yil:
            messagebox.showinfo("Bilgi", "Once silinecek yili secin.")
            return
        etiket = f"{yil}" + (f" / {core.AY_ADLARI[ay-1]}" if ay else " (tum yil)")
        if messagebox.askyesno("Onay", f"{etiket} donemindeki kayitlar silinsin mi?"):
            adet = self.db.donem_sil(yil, ay)
            self.bilgi(f"{adet} kayit silindi.")
            self.yenile()

    # ------------------------------------------------------------------ #

    def yenile(self):
        try:
            self._yillari_tazele(self.kisi_yil, self.odeme_yil, self.kayit_yil)
            kisiler = [TUM] + self.db.kisiler()
            eski = self.donem_kisi.get()
            self.donem_kisi["values"] = kisiler
            self.donem_kisi.set(eski if eski in kisiler else TUM)
            turler = [TUM] + self.db.odeme_turleri()
            eski_tur = self.donem_tur.get()
            self.donem_tur["values"] = turler
            self.donem_tur.set(eski_tur if eski_tur in turler else TUM)
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
