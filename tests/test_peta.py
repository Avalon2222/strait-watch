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
