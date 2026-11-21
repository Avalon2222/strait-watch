"""Tes kasus tepi fungsi analisis (src/analisis.py): tabel kosong, kotak khusus, kategori kosong."""

import numpy as np
import pandas as pd

from src import analisis
from src import mmsi as km


def test_di_dalam_kotak_bbox_khusus_dan_kosong():
    df = pd.DataFrame({"mmsi": ["1", "2"], "lat": [1.0, 5.0], "lon": [104.0, 98.0]})
    kotak_batam = {"lamin": 0.5, "lamax": 1.5, "lomin": 103.5, "lomax": 104.5}
    assert analisis.di_dalam_kotak(df, kotak_batam)["mmsi"].tolist() == ["1"]
    assert analisis.di_dalam_kotak(df.iloc[0:0]).empty


def test_sibuk_per_titik_tanpa_kapal_semua_nol():
    titik = pd.DataFrame({"nama": ["Batam", "Dumai"], "negara": ["Indonesia"] * 2, "lat": [1.1, 1.7], "lon": [104.0, 101.4]})
    kosong = pd.DataFrame(columns=["mmsi", "lat", "lon", "kategori"])
    hasil = analisis.sibuk_per_titik(kosong, titik)
    assert hasil["kapal"].tolist() == [0, 0] and hasil["tanker"].tolist() == [0, 0]
    assert analisis.sibuk_per_titik(kosong, titik.iloc[0:0]).empty


def test_hitung_unik_kategori_kosong_jadi_tidak_diketahui():
    df = pd.DataFrame({"mmsi": ["1", "1", "2", "3"], "kategori": ["Kargo", "Kargo", np.nan, "Kargo"]})
    h = analisis.hitung_unik(df, "kategori").set_index("kategori")
    assert h.loc["Kargo", "kapal"] == 2           # MMSI 1 dihitung sekali
    assert h.loc[km.TIDAK_DIKETAHUI, "kapal"] == 1
    assert h["persen"].sum() == 100.0


def test_hitung_unik_kolom_tidak_ada_dan_batas_teratas():
    df = pd.DataFrame({"mmsi": ["1", "2", "3"], "bendera": ["A", "B", "C"]})
    assert analisis.hitung_unik(df, "kolom_aneh").empty
    assert len(analisis.hitung_unik(df, "bendera", teratas=2)) == 2


PELABUHAN_UJI = pd.DataFrame({"nama": ["A", "B"], "lat": [1.0, 2.0], "lon": [103.0, 104.0],
                              "jenis": ["pelabuhan", "pelabuhan"]})


def test_pelabuhan_terdekat_kapal_tanpa_koordinat_tidak_diberi_nama():
    df = pd.DataFrame({"lat": [1.2, np.nan], "lon": [103.8, np.nan]})
    nama, jarak = analisis.pelabuhan_terdekat(df, PELABUHAN_UJI)
    assert nama.iloc[0] == "A"
    assert nama.iloc[1] is None
    assert np.isnan(jarak.iloc[1])


def test_label_lokasi_koordinat_kosong():
    assert analisis.label_lokasi(np.nan, 103.8, PELABUHAN_UJI) == "Lokasi tidak diketahui"
    assert analisis.label_lokasi(None, None, PELABUHAN_UJI) == "Lokasi tidak diketahui"
    assert analisis.label_lokasi(1.0, 103.0, PELABUHAN_UJI) == "Dekat A (0 km)"


def test_grid_kepadatan_tolak_ukuran_sel_nol_atau_negatif():
    import pytest

    df = pd.DataFrame({"lat": [1.2], "lon": [103.8], "mmsi": ["525000001"]})
    for ukuran in (0, -0.25, float("nan")):
        with pytest.raises(ValueError, match="ukuran_deg"):
            analisis.grid_kepadatan(df, ukuran)


def test_label_lokasi_lewati_titik_kunci_tanpa_koordinat():
    titik = pd.DataFrame({"nama": ["Tanpa Koordinat", "B"], "lat": [np.nan, 1.5], "lon": [np.nan, 103.5]})
    assert analisis.label_lokasi(1.5, 103.5, PELABUHAN_UJI, titik) == "Dekat B (0 km)"


def test_perkaya_heading_511_dan_cog_360_bukan_arah():
    df = pd.DataFrame({"mmsi": ["525001234", "525001235"], "lat": [1.0, 1.0], "lon": [103.0, 103.0],
                       "sog_knot": [0.0, 8.0], "cog": [360.0, 360.0], "heading": [511.0, 90.0], "nama": ["A", "B"]})
    d = analisis.perkaya(df)
    assert pd.isna(d.loc[0, "arah"])
    assert d.loc[1, "arah"] == 90.0


def test_perkaya_mmsi_float_dirapikan():
    df = pd.DataFrame({"mmsi": [525001234.0, np.nan], "lat": [1.0, 1.0], "lon": [103.0, 103.0],
                       "sog_knot": [0.0, 0.0], "cog": [10.0, 10.0], "heading": [np.nan, np.nan], "nama": ["", ""]})
    d = analisis.perkaya(df)
    assert list(d["mmsi"]) == ["525001234", ""]
    assert list(d["label"]) == ["MMSI 525001234", "Tanpa MMSI"]
    assert d.loc[0, "bendera"] == "Indonesia"
