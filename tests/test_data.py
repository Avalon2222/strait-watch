import pytest

from src import ais, muat_data

ada_sampel = pytest.mark.skipif(not muat_data.FILE_SAMPEL.exists(), reason="sampel offline belum direkam")


def test_pelabuhan_csv_valid():
    p = muat_data.muat_pelabuhan()
    assert p["kode"].is_unique
    assert set(p["jenis"]) <= {"pelabuhan", "pangkalan_al"}
    assert p["lat"].between(ais.BBOX_SELAT["lamin"], ais.BBOX_SELAT["lamax"]).all()
    assert p["lon"].between(ais.BBOX_SELAT["lomin"], ais.BBOX_SELAT["lomax"]).all()
    assert (p["jenis"] == "pangkalan_al").sum() >= 5


def test_titik_kunci_csv_valid():
    t = muat_data.muat_titik_kunci()
    assert {"kode", "nama", "lat", "lon", "keterangan"} <= set(t.columns)
    assert len(t) >= 3


@ada_sampel
def test_sampel_offline_bisa_dimuat():
    df = muat_data.muat_sampel()
    assert not df.empty
    assert {"mmsi", "lat", "lon", "sog_knot", "waktu_snapshot", "tipe_kode"} <= set(df.columns)
    assert str(df["waktu_snapshot"].dt.tz) == "UTC"
    terakhir = muat_data.snapshot_terakhir(df)
    assert terakhir["waktu_snapshot"].nunique() == 1
    info = muat_data.info_sampel(df)
    assert info["snapshot"] >= 2 and info["kapal"] > 0


@ada_sampel
def test_live_tanpa_kunci_jatuh_ke_sampel():
    df, sumber, pesan = muat_data.muat_live_atau_sampel(None)
    assert sumber == "sampel" and not df.empty and "Kunci API" in pesan


def test_posisi_terakhir():
    import pandas as pd
    t0 = pd.Timestamp("2026-11-02 10:00", tz="UTC")
    df = pd.DataFrame({"mmsi": ["1", "1", "2", "3"], "lat": [1.0, 1.1, 2.0, 3.0], "lon": [100.0] * 4,
                       "waktu_snapshot": [t0, t0 + pd.Timedelta(minutes=5), t0, t0 - pd.Timedelta(hours=1)]})
    akhir = muat_data.posisi_terakhir(df).set_index("mmsi")
    assert len(akhir) == 3 and akhir.loc["1", "lat"] == 1.1
    assert set(muat_data.posisi_terakhir(df, menit=30)["mmsi"]) == {"1", "2"}
