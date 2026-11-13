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
