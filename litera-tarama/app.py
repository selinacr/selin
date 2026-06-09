"""litera-tarama — Streamlit web arayüzü.

Çalıştırma:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt

import streamlit as st

from litera.export import csv_bytes, excel_bytes, to_dataframe
from litera.report import build_markdown
from litera.search import run_search
from litera.sources import DEFAULT_SOURCES, source_labels

st.set_page_config(page_title="Literatür Tarama", page_icon="🔎", layout="wide")

st.title("🔎 Literatür Tarama ve Özet Sistemi")
st.caption(
    "OpenAlex · Crossref · Semantic Scholar · arXiv kaynaklarını her seferinde "
    "sıfırdan tarar, tekilleştirir ve özetler."
)

labels = source_labels()

with st.sidebar:
    st.header("Arama Ayarları")
    selected = st.multiselect(
        "Kaynaklar",
        options=list(labels.keys()),
        default=DEFAULT_SOURCES,
        format_func=lambda k: labels[k],
    )
    bu_yil = dt.date.today().year
    yil_araligi = st.slider(
        "Yıl aralığı", min_value=1970, max_value=bu_yil,
        value=(bu_yil - 10, bu_yil),
    )
    per_source = st.slider("Kaynak başına azami kayıt", 10, 200, 50, step=10)
    st.markdown("---")
    st.markdown(
        "**Not:** IEEE/Scopus/WoS ve Google Scholar anahtar/abonelik gerektirir; "
        "bu sürümde anahtarsız çekirdek kaynaklar aktiftir. OpenAlex bu "
        "veritabanlarındaki içeriğin büyük kısmını zaten kapsar."
    )

query = st.text_input(
    "Anahtar kelime / konu",
    placeholder="örn. fractional-order analog filter pulse shaping",
)
calistir = st.button("Tara", type="primary", use_container_width=True)

if calistir:
    if not query.strip():
        st.warning("Lütfen bir anahtar kelime girin.")
        st.stop()
    if not selected:
        st.warning("En az bir kaynak seçin.")
        st.stop()

    with st.status("Kaynaklar sıfırdan taranıyor…", expanded=True) as status:
        def progress(name):
            status.write(f"✓ {labels.get(name, name)} tamamlandı")

        result = run_search(
            query.strip(),
            sources=selected,
            year_from=yil_araligi[0],
            year_to=yil_araligi[1],
            per_source_limit=per_source,
            progress=progress,
        )
        status.update(label="Tarama tamamlandı.", state="complete")

    st.session_state["result"] = result
    st.session_state["query"] = query.strip()

result = st.session_state.get("result")
if result is not None:
    s = result.summary
    query = st.session_state.get("query", result.query)

    # --- Üst metrikler -------------------------------------------------------
    c = st.columns(4)
    c[0].metric("Toplam çalışma", s["total"])
    c[1].metric(
        "Tarih aralığı",
        f"{s['year_min']}–{s['year_max']}" if s["year_min"] else "—",
    )
    c[2].metric("Tür sayısı", len(s["by_type"]))
    c[3].metric("Sorgulanan kaynak", len(result.per_source_counts))

    if result.errors:
        st.warning(
            "Erişilemeyen/hatalı kaynaklar: "
            + ", ".join(f"{k}" for k in result.errors)
            + " — (ağ kısıtı veya hız sınırı olabilir)"
        )

    if s["total"] == 0:
        st.info("Bu sorgu için sonuç bulunamadı. Farklı anahtar kelime deneyin.")
        st.stop()

    # --- Dağılımlar ----------------------------------------------------------
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Tür dağılımı")
        st.bar_chart(s["by_type"])
    with col2:
        st.subheader("Yıllara göre dağılım")
        st.bar_chart(s["by_year"])

    # --- Matris tablo --------------------------------------------------------
    st.subheader("Çalışma matrisi")
    df = to_dataframe(result.papers)
    st.dataframe(df, use_container_width=True, height=420)

    # --- İndirme butonları ---------------------------------------------------
    md = build_markdown(query, result, s)
    d = st.columns(3)
    fname = "literatur_" + "".join(ch if ch.isalnum() else "_" for ch in query)[:40]
    d[0].download_button(
        "⬇️ Markdown rapor", md, file_name=f"{fname}.md", mime="text/markdown",
        use_container_width=True,
    )
    d[1].download_button(
        "⬇️ CSV matris", csv_bytes(result.papers), file_name=f"{fname}.csv",
        mime="text/csv", use_container_width=True,
    )
    try:
        d[2].download_button(
            "⬇️ Excel matris", excel_bytes(result.papers),
            file_name=f"{fname}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception:
        d[2].caption("Excel için `openpyxl` kurulu olmalı")

    # --- Öne çıkanlar + rapor önizleme --------------------------------------
    with st.expander("📄 Markdown rapor önizleme", expanded=False):
        st.markdown(md)
