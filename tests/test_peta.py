"""Tes popup dan warna di src/peta.py (tanpa membuka browser)."""

import numpy as np
import pandas as pd

from src import mmsi as km
from src import peta


def _kapal(**ubah) -> pd.Series:
    dasar = {"mmsi": "525000001", "label": "KM UJI", "nama": "KM UJI", "bendera": "Indonesia", "tipe": "Kargo",
             "tujuan": "TANJUNG PRIOK", "status_nav": "Berlayar", "fase": "Berlayar", "sog_knot": 12.3,
             "kecepatan_kmh": 22.8, "cog": 90.0, "imo": 9123456.0, "panjang_m": 120.0, "lebar_m": 20.0,
             "sarat_m": 7.5, "pelabuhan_terdekat": "Batam", "jarak_pelabuhan_km": 4.2}
    dasar.update(ubah)
    return pd.Series(dasar)


def test_popup_lengkap():
    html = peta.popup_kapal(_kapal())
    assert "KM UJI" in html and "TANJUNG PRIOK" in html
    assert "9123456" in html and "Batam (4 km)" in html


def test_popup_tidak_menampilkan_nan():
    # Kapal yang belum mengirim pesan statis: tujuan, IMO, ukuran, pelabuhan masih NaN.
    html = peta.popup_kapal(_kapal(tujuan=np.nan, imo=np.nan, panjang_m=np.nan,
                                   pelabuhan_terdekat=np.nan, jarak_pelabuhan_km=np.nan))
    assert "nan" not in html.lower()
    assert "Tujuan (AIS)</td><td>-</td>" in html
    assert "Pelabuhan terdekat" not in html


def test_popup_label_kosong_jatuh_ke_mmsi():
    html = peta.popup_kapal(_kapal(label=np.nan, nama=""))
    assert "MMSI 525000001" in html


def test_popup_aman_dari_html():
    html = peta.popup_kapal(_kapal(label="<script>x</script>"))
    assert "<script>" not in html


def test_warna_kategori_tak_dikenal_pakai_warna_lain():
    assert peta.warna_kategori("kategori-ngawur") == peta.WARNA_KATEGORI[km.KATEGORI_LAIN]
    assert peta.warna_kategori(None) == peta.warna_kategori(km.TIDAK_DIKETAHUI)


def _armada() -> pd.DataFrame:
    return pd.DataFrame([
        {"mmsi": "525000001", "label": "KM UJI", "nama": "KM UJI", "bendera": "Indonesia", "kategori": "Kargo",
         "lat": 1.2, "lon": 103.8, "arah": 90.0},
        {"mmsi": "563000002", "label": "SG TANKER", "nama": "SG TANKER", "bendera": "Singapura", "kategori": "Tanker",
         "lat": 1.25, "lon": 103.9, "arah": np.nan},
        {"mmsi": "533000003", "label": "MY TUG", "nama": "MY TUG", "bendera": "Malaysia", "kategori": "Tunda & servis",
         "lat": 2.1, "lon": 101.5, "arah": 270.0},
    ])


def _render(m) -> str:
    return m.get_root().render()


def test_ikon_kapal_berputar_atau_titik():
    berputar = peta.ikon_kapal("#fff", 45.4).options["html"]
    assert "rotate(45deg)" in berputar and "<path" in berputar
    titik = peta.ikon_kapal("#fff", np.nan).options["html"]
    assert "<circle" in titik and "rotate" not in titik


def test_teks_format_dan_kosong():
    assert peta._teks(1234.56, " km") == "1,235 km"
    assert peta._teks(7.5, " m", 1) == "7.5 m"
    assert peta._teks(np.nan) == "-" and peta._teks(None) == "-" and peta._teks("") == "-"
    assert peta._teks("abc", "!") == "abc!"


def test_peta_kapal_satu_lapisan_per_kategori():
    html = _render(peta.peta_kapal(_armada()))
    assert html.count("L.marker(") == 3
    for nama in ("Kargo", "Tanker", "Tunda \u0026 servis"):
        assert nama in html
    # Kapal Indonesia disorot dengan garis teal.
    assert peta.WARNA_INDONESIA in html


def test_peta_kapal_tanpa_sorotan_indonesia():
    html = _render(peta.peta_kapal(_armada(), sorot_indonesia=False))
    assert f'stroke="{peta.WARNA_INDONESIA}"' not in html


def test_peta_kapal_dengan_pelabuhan_dan_titik_kunci():
    pelabuhan = pd.DataFrame([
        {"nama": "Batam", "negara": "Indonesia", "jenis": "pelabuhan", "lat": 1.1, "lon": 104.0},
        {"nama": "Lanal Batam", "negara": "Indonesia", "jenis": "pangkalan_al", "lat": 1.15, "lon": 104.05},
    ])
    titik = pd.DataFrame([{"nama": "One Fathom Bank", "keterangan": "Bagian tersempit", "lat": 2.88, "lon": 100.98}])
    html = _render(peta.peta_kapal(_armada(), pelabuhan=pelabuhan, titik_kunci=titik))
    assert "Lanal Batam" in html and "One Fathom Bank" in html
    assert html.count("L.circleMarker(") == 2 and html.count("L.circle(") == 1


def test_peta_heatmap_dengan_sel_terpadat():
    jejak = pd.DataFrame({"lat": [1.2, 1.21, np.nan, 2.0], "lon": [103.8, 103.81, 103.9, np.nan]})
    sel = pd.DataFrame([{"lat_tengah": 1.2, "lon_tengah": 103.8, "kapal": 12, "titik": 40}])
    html = _render(peta.peta_heatmap(jejak, sel_terpadat=sel))
    assert "L.heatLayer" in html
    assert "#1: 12 kapal, 40 posisi" in html


def test_peta_heatmap_tanpa_titik_tetap_jadi():
    jejak = pd.DataFrame({"lat": [np.nan], "lon": [np.nan]})
    html = _render(peta.peta_heatmap(jejak))
    assert "L.heatLayer" not in html


def test_peta_kapal_kategori_kosong_tetap_digambar():
    armada = _armada()
    armada.loc[0, "kategori"] = np.nan
    armada.loc[1, "kategori"] = "Kategori aneh"
    armada.loc[2, "label"] = np.nan
    html = _render(peta.peta_kapal(armada))
    # Sebelumnya kapal berkategori NaN/tak dikenal hilang dari peta karena lapisannya tidak pernah ditambahkan.
    assert html.count("L.marker(") == 3
    assert km.TIDAK_DIKETAHUI in html
    assert "nan ·" not in html and "MY TUG ·" in html


def test_peta_dasar_pakai_tile_gelap():
    html = _render(peta.peta_dasar())
    assert peta.TILE_GELAP.split("{")[0] in html
    assert "L.control.scale" in html


def test_tooltip_pelabuhan_dan_titik_kunci_di_escape():
    m = peta.peta_dasar()
    peta.tambah_pelabuhan(m, pd.DataFrame([
        {"nama": "Dermaga <A&B>", "negara": "Indonesia", "jenis": "pelabuhan", "lat": 1.1, "lon": 104.0},
    ]))
    peta.tambah_titik_kunci(m, pd.DataFrame([
        {"nama": "Selat <X>", "keterangan": "lebar < 3 km", "lat": 2.0, "lon": 101.0},
    ]))
    html = _render(m)
    assert "Dermaga <A&B>" not in html and "Selat <X>" not in html
    assert "Dermaga &lt;A&amp;B&gt;" in html
