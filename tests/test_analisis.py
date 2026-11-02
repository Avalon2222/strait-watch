import numpy as np
import pandas as pd
import pytest

from src import analisis, muat_data


def tabel(baris):
    dasar = {"nama": "", "heading": None, "status_nav_kode": None, "kelas": "A", "waktu_pesan": None,
             "waktu_snapshot": pd.Timestamp("2026-11-02 10:00", tz="UTC"), "tipe_kode": None, "tujuan": None,
             "panjang_m": None, "lebar_m": None, "sarat_m": None, "imo": None, "callsign": None}
    return pd.DataFrame([{**dasar, **b} for b in baris])


@pytest.fixture
def pelabuhan():
    return muat_data.muat_pelabuhan()


@pytest.fixture
def kapal():
    return tabel([
        {"mmsi": "525000001", "nama": "KM INDO", "lat": 1.17, "lon": 104.02, "sog_knot": 12.0, "cog": 300.0, "tipe_kode": 70, "status_nav_kode": 0},
        {"mmsi": "563000001", "nama": "SG TANKER", "lat": 1.25, "lon": 103.70, "sog_knot": 0.1, "cog": 15.0, "heading": 90.0, "tipe_kode": 84, "status_nav_kode": 1},
        {"mmsi": "371000001", "nama": "", "lat": 2.90, "lon": 100.95, "sog_knot": 18.0, "cog": 135.0, "tipe_kode": 80},
        {"mmsi": "002570100", "nama": "COAST", "lat": 1.3, "lon": 103.8, "sog_knot": None, "cog": None},
    ])


def test_haversine_dikenal():
    # Singapura (Pasir Panjang) ke Port Klang kurang lebih 320 km
    d = analisis.haversine_km(1.27, 103.76, 3.0, 101.39)
    assert 310 < d < 335
    assert analisis.haversine_km(1.0, 100.0, 1.0, 100.0) == 0
    v = analisis.haversine_vektor(np.array([1.27]), np.array([103.76]), 3.0, 101.39)
    assert abs(v[0] - d) < 1e-6


@pytest.mark.parametrize("sog, status, fase", [
    (12.0, 0, "Berlayar"), (3.0, 0, "Lambat"), (0.2, 0, "Diam"), (0.2, 1, "Berlabuh jangkar"), (0.0, 5, "Tertambat"),
    (4.0, 7, "Menangkap ikan"), (None, None, "Tidak diketahui"), (float("nan"), 15, "Tidak diketahui"), (7.0, None, "Berlayar"),
])
def test_fase_pelayaran(sog, status, fase):
    assert analisis.fase_pelayaran(sog, status) == fase


def test_perkaya(kapal, pelabuhan):
    d = analisis.perkaya(kapal, pelabuhan)
    r = d.set_index("mmsi")
    assert r.loc["525000001", "bendera"] == "Indonesia"
    assert r.loc["525000001", "kategori"] == "Kargo"
    assert r.loc["525000001", "fase"] == "Berlayar"
    assert r.loc["525000001", "arah"] == 300.0  # bergerak: pakai COG
    assert r.loc["563000001", "arah"] == 90.0   # diam: pakai heading
    assert r.loc["563000001", "fase"] == "Berlabuh jangkar"
    assert r.loc["563000001", "kecepatan_kmh"] == pytest.approx(0.2, abs=0.05)
    assert r.loc["371000001", "label"] == "MMSI 371000001"
    assert r.loc["371000001", "bendera"] == "Panama"
    assert r.loc["525000001", "pelabuhan_terdekat"] == "Pelabuhan Batu Ampar"
    assert r.loc["525000001", "jarak_pelabuhan_km"] < 5
    assert r.loc["002570100", "jenis_mmsi"] == "Stasiun pantai"
    assert "Pelabuhan" in r.loc["371000001", "pelabuhan_terdekat"] or "Port" in r.loc["371000001", "pelabuhan_terdekat"]


def test_perkaya_kosong(pelabuhan):
    d = analisis.perkaya(pd.DataFrame(columns=["mmsi", "nama", "lat", "lon", "sog_knot", "cog", "heading", "status_nav_kode", "tipe_kode"]), pelabuhan)
    assert d.empty and "bendera" in d.columns and "fase" in d.columns


def test_hanya_kapal(kapal, pelabuhan):
    d = analisis.hanya_kapal(analisis.perkaya(kapal, pelabuhan))
    assert "002570100" not in set(d["mmsi"])
    assert len(d) == 3


def test_hitung_unik_dan_ringkasan(kapal, pelabuhan):
    d = analisis.hanya_kapal(analisis.perkaya(kapal, pelabuhan))
    jejak = pd.concat([d, d.assign(waktu_snapshot=pd.Timestamp("2026-11-02 10:01", tz="UTC"))])
    per = analisis.hitung_unik(jejak, "kategori")
    assert per.set_index("kategori").loc["Tanker", "kapal"] == 2  # unik, bukan baris
    assert per["persen"].sum() == pytest.approx(100, abs=0.2)
    r = analisis.ringkasan(jejak)
    assert r["total"] == 3 and r["indonesia"] == 1 and r["tanker"] == 2 and r["kargo"] == 1
    assert r["persen_indonesia"] == pytest.approx(33.3, abs=0.1)
    assert r["bergerak"] == 2 and r["berlabuh"] == 1
    assert analisis.ringkasan(d.iloc[0:0])["total"] == 0


def test_grid_kepadatan(kapal, pelabuhan):
    d = analisis.hanya_kapal(analisis.perkaya(kapal, pelabuhan))
    g = analisis.grid_kepadatan(d, 0.5)
    assert g["titik"].sum() == 3
    assert g.iloc[0]["kapal"] >= g.iloc[-1]["kapal"]
    # dua kapal di sekitar Singapura jatuh ke sel 1.0-1.5 / 103.5-104.0 dan 104.0-104.5
    assert set(g["lat_tengah"]) == {1.25, 2.75}


def test_label_lokasi_dan_sekitar(kapal, pelabuhan):
    titik = muat_data.muat_titik_kunci()
    d = analisis.hanya_kapal(analisis.perkaya(kapal, pelabuhan))
    assert analisis.label_lokasi(2.9, 100.95, pelabuhan, titik).startswith("Dekat One Fathom Bank")
    sekitar = analisis.kapal_di_sekitar(d, 2.88, 100.98, 10)
    assert list(sekitar["mmsi"]) == ["371000001"]
    sibuk = analisis.sibuk_per_titik(d, titik, 25)
    assert sibuk.iloc[0]["kapal"] >= 1 and {"nama", "kapal", "tanker"} <= set(sibuk.columns)


def test_panjang_jejak(kapal, pelabuhan):
    d = analisis.hanya_kapal(analisis.perkaya(kapal, pelabuhan))
    d2 = d.copy()
    d2["waktu_snapshot"] = pd.Timestamp("2026-11-02 10:01", tz="UTC")
    d2.loc[d2["mmsi"] == "525000001", "lon"] += 0.1  # sekitar 11 km ke timur
    pj = analisis.panjang_jejak_km(pd.concat([d, d2]))
    assert pj.iloc[0]["mmsi"] == "525000001"
    assert 10 < pj.iloc[0]["km"] < 12
    assert analisis.panjang_jejak_km(d).empty


def test_di_dalam_kotak():
    df = pd.DataFrame({"lat": [1.0, 20.0], "lon": [100.0, 100.0], "mmsi": ["1", "2"]})
    assert list(analisis.di_dalam_kotak(df)["mmsi"]) == ["1"]
