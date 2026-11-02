"""Strait Watch — peta kapal live di Selat Malaka dan Selat Singapura dari data AIS publik (aisstream.io).

Jalankan: streamlit run app.py
Struktur file ini dibaca dari atas ke bawah: konfigurasi → data → sidebar → KPI → halaman.
"""

from __future__ import annotations

import os
from datetime import timezone, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from src import ais, analisis, muat_data, peta, portwatch
from src import mmsi as km

# ------------------------------------------------------------------ konfigurasi
st.set_page_config(page_title="Strait Watch", page_icon="🚢", layout="wide")

# Kunci API aisstream.io (gratis) dibaca dari st.secrets atau variabel lingkungan.
# Di Streamlit Community Cloud: menu Settings → Secrets, isi:
#   [aisstream]
#   api_key = "..."
try:
    _kunci_secrets = st.secrets.get("aisstream", {}).get("api_key")
    if _kunci_secrets:
        os.environ.setdefault("AISSTREAM_API_KEY", str(_kunci_secrets))
except Exception:  # tidak ada berkas secrets
    pass

WIB = timezone(timedelta(hours=7))
TEAL = "#2ec4b6"
MERAH = "#ff4d6d"
ABU = "#6c7a89"
TEMPLATE = "plotly_dark"
MAKS_SNAPSHOT_SESI = 90  # batas jejak yang disimpan di memori pada mode live
JENDELA_MENIT = 30  # mode live: peta menampilkan posisi terakhir setiap kapal yang terdengar 30 menit terakhir


def fmt_wib(ts) -> str:
    """Timestamp UTC → teks WIB, misalnya '02 Nov 2026 20:15:00 WIB'."""
    if ts is None or pd.isna(ts):
        return "-"
    return pd.Timestamp(ts).tz_convert(WIB).strftime("%d %b %Y %H:%M:%S WIB")


def grafik_batang(df: pd.DataFrame, x: str, y: str, judul: str, warna=None, hover: str | None = None,
                  satuan: str = "kapal") -> go.Figure:
    """Batang horizontal; ``warna`` boleh satu warna, daftar warna, atau None (teal)."""
    fig = go.Figure(
        go.Bar(
            x=df[x], y=df[y], orientation="h", marker_color=warna or TEAL, marker_line_width=0,
            text=df[x], textposition="outside", cliponaxis=False,
            customdata=df[hover] if hover else None,
            hovertemplate="<b>%{y}</b><br>%{x} " + satuan + ("<br>%{customdata}%" if hover else "") + "<extra></extra>",
        )
    )
    fig.update_layout(
        template=TEMPLATE, title=judul, height=max(300, 28 * len(df) + 90),
        margin=dict(l=10, r=40, t=50, b=10), yaxis=dict(autorange="reversed", title=""),
        xaxis=dict(title=f"{satuan} unik", showgrid=True, gridcolor="#223"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner=False)
def pelabuhan_df() -> pd.DataFrame:
    return muat_data.muat_pelabuhan()


@st.cache_data(show_spinner=False)
def titik_kunci_df() -> pd.DataFrame:
    return muat_data.muat_titik_kunci()


@st.cache_data(show_spinner=False)
def portwatch_df() -> pd.DataFrame:
    return muat_data.muat_portwatch()


@st.cache_data(show_spinner=False)
def portwatch_ringkas_df() -> pd.DataFrame:
    return muat_data.muat_portwatch_ringkas()


@st.cache_data(show_spinner=False)
def sampel_df() -> pd.DataFrame:
    return analisis.perkaya(muat_data.muat_sampel(), pelabuhan_df())


def ambil_live(durasi: int) -> tuple[pd.DataFrame, str, str]:
    """Mendengarkan aliran AIS selama ``durasi`` detik. Hasilnya disimpan di session_state agar
    pergantian filter tidak memicu pendengaran ulang; tekan Refresh untuk snapshot baru."""
    cache_statis = st.session_state.setdefault("cache_statis", {})
    with st.spinner(f"Mendengarkan aisstream.io selama {durasi} detik..."):
        df, sumber, pesan = muat_data.muat_live_atau_sampel(ais.ambil_api_key(), durasi, cache_statis)
    df = analisis.perkaya(df, pelabuhan_df())
    st.session_state["snapshot_live"] = (df, sumber, pesan)
    if sumber == "live":
        tambah_ke_jejak_sesi(df)
    return df, sumber, pesan


def tambah_ke_jejak_sesi(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Mode live: kumpulkan snapshot yang pernah dilihat agar heatmap punya jejak."""
    jejak = st.session_state.get("jejak_live")
    if jejak is None or jejak.empty:
        jejak = snapshot
    elif snapshot["waktu_snapshot"].iloc[0] not in set(jejak["waktu_snapshot"].unique()):
        jejak = pd.concat([jejak, snapshot], ignore_index=True)
        waktu = sorted(jejak["waktu_snapshot"].unique())
        if len(waktu) > MAKS_SNAPSHOT_SESI:
            jejak = jejak[jejak["waktu_snapshot"].isin(waktu[-MAKS_SNAPSHOT_SESI:])]
    st.session_state["jejak_live"] = jejak
    return jejak


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🚢 Strait Watch")
    st.caption("The world's busiest chokepoint, live.")

    sumber_pilihan = st.radio(
        "Data source",
        ["Live (aisstream.io)", "Offline sample"],
        help="Live mendengarkan aliran AIS aisstream.io selama beberapa detik (perlu kunci API gratis). "
             "Sampel offline adalah rekaman yang disertakan dalam repositori.",
    )
    ada_kunci = bool(ais.ambil_api_key())
    if sumber_pilihan.startswith("Live") and not ada_kunci:
        kunci_manual = st.text_input("aisstream.io API key", type="password",
                                     help="Gratis: masuk dengan akun GitHub di aisstream.io, lalu buat kunci. "
                                          "Kunci hanya disimpan di sesi browser ini.")
        if kunci_manual.strip():
            os.environ["AISSTREAM_API_KEY"] = kunci_manual.strip()
            ada_kunci = True
    durasi = st.slider("Listen duration (s)", 10, 60, ais.DURASI_DEFAULT, 5,
                       help="Makin lama mendengarkan, makin banyak kapal (terutama yang berlabuh) yang sempat melapor.",
                       disabled=not sumber_pilihan.startswith("Live"))
    kol_a, kol_b = st.columns(2)
    refresh = kol_a.button("🔄 Refresh", use_container_width=True, help="Dengarkan aliran lagi dan ambil snapshot baru.")
    if kol_b.button("🧹 Clear trail", use_container_width=True, help="Kosongkan jejak yang terkumpul di mode live."):
        st.session_state.pop("jejak_live", None)

    pelabuhan = pelabuhan_df()
    titik_kunci = titik_kunci_df()
    if sumber_pilihan.startswith("Live"):
        if refresh or "snapshot_live" not in st.session_state:
            terkini, sumber, pesan = ambil_live(durasi)
        else:
            terkini, sumber, pesan = st.session_state["snapshot_live"]
        if sumber == "live":
            jejak = st.session_state.get("jejak_live", terkini)
            terkini = muat_data.posisi_terakhir(jejak, JENDELA_MENIT)
        else:
            jejak = sampel_df()
            terkini = muat_data.posisi_terakhir(jejak)
    else:
        jejak = sampel_df()
        terkini = muat_data.posisi_terakhir(jejak)
        sumber, pesan = "sampel", "Sampel offline dari repositori."

    terkini = analisis.hanya_kapal(terkini)
    jejak = analisis.hanya_kapal(jejak)

    st.divider()
    st.subheader("Filter")
    kategori_opsi = [k for k in km.URUTAN_KATEGORI if k in set(terkini["kategori"])]
    kategori_pilih = st.multiselect("Ship type", kategori_opsi, default=[])
    bendera_opsi = analisis.hitung_unik(terkini, "bendera")["bendera"].tolist()
    bendera_pilih = st.multiselect("Flag state", bendera_opsi, default=[])
    hanya_indonesia = st.checkbox("Indonesian flag only", value=False)
    sembunyikan_diam = st.checkbox("Hide anchored / moored ships", value=False)
    sog_maks = int(max(25, (terkini["sog_knot"].max() if terkini["sog_knot"].notna().any() else 25)) + 1)
    rentang_sog = st.slider("Speed (knot)", 0, sog_maks, (0, sog_maks))

    st.divider()
    mode_belajar = st.toggle("🎓 Learning mode", value=False, help="Tampilkan penjelasan konsep di setiap bagian.")
    st.caption(
        "Data: [aisstream.io](https://aisstream.io) · peta dasar Esri. Posisi kapal berasal dari penerima AIS "
        "sukarelawan; kapal tanpa AIS (sebagian kapal perang, kapal kecil) tidak terlihat."
    )


def terapkan_filter(df: pd.DataFrame) -> pd.DataFrame:
    hasil = df
    if kategori_pilih:
        hasil = hasil[hasil["kategori"].isin(kategori_pilih)]
    if bendera_pilih:
        hasil = hasil[hasil["bendera"].isin(bendera_pilih)]
    if hanya_indonesia:
        hasil = hasil[hasil["bendera"] == "Indonesia"]
    if sembunyikan_diam:
        hasil = hasil[~hasil["fase"].isin(["Berlabuh jangkar", "Tertambat", "Diam"])]
    lo, hi = rentang_sog
    if (lo, hi) != (0, sog_maks):
        hasil = hasil[pd.to_numeric(hasil["sog_knot"], errors="coerce").fillna(0).between(lo, hi)]
    return hasil


terkini_f = terapkan_filter(terkini)
jejak_f = terapkan_filter(jejak)

# ------------------------------------------------------------------ judul & KPI
st.title("Strait Watch")
st.markdown(
    "Sekitar **seperempat perdagangan dunia** dan sebagian besar impor minyak Asia Timur melewati "
    "Selat Malaka, jalur sempit antara Sumatera dan Semenanjung Malaya. Setiap ikon di bawah adalah satu "
    "kapal yang memancarkan sinyal AIS dan tertangkap jaringan penerima publik. Warna menunjukkan jenis kapal, "
    "arah ikon mengikuti haluan, garis tepi teal menandai bendera Indonesia."
)

info = muat_data.info_sampel(jejak)
if sumber == "live":
    st.success(f"🟢 {pesan} Peta menampilkan posisi terakhir {len(terkini)} kapal yang terdengar sejak "
               f"{fmt_wib(info['mulai'])}; tekan Refresh untuk menambah.")
elif sumber_pilihan.startswith("Live"):
    st.warning(f"🟠 {pesan}")
else:
    st.info(
        f"📼 Sampel offline: posisi terakhir {info['kapal']} kapal dari {info['snapshot']} snapshot per menit, "
        f"{fmt_wib(info['mulai'])} sampai {fmt_wib(info['selesai'])}."
    )
st.caption("ℹ️ Penerima AIS darat aisstream.io di kawasan ini masih jarang, sehingga peta live terutama menangkap kapal di "
           "sekitar Singapura dan Batam. Untuk lalu lintas seluruh selat, buka halaman **📈 Strait traffic** (AIS satelit).")

ringkas = analisis.ringkasan(terkini_f)
k1, k2, k3, k4, k5, k6 = st.columns([1, 1.2, 1, 1, 1.3, 1.3])
k1.metric("Kapal terdeteksi", ringkas["total"])
k2.metric("Bendera Indonesia", f"{ringkas['persen_indonesia']}%", f"{ringkas['indonesia']} kapal", delta_color="off")
k3.metric("Tanker", ringkas["tanker"])
k4.metric("Kargo", ringkas["kargo"])
k5.metric("Bergerak / berlabuh", f"{ringkas['bergerak']} / {ringkas['berlabuh']}")
k6.metric("Bendera teratas", ringkas["bendera_teratas"], f"{ringkas['jumlah_bendera']} negara", delta_color="off")

if mode_belajar:
    with st.expander("🎓 Apa itu AIS dan dari mana angka ini berasal?", expanded=True):
        st.markdown(
            """
            **AIS** (Automatic Identification System) adalah pemancar radio VHF yang wajib dipasang pada kapal
            niaga di atas 300 GT dan semua kapal penumpang (konvensi SOLAS). Setiap 2–10 detik kapal yang bergerak
            menyiarkan posisi GPS, kecepatan (SOG), haluan (COG), dan status navigasi; setiap 6 menit ia menyiarkan
            data statis: nama, tipe kapal, tujuan, dan ukuran. Sinyalnya tidak terenkripsi, sehingga penerima
            murah di pantai dapat menangkapnya.

            **aisstream.io** mengumpulkan sinyal dari ribuan penerima sukarelawan dan menyiarkannya ulang
            lewat WebSocket. Tidak ada endpoint "ambil semua kapal sekarang": aplikasi ini **mendengarkan aliran
            selama beberapa detik** (`src/ais.py`), menyimpan posisi terakhir setiap MMSI, lalu:

            1. menggabungkan posisi dengan data statis yang pernah diterima (`ke_dataframe`),
            2. menebak **negara bendera** dari tiga digit pertama MMSI (`src/mmsi.py`, standar ITU-R M.585),
            3. mengelompokkan **tipe kapal** dari kode AIS 0–99 (kargo 70–79, tanker 80–89, dan seterusnya),
            4. menandai **fase** dari kecepatan dan status navigasi (`src/analisis.py`).

            Karena pesan statis hanya datang tiap 6 menit, pada pendengaran 20 detik sebagian kapal masih
            "Tidak diketahui" tipenya. Tekan **Refresh** beberapa kali: data statis disimpan antar snapshot
            sehingga peta makin lama makin lengkap. Tanpa kunci API, aplikasi memakai sampel offline.
            """
        )

# Navigasi memakai segmented control, bukan st.tabs: tab tersembunyi berukuran 0 piksel
# membuat Leaflet (terutama HeatMap) gagal menggambar peta kedua. Hanya satu halaman dirender.
HALAMAN = ["🚢 Live map", "📈 Strait traffic", "🔥 Traffic heatmap", "👑 Who rules the strait", "⚓ Chokepoints & bases",
           "📋 Data & sources", "🧭 How it works"]
H_PETA, H_TRANSIT, H_HEAT, H_SIAPA, H_CHOKE, H_DATA, H_CARA = HALAMAN
halaman = st.segmented_control("Halaman", HALAMAN, default=HALAMAN[0], label_visibility="collapsed")
if halaman is None:
    halaman = H_PETA

# ------------------------------------------------------------------ halaman peta
if halaman == H_PETA:
    if terkini_f.empty:
        st.warning("Tidak ada kapal yang lolos filter.")
    else:
        pusat, zoom = peta.pusat_dan_zoom(terkini_f)
        m = peta.peta_kapal(terkini_f, pelabuhan, titik_kunci, pusat=pusat, zoom=zoom)
        st_folium(m, use_container_width=True, height=580, returned_objects=[], key="peta_kapal", center=pusat, zoom=zoom)
        legenda = " · ".join(
            f"<span style='color:{w};font-weight:700'>■</span> {k}"
            for k, w in peta.WARNA_KATEGORI.items() if k in set(terkini_f["kategori"])
        )
        st.markdown(
            f"<div style='font-size:13px'>{legenda} · <span style='color:#fff'>●</span> pelabuhan · "
            f"<span style='color:{TEAL}'>◉</span> pangkalan AL · <span style='color:#f2b705'>◌</span> titik kunci selat · "
            f"garis tepi <span style='color:{TEAL}'>teal</span> = bendera Indonesia</div>",
            unsafe_allow_html=True,
        )
        st.caption("Klik ikon untuk detail: nama, MMSI, tipe, tujuan, kecepatan, status, pelabuhan terdekat. "
                   "Ikon bulat = kapal tanpa data haluan (biasanya sedang berlabuh).")

    if mode_belajar:
        with st.expander("🎓 Bagaimana ikon kapal diputar sesuai haluan?"):
            st.markdown(
                """
                Folium tidak punya marker berbentuk kapal, jadi `src/peta.py` membuat **DivIcon**: potongan HTML
                berisi SVG lambung kapal dengan gaya `transform: rotate(<arah>deg)`. Kolom `arah` dipilih di
                `analisis.perkaya`: **COG** (course over ground, arah gerak sebenarnya) saat kapal bergerak,
                dan **heading** (arah haluan kapal) saat ia diam, karena COG kapal yang berlabuh berubah-ubah
                mengikuti arus dan angin.

                ```python
                svg = f'<svg ... style="transform: rotate({arah:.0f}deg)"><path d="M12 1.5 L17.5 9 ..." fill="{warna}"/></svg>'
                folium.DivIcon(html=svg, icon_size=(16, 16), icon_anchor=(8, 8))
                ```
                Nilai khusus AIS perlu dibuang lebih dulu: COG 360 dan heading 511 berarti "tidak tersedia",
                bukan arah. Kapal tanpa arah digambar sebagai lingkaran.
                """
            )

# ------------------------------------------------------------------ halaman transit harian
if halaman == H_TRANSIT:
    pw = portwatch_df()
    if pw.empty:
        st.warning("Data PortWatch belum tersedia. Jalankan `python scripts/perbarui_portwatch.py`.")
    else:
        st.markdown(
            "Peta live hanya melihat kapal yang tertangkap penerima darat. Untuk gambaran utuh, halaman ini memakai "
            "**IMF PortWatch**: hitungan kapal yang melintasi setiap selat per hari, dari AIS **satelit**, sejak 2019. "
            f"Data terakhir: **{pw['tanggal'].max():%d %b %Y}** (PortWatch terbit dengan jeda beberapa hari)."
        )
        id_ke_nama = {k: v["nama"] for k, v in portwatch.SELAT.items() if k in set(pw["portid"])}
        t1, t2, t3 = st.columns([1.4, 1, 1])
        pilih_id = t1.selectbox("Strait", list(id_ke_nama), format_func=lambda k: f"{id_ke_nama[k]} · {portwatch.SELAT[k]['alki']}"
                                if portwatch.SELAT[k]["grup"] == "Indonesia" else id_ke_nama[k])
        jendela = t2.select_slider("Moving average (days)", [7, 14, 30, 60, 90], value=30)
        rentang = t3.selectbox("Range", ["1 tahun", "2 tahun", "Semua (sejak 2019)"], index=2)
        tr = portwatch.tren(pw, pilih_id, jendela)
        if rentang != "Semua (sejak 2019)":
            tahun = int(rentang.split()[0])
            tr = tr[tr["tanggal"] >= tr["tanggal"].max() - pd.DateOffset(years=tahun)]

        akhir = tr.tail(30)
        setahun_lalu = pw[(pw["portid"] == pilih_id)
                          & pw["tanggal"].between(tr["tanggal"].max() - pd.Timedelta(days=394), tr["tanggal"].max() - pd.Timedelta(days=365))]
        m1, m2, m3, m4 = st.columns(4)
        rata30 = akhir["n_total"].mean()
        m1.metric("Kapal per hari (30 hari)", f"{rata30:,.0f}",
                  f"{(rata30 / setahun_lalu['n_total'].mean() - 1) * 100:+.1f}% vs tahun lalu" if not setahun_lalu.empty else None)
        m2.metric("Tanker per hari", f"{akhir['n_tanker'].mean():,.0f}", f"{100 * akhir['n_tanker'].sum() / max(akhir['n_total'].sum(), 1):.0f}% dari total", delta_color="off")
        m3.metric("Kapasitas per hari", f"{akhir['capacity'].mean() / 1e6:,.1f} jt DWT")
        m4.metric("Rekor harian", f"{tr['n_total'].max():,.0f}", f"{tr.loc[tr['n_total'].idxmax(), 'tanggal']:%d %b %Y}", delta_color="off")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=tr["tanggal"], y=tr["n_total"], mode="lines", name="Harian",
                                 line=dict(color="#3a4a5e", width=1), hovertemplate="%{x|%d %b %Y}: %{y} kapal<extra></extra>"))
        fig.add_trace(go.Scatter(x=tr["tanggal"], y=tr["rata_bergerak"], mode="lines", name=f"Rata-rata {jendela} hari",
                                 line=dict(color=TEAL, width=2.5), hovertemplate="%{x|%d %b %Y}: %{y:.0f} kapal<extra></extra>"))
        tanker_rb = tr["n_tanker"].rolling(jendela, min_periods=max(1, jendela // 2)).mean()
        fig.add_trace(go.Scatter(x=tr["tanggal"], y=tanker_rb, mode="lines", name=f"Tanker ({jendela} hari)",
                                 line=dict(color=MERAH, width=2), hovertemplate="%{x|%d %b %Y}: %{y:.0f} tanker<extra></extra>"))
        fig.update_layout(template=TEMPLATE, title=f"Transit harian {id_ke_nama[pilih_id]}", height=420,
                          margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
                          yaxis_title="kapal per hari", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        if pilih_id == "chokepoint5":
            st.caption("⚠️ Angka Selat Malaka naik sekitar 30% dalam satu bulan pada November 2021, sementara selat lain tidak. "
                       "Lompatan setajam itu lebih mungkin berasal dari perubahan cakupan atau cara penghitungan PortWatch "
                       "daripada lonjakan lalu lintas sungguhan, jadi perbandingan sebelum dan sesudah 2022 perlu dibaca hati-hati.")

        c1, c2 = st.columns(2)
        bd = portwatch.bandingkan(pw, 365)
        warna_bd = [TEAL if g == "Indonesia" else ABU for g in bd["grup"]]
        bd["label"] = [f"{s_} · {a}" if g == "Indonesia" else s_ for s_, g, a in zip(bd["selat"], bd["grup"], bd["alki"])]
        fig_bd = grafik_batang(bd, "rata_harian", "label", "Rata-rata kapal per hari, 365 hari terakhir", warna=warna_bd,
                               hover="persen_tanker", satuan="kapal/hari")
        fig_bd.update_traces(hovertemplate="<b>%{y}</b><br>%{x} kapal per hari<br>tanker %{customdata}%<extra></extra>")
        fig_bd.update_xaxes(title="kapal per hari")
        c1.plotly_chart(fig_bd, use_container_width=True)
        kp = portwatch.komposisi(pw, pilih_id, 365)
        warna_jenis = {"Tanker": MERAH, "Kontainer": "#4cc9f0", "Curah kering": "#f2b705", "Kargo umum": "#c77dff", "Ro-Ro": "#80ed99"}
        fig_kp = grafik_batang(kp, "kapal", "jenis", f"Jenis kapal di {id_ke_nama[pilih_id]}, 365 hari terakhir",
                               warna=[warna_jenis.get(j, ABU) for j in kp["jenis"]], hover="persen", satuan="transit")
        c2.plotly_chart(fig_kp, use_container_width=True)
        st.caption("Teal = selat di perairan Indonesia. Selat Malaka bukan ALKI: ia selat internasional yang dikelola bersama "
                   "Indonesia, Malaysia, dan Singapura. Sunda (ALKI I), Lombok dan Makassar (ALKI II), serta Ombai (ALKI III) "
                   "adalah jalur alternatif yang ditetapkan Indonesia.")

        c3, c4 = st.columns(2)
        with c3:
            st.subheader("Unusual days")
            an = portwatch.anomali(pw, pilih_id)
            if an.empty:
                st.write("Tidak ada hari yang menyimpang ≥ 2,5 simpangan baku dari 28 hari sebelumnya.")
            else:
                an = an.sort_values("tanggal", ascending=False).head(12)
                an["tanggal"] = an["tanggal"].dt.strftime("%d %b %Y")
                st.dataframe(an.rename(columns={"tanggal": "Tanggal", "n_total": "Kapal", "n_tanker": "Tanker", "z": "z-score"})
                             [["Tanggal", "Kapal", "Tanker", "z-score"]], use_container_width=True, hide_index=True)
        with c4:
            st.subheader("Average per year")
            pt = portwatch.per_tahun(pw[pw["portid"] == pilih_id])
            st.dataframe(pt.rename(columns={"tahun": "Tahun", "rata_harian": "Kapal/hari", "hari": "Hari data"})
                         [["Tahun", "Kapal/hari", "Hari data"]], use_container_width=True, hide_index=True)

    if mode_belajar:
        with st.expander("🎓 AIS darat vs AIS satelit, dan apa itu 'transit'"):
            st.markdown(
                """
                Penerima AIS di darat hanya menjangkau 40–70 km dari pantai, dan jumlahnya tidak merata. **Satelit**
                menangkap sinyal AIS dari orbit, sehingga cakupannya merata di tengah laut, tetapi datanya mahal dan
                biasanya tidak dibuka secara live. IMF PortWatch membeli data satelit tersebut lalu membuka
                **hasil olahannya**: berapa kapal yang **melintasi** garis batas setiap selat per hari.

                Satu "transit" = satu kapal yang masuk dari satu sisi dan keluar dari sisi lain. Kapal yang berlabuh di
                selat tidak dihitung, jadi angka ini mengukur **lalu lintas lewat**, bukan kepadatan.

                Hari yang tidak biasa dicari dengan z-score yang sama seperti mendeteksi lonjakan harga:

                ```python
                acuan = d["n_total"].shift(1).rolling(28)          # 28 hari sebelumnya, tanpa hari ini
                d["z"] = (d["n_total"] - acuan.mean()) / acuan.std()
                ```
                `shift(1)` penting: tanpa itu, hari yang sedang diuji ikut membentuk "kebiasaan"-nya sendiri.
                """
            )

# ------------------------------------------------------------------ halaman heatmap
if halaman == H_HEAT:
    info_jejak = muat_data.info_sampel(jejak_f)
    if sumber == "live" and info_jejak["snapshot"] < 3:
        st.info(
            f"Jejak live baru {info_jejak['snapshot']} snapshot. Tekan **Refresh** beberapa kali agar jejak terkumpul, "
            "atau beralih ke **Offline sample** untuk melihat heatmap dari rekaman penuh."
        )
    kh1, kh2, kh3 = st.columns(3)
    ukuran_sel = kh1.select_slider("Ukuran sel kepadatan (derajat)", [0.1, 0.25, 0.5], value=0.25)
    radius_heat = kh2.slider("Radius heatmap", 4, 24, 9)
    jumlah_sel = kh3.slider("Sel terpadat ditandai", 0, 10, 5)
    grid = analisis.grid_kepadatan(jejak_f, ukuran_sel)
    teratas = grid.head(jumlah_sel).copy()
    if not teratas.empty:
        teratas["label"] = [analisis.label_lokasi(a, b, pelabuhan, titik_kunci)
                            for a, b in zip(teratas["lat_tengah"], teratas["lon_tengah"])]
    if jejak_f.empty:
        st.warning("Tidak ada jejak yang lolos filter.")
    else:
        pusat2, zoom2 = peta.pusat_dan_zoom(jejak_f)
        m2 = peta.peta_heatmap(jejak_f, pelabuhan, titik_kunci, teratas if jumlah_sel else None,
                               radius=radius_heat, blur=radius_heat + 4, pusat=pusat2, zoom=zoom2)
        st_folium(m2, use_container_width=True, height=580, returned_objects=[], key="peta_heatmap", center=pusat2, zoom=zoom2)
    st.caption(
        f"Heatmap dibangun dari {info_jejak['baris']:,} posisi, {info_jejak['snapshot']} snapshot, "
        f"{info_jejak['kapal']} kapal unik ({fmt_wib(info_jejak['mulai'])} – {fmt_wib(info_jejak['selesai'])})."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Busiest grid cells")
        if teratas.empty:
            st.write("-")
        else:
            tampil = teratas.rename(columns={"label": "Lokasi", "kapal": "Kapal unik", "titik": "Posisi terekam",
                                             "lat_tengah": "Lat", "lon_tengah": "Lon"})
            st.dataframe(tampil[["Lokasi", "Kapal unik", "Posisi terekam", "Lat", "Lon"]],
                         use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Longest trails")
        pj = analisis.panjang_jejak_km(jejak_f)
        if pj.empty:
            st.write("Perlu minimal 2 snapshot.")
        else:
            st.dataframe(pj.rename(columns={"label": "Kapal", "kategori": "Tipe", "segmen": "Segmen", "km": "Jarak (km)"})
                         [["Kapal", "Tipe", "Segmen", "Jarak (km)"]], use_container_width=True, hide_index=True)

    if mode_belajar:
        with st.expander("🎓 Mengapa heatmap bisa menggambar 'jalur' padahal datanya hanya titik?"):
            st.markdown(
                """
                Satu snapshot hanya berisi **posisi sesaat**. Namun jika snapshot direkam setiap 60 detik selama
                10 menit, sebuah kapal kontainer berkecepatan 20 knot (37 km/jam) meninggalkan 10 titik sepanjang
                sekitar 6 km. Ratusan kapal yang melakukan hal yang sama menggambar **traffic separation scheme**
                (jalur satu arah ke tenggara dan ke barat laut) dengan sendirinya; heatmap hanya "menyalakan" tempat
                yang banyak titiknya.

                **Grid kepadatan** (`grid_kepadatan` di `src/analisis.py`) bekerja lebih sederhana lagi: koordinat
                dibulatkan ke bawah ke kelipatan ukuran sel, lalu dihitung per sel.

                ```python
                g["lat_sel"] = np.floor(g["lat"] / ukuran_deg)
                g["lon_sel"] = np.floor(g["lon"] / ukuran_deg)
                agg = g.groupby(["lat_sel", "lon_sel"]).agg(titik=("mmsi", "size"), kapal=("mmsi", "nunique"))
                ```
                Dua ukuran berbeda: `titik` menghitung semua posisi (kapal yang berlabuh berbulan-bulan akan
                menumpuk), sedangkan `kapal` menghitung kapal unik (MMSI). Area labuh jangkar di Singapura
                menang di `titik`, jalur pelayaran menang di `kapal`.
                """
            )

# ------------------------------------------------------------------ halaman siapa yang menguasai
if halaman == H_SIAPA:
    if terkini_f.empty:
        st.warning("Tidak ada kapal yang lolos filter.")
    else:
        g1, g2 = st.columns(2)
        per_bendera = analisis.hitung_unik(terkini_f, "bendera", 14)
        warna_b = [TEAL if b == "Indonesia" else (ABU if b == km.TIDAK_DIKETAHUI else "#4cc9f0") for b in per_bendera["bendera"]]
        g1.plotly_chart(grafik_batang(per_bendera, "kapal", "bendera", "Negara bendera (snapshot terkini)",
                                      warna=warna_b, hover="persen"), use_container_width=True)
        per_kategori = analisis.hitung_unik(terkini_f, "kategori")
        g2.plotly_chart(grafik_batang(per_kategori, "kapal", "kategori", "Jenis kapal (snapshot terkini)",
                                      warna=[peta.warna_kategori(k) for k in per_kategori["kategori"]], hover="persen"),
                        use_container_width=True)
        st.caption("Teal = Indonesia. Bendera ditebak dari tiga digit pertama MMSI, jadi 'Panama', 'Liberia', dan "
                   "'Kepulauan Marshall' adalah bendera kemudahan: pemiliknya bisa dari negara mana saja.")

        g3, g4 = st.columns(2)
        per_fase = analisis.hitung_unik(terkini_f, "fase")
        g3.plotly_chart(grafik_batang(per_fase, "kapal", "fase", "Fase pelayaran", hover="persen"), use_container_width=True)
        sog = pd.to_numeric(terkini_f.drop_duplicates("mmsi")["sog_knot"], errors="coerce").dropna()
        fig_sog = px.histogram(sog, nbins=25, template=TEMPLATE, title="Sebaran kecepatan (knot)",
                               color_discrete_sequence=[TEAL])
        fig_sog.update_layout(showlegend=False, xaxis_title="knot", yaxis_title="kapal", bargap=0.08,
                              margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", height=360)
        fig_sog.update_traces(hovertemplate="%{x} knot<br>%{y} kapal<extra></extra>")
        g4.plotly_chart(fig_sog, use_container_width=True)

        g5, g6 = st.columns(2)
        tujuan = terkini_f.drop_duplicates("mmsi")
        tujuan = tujuan[tujuan["tujuan"].fillna("").astype(str).str.strip() != ""]
        per_tujuan = analisis.hitung_unik(tujuan, "tujuan", 12)
        if per_tujuan.empty:
            g5.info("Belum ada kapal yang mengirim tujuan (pesan statis datang tiap 6 menit).")
        else:
            g5.plotly_chart(grafik_batang(per_tujuan, "kapal", "tujuan", "Tujuan yang dilaporkan (AIS)", hover="persen"),
                            use_container_width=True)
        indo = terkini_f[terkini_f["bendera"] == "Indonesia"]
        per_kat_indo = analisis.hitung_unik(indo, "kategori")
        if per_kat_indo.empty:
            g6.info("Tidak ada kapal berbendera Indonesia yang lolos filter.")
        else:
            g6.plotly_chart(grafik_batang(per_kat_indo, "kapal", "kategori", "Kapal berbendera Indonesia menurut jenis",
                                          warna=[peta.warna_kategori(k) for k in per_kat_indo["kategori"]], hover="persen"),
                            use_container_width=True)
        st.caption("Tujuan diketik manual oleh awak kapal, sehingga ejaannya beragam (SINGAPORE, SG SIN, S'PORE).")

    if mode_belajar:
        with st.expander("🎓 Mengapa menghitung kapal unik, bukan baris, dan apa itu bendera kemudahan?"):
            st.markdown(
                """
                Dalam jejak, satu kapal muncul di banyak snapshot. Jika yang dihitung adalah **baris**, kapal yang
                berlabuh berminggu-minggu akan terlihat seperti puluhan kapal. Karena itu seluruh grafik memakai
                `groupby(...)["mmsi"].nunique()`: MMSI unik per kapal, sehingga hitungannya benar-benar jumlah kapal.

                **Bendera kemudahan** (flag of convenience): pemilik kapal mendaftarkan kapalnya di negara dengan pajak
                dan aturan yang longgar. Itulah sebabnya Panama, Liberia, dan Kepulauan Marshall, tiga negara kecil
                tanpa industri pelayaran besar, hampir selalu memuncaki grafik bendera. "Siapa yang menguasai selat"
                menurut bendera bukan berarti siapa pemiliknya; data kepemilikan sebenarnya tidak ada di AIS.
                """
            )

# ------------------------------------------------------------------ halaman chokepoint & pangkalan
if halaman == H_CHOKE:
    st.markdown(
        "Siapa yang sedang berada di **titik tersempit** selat, dan apa yang ada di depan **pangkalan TNI AL**? "
        "Radius dihitung dari posisi pada snapshot terkini (setelah filter)."
    )
    radius_km = st.slider("Radius pantau (km)", 5, 60, 25, 5)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Chokepoints")
        sibuk_titik = analisis.sibuk_per_titik(terkini_f, titik_kunci, radius_km)
        st.dataframe(sibuk_titik.rename(columns={"nama": "Titik", "kapal": "Kapal", "tanker": "Tanker"})[["Titik", "Kapal", "Tanker"]],
                     use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Ports & naval bases")
        sibuk_pel = analisis.sibuk_per_titik(terkini_f, pelabuhan, radius_km)
        sibuk_pel = sibuk_pel.merge(pelabuhan[["nama", "jenis"]], on="nama", how="left")
        sibuk_pel["jenis"] = sibuk_pel["jenis"].map({"pelabuhan": "Pelabuhan", "pangkalan_al": "Pangkalan AL"})
        st.dataframe(sibuk_pel.rename(columns={"nama": "Lokasi", "negara": "Negara", "jenis": "Jenis", "kapal": "Kapal", "tanker": "Tanker"})
                     [["Lokasi", "Negara", "Jenis", "Kapal", "Tanker"]].head(15), use_container_width=True, hide_index=True)

    st.subheader("Military & law enforcement broadcasting AIS")
    militer = terkini_f[terkini_f["kategori"] == "Militer & penegak hukum"].drop_duplicates("mmsi")
    if militer.empty:
        st.write("Tidak ada kapal yang melaporkan tipe militer/penegak hukum pada snapshot ini.")
    else:
        st.dataframe(militer[["label", "bendera", "tipe", "fase", "sog_knot", "pelabuhan_terdekat", "jarak_pelabuhan_km", "mmsi"]]
                     .rename(columns={"label": "Kapal", "bendera": "Bendera", "tipe": "Tipe", "fase": "Fase", "sog_knot": "Knot",
                                      "pelabuhan_terdekat": "Dekat", "jarak_pelabuhan_km": "km", "mmsi": "MMSI"}),
                     use_container_width=True, hide_index=True)
    st.caption(
        "Kapal perang tidak wajib memancarkan AIS dan umumnya mematikannya saat operasi; yang terlihat di sini "
        "hanya kapal patroli, SAR, dan penegak hukum yang memilih untuk tampil. Tidak terlihat bukan berarti tidak ada."
    )

    if mode_belajar:
        with st.expander("🎓 Rumus haversine untuk 'kapal dalam radius X km'"):
            st.markdown(
                r"""
                Jarak lingkaran besar antara dua titik di permukaan bola berjari-jari $R$:

                $$a = \sin^2\!\left(\frac{\Delta\varphi}{2}\right) + \cos\varphi_1 \cos\varphi_2 \sin^2\!\left(\frac{\Delta\lambda}{2}\right),
                \qquad d = 2R \arcsin\sqrt{a}$$

                dengan $\varphi$ lintang dan $\lambda$ bujur dalam radian, $R = 6.371$ km. `haversine_vektor` di
                `src/analisis.py` menghitung jarak ribuan kapal ke satu titik sekaligus dengan numpy, lalu
                `kapal_di_sekitar` menyaring yang di bawah radius. Di dekat khatulistiwa 1° lintang ≈ 111 km,
                jadi radius 25 km ≈ 0,22°.
                """
            )

# ------------------------------------------------------------------ halaman data
if halaman == H_DATA:
    st.subheader("Latest snapshot")
    kolom_tampil = ["label", "mmsi", "bendera", "kategori", "tipe", "tujuan", "fase", "status_nav", "sog_knot",
                    "kecepatan_kmh", "cog", "heading", "lat", "lon", "pelabuhan_terdekat", "jarak_pelabuhan_km",
                    "panjang_m", "lebar_m", "sarat_m", "imo", "callsign", "kelas", "waktu_pesan"]
    kolom_tampil = [k for k in kolom_tampil if k in terkini_f.columns]
    st.dataframe(terkini_f[kolom_tampil].sort_values("label"), use_container_width=True, hide_index=True, height=420)
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download snapshot terkini (CSV)", terkini_f.to_csv(index=False).encode("utf-8"),
                       "snapshot_terkini.csv", "text/csv", use_container_width=True)
    d2.download_button("⬇️ Download seluruh jejak (CSV)", jejak_f.to_csv(index=False).encode("utf-8"),
                       "jejak.csv", "text/csv", use_container_width=True)

    st.subheader("Reference points")
    r1, r2 = st.columns([2, 1])
    r1.dataframe(pelabuhan, use_container_width=True, hide_index=True, height=300)
    r2.dataframe(titik_kunci[["nama", "lat", "lon"]], use_container_width=True, hide_index=True, height=300)

    st.subheader("Sources & limitations")
    st.markdown(
        f"""
        - **Posisi kapal**: [aisstream.io](https://aisstream.io), WebSocket `{ais.URL_STREAM}`, kotak batas lintang
          {ais.BBOX_SELAT['lamin']} s.d. {ais.BBOX_SELAT['lamax']}, bujur {ais.BBOX_SELAT['lomin']} s.d. {ais.BBOX_SELAT['lomax']}.
          Pesan yang dipakai: `PositionReport`, `StandardClassBPositionReport`, `ShipStaticData`. Kunci API gratis
          (masuk dengan GitHub); data untuk penggunaan non-komersial.
        - **Negara bendera**: dari Maritime Identification Digits (3 digit pertama MMSI), standar ITU-R M.585 (`src/mmsi.py`).
          MID yang tidak ada dalam daftar menjadi "Tidak diketahui".
        - **Tipe kapal**: kode AIS 0–99 (ITU-R M.1371) yang diisi sendiri oleh operator kapal; bisa salah atau kosong.
        - **Pelabuhan, pangkalan, titik kunci**: koordinat dari Wikipedia dan peta umum, dibulatkan (`data/pelabuhan.csv`,
          `data/titik_kunci.csv`). Daftar tidak lengkap; pelabuhan kecil tidak dihitung.
        - **Cakupan tidak merata.** Penerima AIS darat menjangkau sekitar 40–70 km dari pantai. Selat Singapura dan
          pantai Malaysia tercakup sangat baik; pantai timur Sumatera dan laut lepas di utara lebih tipis. Area yang
          terlihat kosong belum tentu kosong.
        - **Kapal tanpa AIS tidak terlihat**: kapal kecil di bawah 300 GT tanpa AIS kelas B, sebagian kapal perang,
          dan kapal yang sengaja mematikan pemancar ("dark ships").
        - **Disclaimer.** Seluruh data berasal dari sumber publik dan bersifat edukatif; bukan data operasional
          pelayaran dan tidak boleh dipakai untuk navigasi, pengawasan, atau keputusan keselamatan. Proyek ini
          merupakan portofolio pribadi dan tidak berafiliasi dengan aisstream.io, otoritas pelabuhan, TNI AL, atau
          operator kapal mana pun.
        """
    )

# ------------------------------------------------------------------ halaman cara kerja
if halaman == H_CARA:
    st.subheader("Data flow")
    st.graphviz_chart(
        """
        digraph G {
          rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", fillcolor="#0f1c2e",
          fontcolor="#e8ecf4", color="#2ec4b6", fontname="Helvetica"]; edge [color="#9aa5b1"];
          A [label="Kapal memancarkan AIS\\n(VHF, tiap 2-10 detik)"];
          B [label="Penerima sukarelawan\\naisstream.io"];
          C [label="WebSocket, dengarkan 20 detik\\nsrc/ais.py"];
          D [label="Posisi terakhir per MMSI\\n+ data statis (cache sesi)"];
          E [label="perkaya()\\nbendera · tipe · fase · pelabuhan terdekat\\nsrc/analisis.py"];
          F [label="Peta Folium\\nsrc/peta.py"];
          G [label="Grafik Plotly\\napp.py"];
          S [label="Sampel offline\\ndata/sample/posisi.csv", fillcolor="#2a2f3a"];
          A -> B -> C -> D -> E; S -> D; E -> F; E -> G;
        }
        """
    )
    st.markdown(
        """
        | Langkah | File | Inti |
        |---|---|---|
        | Dengarkan | `src/ais.py` | Buka WebSocket, kirim pesan langganan (kunci, kotak batas, jenis pesan), simpan posisi terakhir tiap MMSI selama N detik |
        | Rapikan | `src/ais.py` | Buang nilai "tidak tersedia" AIS (SOG 102,3; COG 360; heading 511), bersihkan nama dari karakter `@`, gabung posisi dan data statis |
        | Perkaya | `src/analisis.py` | Bendera dari MID, kategori dari kode tipe, fase dari SOG dan status navigasi, pelabuhan terdekat (haversine) |
        | Peta | `src/peta.py` | DivIcon SVG berputar sesuai COG/heading; HeatMap dari seluruh jejak; lapisan per kategori |
        | Hitung | `src/analisis.py` | Kapal unik per bendera/jenis, grid kepadatan, kapal dalam radius titik kunci dan pangkalan |
        | Rekam sampel | `scripts/rekam_sampel.py` | Mendengarkan N menit, satu posisi per kapal per bucket 60 detik, simpan ke CSV |

        **Mengapa mendengarkan, bukan meminta?** Berbeda dengan API pesawat (satu permintaan HTTP = satu snapshot),
        AIS adalah siaran. aisstream.io meneruskan setiap pesan saat tiba, sehingga "snapshot" di sini berarti
        *semua kapal yang sempat berbicara dalam N detik*. Kapal yang bergerak melapor tiap beberapa detik dan hampir
        pasti tertangkap; kapal yang berlabuh melapor tiap 3 menit, jadi sebagian baru muncul setelah beberapa kali
        Refresh. Itulah sebabnya slider **Listen duration** ada: 20 detik cukup untuk gambaran, 60 detik untuk hitungan
        yang lebih lengkap.

        **Batas aisstream.io.** Satu kunci API hanya boleh memegang satu koneksi pada satu waktu dan ditujukan untuk
        penggunaan non-komersial. Aplikasi ini menutup koneksi segera setelah N detik, dan hasilnya disimpan di sesi
        sehingga mengganti filter tidak membuka koneksi baru.
        """
    )
    if mode_belajar:
        with st.expander("🎓 Membaca MMSI: 9 digit yang menyimpan negara"):
            st.markdown(
                """
                MMSI (Maritime Mobile Service Identity) adalah nomor 9 digit yang dipakai radio kapal. Tiga digit
                pertama, **MID**, dialokasikan ITU per negara: `525` Indonesia, `533` Malaysia, `563`–`566` Singapura,
                `412`–`414` Tiongkok, `351`–`357` dan `370`–`374` Panama. Awalan khusus menandai bukan-kapal:
                `00` stasiun pantai, `99` pelampung navigasi (AtoN), `970` pemancar darurat AIS-SART.

                ```python
                def negara_bendera(mmsi):
                    s = str(mmsi)
                    if len(s) != 9 or jenis_mmsi(s) != "Kapal":
                        return "Tidak diketahui"
                    return MID_NEGARA.get(int(s[:3]), "Tidak diketahui")
                ```
                Karena ini standar terbuka, tabelnya bisa diperluas sendiri; lihat `docs/LATIHAN.md`.
                """
            )
