"""Ortak arayuz parcalari: renk paleti, ttk stilleri ve tablo yardimcilari."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

RENK = {
    "zemin": "#f4f5f3",
    "kart": "#ffffff",
    "cizgi": "#e2e5e1",
    "yazi": "#16211d",
    "soluk": "#6b7671",
    "vurgu": "#14554a",
    "vurgu_yazi": "#ffffff",
    "vurgu_acik": "#e6efeb",
    "serit": "#fafbfa",
    "toplam": "#eef3f0",
}


def yazi_tipi(kok: tk.Misc) -> str:
    mevcut = set(tkfont.families(kok))
    for aday in ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans", "Arial"):
        if aday in mevcut:
            return aday
    return "TkDefaultFont"


def stil_kur(kok: tk.Misc) -> ttk.Style:
    """Uygulamanin tum ttk stillerini tanimlar."""
    stil = ttk.Style(kok)
    try:
        stil.theme_use("clam")
    except tk.TclError:
        pass
    ad = yazi_tipi(kok)
    kok.configure(background=RENK["zemin"])
    stil.configure(".", background=RENK["zemin"], foreground=RENK["yazi"],
                   font=(ad, 10), borderwidth=0)
    stil.configure("TFrame", background=RENK["zemin"])
    stil.configure("Kart.TFrame", background=RENK["kart"])
    stil.configure("TLabel", background=RENK["zemin"], foreground=RENK["yazi"])
    stil.configure("Kart.TLabel", background=RENK["kart"])
    stil.configure("Baslik.TLabel", font=(ad, 19, "bold"))
    stil.configure("AltBaslik.TLabel", foreground=RENK["soluk"], font=(ad, 10))
    stil.configure("Bolum.TLabel", font=(ad, 11, "bold"))
    stil.configure("Sayi.TLabel", font=(ad, 20, "bold"), background=RENK["kart"])
    stil.configure("SayiEtiket.TLabel", foreground=RENK["soluk"], font=(ad, 9),
                   background=RENK["kart"])
    stil.configure("Ipucu.TLabel", foreground=RENK["soluk"], font=(ad, 9))
    stil.configure("Durum.TLabel", foreground=RENK["vurgu"], font=(ad, 9, "bold"))

    # Secilebilir "chip" dugmeleri (segmentli filtreler)
    stil.configure("Chip.Toolbutton", font=(ad, 10), padding=(14, 6),
                   background=RENK["kart"], foreground=RENK["yazi"],
                   borderwidth=1, relief="flat", anchor="center")
    stil.map("Chip.Toolbutton",
             background=[("selected", RENK["vurgu"]), ("active", RENK["vurgu_acik"])],
             foreground=[("selected", RENK["vurgu_yazi"])])
    stil.configure("TCheckbutton", background=RENK["zemin"])

    stil.configure("TButton", font=(ad, 10), padding=(12, 6),
                   background=RENK["kart"], foreground=RENK["yazi"], relief="flat")
    stil.map("TButton", background=[("active", RENK["vurgu_acik"])])
    stil.configure("Ana.TButton", background=RENK["vurgu"], foreground=RENK["vurgu_yazi"],
                   font=(ad, 10, "bold"), padding=(16, 8))
    stil.map("Ana.TButton", background=[("active", "#1b6c5e")])

    stil.configure("TEntry", fieldbackground=RENK["kart"], padding=6)
    stil.configure("TCombobox", fieldbackground=RENK["kart"], padding=4)

    stil.configure("Panel.Treeview", background=RENK["kart"], fieldbackground=RENK["kart"],
                   foreground=RENK["yazi"], rowheight=27, font=(ad, 10), borderwidth=0)
    stil.configure("Panel.Treeview.Heading", background=RENK["kart"],
                   foreground=RENK["soluk"], font=(ad, 9, "bold"), relief="flat",
                   padding=(6, 8))
    stil.map("Panel.Treeview.Heading", background=[("active", RENK["vurgu_acik"])])
    stil.configure("TScrollbar", background=RENK["kart"], troughcolor=RENK["zemin"],
                   bordercolor=RENK["zemin"], arrowcolor=RENK["soluk"], relief="flat")
    stil.map("TScrollbar", background=[("active", RENK["vurgu_acik"])])
    stil.map("Panel.Treeview",
             background=[("selected", RENK["vurgu_acik"])],
             foreground=[("selected", RENK["yazi"])])
    return stil


def tablo_olustur(ana, yukseklik=18):
    """Kaydirma cubuklu, seritli bir Treeview doner."""
    kutu = ttk.Frame(ana, style="Kart.TFrame")
    agac = ttk.Treeview(kutu, columns=("bos",), show="headings", height=yukseklik,
                        style="Panel.Treeview")
    dikey = ttk.Scrollbar(kutu, orient="vertical", command=agac.yview)
    yatay = ttk.Scrollbar(kutu, orient="horizontal", command=agac.xview)
    agac.configure(yscrollcommand=dikey.set, xscrollcommand=yatay.set)
    agac.grid(row=0, column=0, sticky="nsew")
    dikey.grid(row=0, column=1, sticky="ns")
    yatay.grid(row=1, column=0, sticky="ew")
    kutu.rowconfigure(0, weight=1)
    kutu.columnconfigure(0, weight=1)
    agac.tag_configure("tek", background=RENK["serit"])
    agac.tag_configure("cift", background=RENK["kart"])
    agac.tag_configure("toplam", background=RENK["toplam"], font=(yazi_tipi(ana), 10, "bold"))
    return kutu, agac


def tabloyu_doldur(agac, basliklar, satirlar, genis_ilk=230, vurgulu_kolonlar=(),
                   toplam_satiri=False):
    """Basliklari ve satirlari yazar; son satir istenirse toplam olarak isaretlenir."""
    agac.delete(*agac.get_children())
    agac["columns"] = [str(i) for i in range(len(basliklar))]
    for i, baslik in enumerate(basliklar):
        agac.heading(str(i), text=baslik)
        genislik = 108 if i in vurgulu_kolonlar else 96
        agac.column(str(i), width=genislik, anchor="e", stretch=(i > 0))
    if basliklar:
        agac.column("0", width=genis_ilk, anchor="w", stretch=True)
    son = len(satirlar) - 1
    for sira, satir in enumerate(satirlar):
        etiket = "toplam" if (toplam_satiri and sira == son) else ("tek" if sira % 2 else "cift")
        agac.insert("", "end", values=satir, tags=(etiket,))
