"""Membangun peta Folium: ikon kapal berputar sesuai haluan, pelabuhan, pangkalan, titik kunci, dan heatmap."""

from __future__ import annotations

import html
import math

import folium
import pandas as pd
from folium.plugins import HeatMap

from src import mmsi as km

PUSAT_SELAT = (2.6, 100.9)
ZOOM_AWAL = 7
TILE_GELAP = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/"
    "MapServer/tile/{z}/{y}/{x}"
)
ATRIBUSI_TILE = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, OpenStreetMap contributors"

# Warna per kategori kapal. Tanker sengaja paling mencolok (energi lewat selat ini).
WARNA_KATEGORI: dict[str, str] = {
    "Kargo": "#4cc9f0",
    "Tanker": "#ff4d6d",
    "Penumpang": "#80ed99",
    "Nelayan": "#f2b705",
    "Tunda & servis": "#c77dff",
    "Kecepatan tinggi": "#ff8c42",
    "Rekreasi": "#f6bd60",
    "Militer & penegak hukum": "#ffffff",
    km.KATEGORI_LAIN: "#9aa5b1",
    km.TIDAK_DIKETAHUI: "#5c6b7a",
}
WARNA_INDONESIA = "#2ec4b6"

# Bentuk kapal sederhana (lambung + haluan runcing), menghadap ke atas = utara, viewBox 24x24.
_JALUR_KAPAL = "M12 1.5 L17.5 9 L17.5 20.5 Q12 23 6.5 20.5 L6.5 9 Z"


def warna_kategori(kategori: str | None) -> str:
    return WARNA_KATEGORI.get(kategori or km.TIDAK_DIKETAHUI, WARNA_KATEGORI[km.KATEGORI_LAIN])


def ikon_kapal(warna: str, arah: float | None, ukuran: int = 16, garis: str = "#111") -> folium.DivIcon:
    """DivIcon SVG kapal yang diputar ``arah`` derajat searah jarum jam; tanpa arah digambar sebagai titik."""
    if arah is None or pd.isna(arah):
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{ukuran}" height="{ukuran}" viewBox="0 0 24 24">'
            f'<circle cx="12" cy="12" r="6" fill="{warna}" stroke="{garis}" stroke-width="1.2"/></svg>'
        )
    else:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{ukuran}" height="{ukuran}" viewBox="0 0 24 24" '
            f'style="transform: rotate({float(arah):.0f}deg); filter: drop-shadow(0 0 2px #000);">'
            f'<path d="{_JALUR_KAPAL}" fill="{warna}" stroke="{garis}" stroke-width="1.2"/></svg>'
        )
    return folium.DivIcon(html=svg, icon_size=(ukuran, ukuran), icon_anchor=(ukuran // 2, ukuran // 2))


def _teks(v, satuan: str = "", desimal: int = 0) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return "-"
    try:
        return f"{float(v):,.{desimal}f}{satuan}"
    except (TypeError, ValueError):
        return f"{v}{satuan}"


def _isi(v):
    """Nilai apa adanya, atau None kalau kosong/NaN (NaN itu truthy, jadi `or` biasa tidak cukup)."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    return v


def popup_kapal(b: pd.Series) -> str:
    """HTML popup untuk satu kapal."""
    label = html.escape(str(_isi(b.get("label")) or _isi(b.get("nama")) or f"MMSI {b.get('mmsi')}"))
    bendera = html.escape(str(b.get("bendera", "")))
    tipe = html.escape(str(b.get("tipe", "")))
    tujuan = html.escape(str(_isi(b.get("tujuan")) or "-"))
    pelabuhan = _isi(b.get("pelabuhan_terdekat"))
    baris_pelabuhan = (
        f"<tr><td>Pelabuhan terdekat</td><td>{html.escape(str(pelabuhan))} ({_teks(b.get('jarak_pelabuhan_km'), ' km')})</td></tr>"
        if pelabuhan else ""
    )
    dimensi = ""
    if b.get("panjang_m") and not pd.isna(b.get("panjang_m")):
        dimensi = f"<tr><td>Ukuran</td><td>{_teks(b.get('panjang_m'), ' m')} × {_teks(b.get('lebar_m'), ' m')}, sarat {_teks(b.get('sarat_m'), ' m', 1)}</td></tr>"
    imo = b.get("imo")
    baris_imo = f"<tr><td>IMO</td><td>{int(imo)}</td></tr>" if imo and not pd.isna(imo) else ""
    return f"""
    <div style="font-family: system-ui, sans-serif; font-size: 13px; min-width: 230px;">
      <div style="font-size: 16px; font-weight: 700;">{label}</div>
      <div style="color:#555; margin-bottom:6px;">{tipe} · bendera {bendera}</div>
      <table style="border-collapse: collapse; width:100%;">
        <tr><td>MMSI</td><td><code>{html.escape(str(b.get('mmsi', '')))}</code></td></tr>
        {baris_imo}
        <tr><td>Tujuan (AIS)</td><td>{tujuan}</td></tr>
        <tr><td>Status</td><td>{html.escape(str(b.get('status_nav', '')))} · {html.escape(str(b.get('fase', '')))}</td></tr>
        <tr><td>Kecepatan</td><td>{_teks(b.get('sog_knot'), ' knot', 1)} ({_teks(b.get('kecepatan_kmh'), ' km/jam')})</td></tr>
        <tr><td>Haluan (COG)</td><td>{_teks(b.get('cog'), '°')}</td></tr>
        {dimensi}
        {baris_pelabuhan}
      </table>
    </div>
    """


def peta_dasar(pusat=PUSAT_SELAT, zoom: int = ZOOM_AWAL) -> folium.Map:
    """Peta gelap (Esri World Dark Gray) agar ikon berwarna terlihat jelas."""
    m = folium.Map(location=pusat, zoom_start=zoom, tiles=None, control_scale=True)
    folium.TileLayer(tiles=TILE_GELAP, attr=ATRIBUSI_TILE, name="Peta dasar gelap", control=False, max_zoom=16).add_to(m)
    return m


def tambah_pelabuhan(m: folium.Map, pelabuhan: pd.DataFrame) -> None:
    """Pelabuhan (lingkaran putih) dan pangkalan AL (kotak kecil teal) dalam dua lapisan terpisah."""
    fg_p = folium.FeatureGroup(name="Pelabuhan", show=True)
    fg_b = folium.FeatureGroup(name="Pangkalan AL", show=True)
    for _, b in pelabuhan.iterrows():
        pangkalan = b.get("jenis") == "pangkalan_al"
        folium.CircleMarker(
            location=(b["lat"], b["lon"]), radius=5 if pangkalan else 4,
            color=WARNA_INDONESIA if pangkalan else "#ffffff", weight=2 if pangkalan else 1,
            fill=True, fill_color="#07111f" if pangkalan else "#ffffff", fill_opacity=0.9,
            tooltip=f"{'⚓ ' if pangkalan else ''}{b['nama']} ({b['negara']})",
        ).add_to(fg_b if pangkalan else fg_p)
    fg_p.add_to(m)
    fg_b.add_to(m)


def tambah_titik_kunci(m: folium.Map, titik: pd.DataFrame) -> None:
    """Chokepoint dan pintu selat sebagai lingkaran putus-putus beradius 15 km."""
    fg = folium.FeatureGroup(name="Titik kunci selat", show=True)
    for _, t in titik.iterrows():
        folium.Circle(
            location=(t["lat"], t["lon"]), radius=15_000, color="#f2b705", weight=1.5, dash_array="6 6",
            fill=False, tooltip=f"{t['nama']}: {t['keterangan']}",
        ).add_to(fg)
    fg.add_to(m)


def peta_kapal(df: pd.DataFrame, pelabuhan: pd.DataFrame | None = None, titik_kunci: pd.DataFrame | None = None,
               pusat=PUSAT_SELAT, zoom: int = ZOOM_AWAL, sorot_indonesia: bool = True) -> folium.Map:
    """Peta dengan satu ikon per kapal, diwarnai per kategori dan diputar sesuai haluan."""
    m = peta_dasar(pusat, zoom)
    if titik_kunci is not None and not titik_kunci.empty:
        tambah_titik_kunci(m, titik_kunci)
    if pelabuhan is not None and not pelabuhan.empty:
        tambah_pelabuhan(m, pelabuhan)

    lapisan: dict[str, folium.FeatureGroup] = {}
    for _, b in df.iterrows():
        # NaN itu truthy: tanpa _isi, kapal berkategori kosong masuk lapisan "nan" yang tidak pernah digambar.
        kategori = _isi(b.get("kategori")) or km.TIDAK_DIKETAHUI
        if kategori not in km.URUTAN_KATEGORI:
            kategori = km.TIDAK_DIKETAHUI
        label = _isi(b.get("label")) or _isi(b.get("nama")) or f"MMSI {b.get('mmsi')}"
        indo = b.get("bendera") == "Indonesia"
        garis = WARNA_INDONESIA if (indo and sorot_indonesia) else "#111"
        fg = lapisan.setdefault(kategori, folium.FeatureGroup(name=kategori, show=True))
        folium.Marker(
            location=(b["lat"], b["lon"]),
            icon=ikon_kapal(warna_kategori(kategori), b.get("arah"), ukuran=18 if indo else 15, garis=garis),
            tooltip=f"{label} · {kategori} · {b.get('bendera')}",
            popup=folium.Popup(popup_kapal(b), max_width=340),
        ).add_to(fg)
    for nama in km.URUTAN_KATEGORI:
        if nama in lapisan:
            lapisan[nama].add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


def peta_heatmap(jejak: pd.DataFrame, pelabuhan: pd.DataFrame | None = None, titik_kunci: pd.DataFrame | None = None,
                 sel_terpadat: pd.DataFrame | None = None, radius: int = 10, blur: int = 14,
                 pusat=PUSAT_SELAT, zoom: int = ZOOM_AWAL) -> folium.Map:
    """Heatmap dari seluruh posisi dalam rekaman; opsional lingkaran sel terpadat."""
    m = peta_dasar(pusat, zoom)
    if titik_kunci is not None and not titik_kunci.empty:
        tambah_titik_kunci(m, titik_kunci)
    if pelabuhan is not None and not pelabuhan.empty:
        tambah_pelabuhan(m, pelabuhan)
    titik = jejak[["lat", "lon"]].dropna().to_numpy().tolist()
    if titik:
        HeatMap(titik, name="Kepadatan lalu lintas", radius=radius, blur=blur, min_opacity=0.25,
                gradient={"0.2": "#1d3557", "0.45": "#2ec4b6", "0.7": "#f2b705", "1": "#ff4d6d"}).add_to(m)
    if sel_terpadat is not None and not sel_terpadat.empty:
        fg = folium.FeatureGroup(name="Sel terpadat", show=True)
        for i, s in sel_terpadat.reset_index(drop=True).iterrows():
            folium.CircleMarker(
                location=(s["lat_tengah"], s["lon_tengah"]), radius=10 + 2 * (len(sel_terpadat) - i),
                color="#ff4d6d", weight=2, fill=False,
                tooltip=f"#{i + 1}: {int(s['kapal'])} kapal, {int(s['titik'])} posisi" + (f" · {s['label']}" if "label" in s else ""),
            ).add_to(fg)
        fg.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m



def pusat_dan_zoom(df: pd.DataFrame, lebar_px: int = 900, tinggi_px: int = 560,
                   min_rentang: float = 0.4) -> tuple[tuple[float, float], int]:
    """Pusat dan level zoom agar sebagian besar kapal (kuantil 10-90%) pas di peta.

    Leaflet memakai tile 256 piksel: pada zoom z seluruh dunia selebar 256·2^z piksel, sehingga rentang
    ``r`` derajat bujur muat di ``lebar_px`` piksel bila 2^z ≤ lebar_px·360 / (256·r).
    Kapal di luar bingkai tetap ada di peta dan terlihat saat diperkecil. Tanpa data, kembali ke tampilan seluruh selat.
    """
    if df.empty or df["lat"].dropna().empty:
        return PUSAT_SELAT, ZOOM_AWAL
    lat, lon = df["lat"].dropna(), df["lon"].dropna()
    la0, la1 = lat.quantile(0.10), lat.quantile(0.90)
    lo0, lo1 = lon.quantile(0.10), lon.quantile(0.90)
    r_lat = max(la1 - la0, min_rentang) * 1.25
    r_lon = max(lo1 - lo0, min_rentang) * 1.25
    z_lon = math.log2(lebar_px * 360 / (256 * r_lon))
    z_lat = math.log2(tinggi_px * 180 / (256 * r_lat))  # dekat khatulistiwa, cukup akurat
    zoom = int(max(5, min(11, math.floor(min(z_lon, z_lat)))))
    return (float((la0 + la1) / 2), float((lo0 + lo1) / 2)), zoom
