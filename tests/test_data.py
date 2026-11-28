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


def test_posisi_terakhir_pesan_ganda_satu_snapshot_ambil_yang_akhir():
    import pandas as pd

    t0 = pd.Timestamp("2026-01-01", tz="UTC")
    baris = [
        {"mmsi": str(100_000_000 + k), "waktu_snapshot": t0 + pd.Timedelta(minutes=s), "lat": float(urut), "lon": 0.0}
        for s in range(3) for k in range(60) for urut in range(2)
    ]
    akhir = muat_data.posisi_terakhir(pd.DataFrame(baris))
    assert len(akhir) == 60
    assert (akhir["lat"] == 1.0).all()


def test_muat_pelabuhan_koordinat_teks_rusak_dibuang(tmp_path):
    path = tmp_path / "pelabuhan.csv"
    path.write_text(
        "kode,nama,kota,negara,jenis,lat,lon\n"
        "PKG,Port Klang,Klang,MY,pelabuhan,3.0,101.4\n"
        "XXX,Rusak,?,ID,pelabuhan,-,101.0\n"
        "BLW,Belawan,Medan,ID,pelabuhan,3.78,98.69\n"
    )
    p = muat_data.muat_pelabuhan(path)
    assert p["kode"].tolist() == ["PKG", "BLW"]
    assert p["lat"].dtype.kind == "f"


def test_muat_sampel_waktu_snapshot_rusak_dibuang(tmp_path):
    path = tmp_path / "posisi.csv"
    path.write_text(
        "mmsi,nama,lat,lon,sog_knot,cog,waktu_snapshot\n"
        "525019001,KM A,1.2,103.9,10,100,2026-11-02T17:00:00Z\n"
        "525019002,KM B,1.3,103.8,10,100,kapan\n"
        "525019003,KM C,x,103.7,10,100,2026-11-02T17:00:00Z\n"
    )
    df = muat_data.muat_sampel(path, path_statis=None)
    assert df["mmsi"].tolist() == ["525019001"]
    assert str(df["waktu_snapshot"].dt.tz) == "UTC"
