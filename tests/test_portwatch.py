import numpy as np
import pandas as pd
import pytest

from src import muat_data, portwatch


def data_buatan(hari=400):
    tanggal = pd.date_range("2025-01-01", periods=hari, freq="D")
    baris = []
    for i, t in enumerate(tanggal):
        malaka = 220 + (60 if i == hari - 10 else 0)  # satu lonjakan
        for portid, nama, total in [("chokepoint5", "Malacca Strait", malaka), ("chokepoint19", "Sunda Strait", 30)]:
            baris.append({"date": t.strftime("%Y-%m-%d"), "portid": portid, "portname": nama,
                          "n_tanker": total * 0.4, "n_container": total * 0.25, "n_dry_bulk": total * 0.25,
                          "n_general_cargo": total * 0.08, "n_roro": total * 0.02, "n_total": total,
                          "capacity": total * 40000, "capacity_tanker": total * 20000})
    return portwatch.rapikan(pd.DataFrame(baris))


def test_rapikan():
    d = data_buatan(10)
    assert list(d.columns) == portwatch.KOLOM
    assert set(d["selat"]) == {"Selat Malaka", "Selat Sunda"}
    assert pd.api.types.is_datetime64_any_dtype(d["tanggal"])
    assert d["tanggal"].is_monotonic_increasing
    assert portwatch.rapikan(pd.DataFrame()).empty


def test_rapikan_tanpa_portname_untuk_port_tak_dikenal():
    baris = [{"date": "2025-01-01", "portid": "chokepoint99", "n_tanker": 1, "n_container": 0,
              "n_dry_bulk": 0, "n_general_cargo": 0, "n_roro": 0, "n_total": 1,
              "capacity": 1, "capacity_tanker": 1}]
    d = portwatch.rapikan(pd.DataFrame(baris))
    assert d.iloc[0]["selat"] == "chokepoint99"


def test_rapikan_buang_duplikat():
    d = data_buatan(3)
    dobel = pd.concat([d, d]).rename(columns={"tanggal": "date"})
    assert len(portwatch.rapikan(dobel)) == len(d)


def test_semua_selat_punya_nama_dan_grup():
    for info in portwatch.SELAT.values():
        assert info["nama"] and info["grup"] in ("Indonesia", "Pembanding")


def test_tren_dan_per_tahun():
    d = data_buatan()
    t = portwatch.tren(d, "chokepoint5", 30)
    assert len(t) == 400 and t["rata_bergerak"].iloc[14:].notna().all()
    pt = portwatch.per_tahun(d)
    assert set(pt["tahun"]) == {2025, 2026}
    sunda = pt[(pt["selat"] == "Selat Sunda") & (pt["tahun"] == 2025)].iloc[0]
    assert sunda["rata_harian"] == 30 and sunda["hari"] == 365


def test_komposisi_jumlah_100_persen():
    k = portwatch.komposisi(data_buatan(), "chokepoint5", 365)
    assert k.iloc[0]["jenis"] == "Tanker"
    assert k["persen"].sum() == pytest.approx(100, abs=0.5)
    assert portwatch.komposisi(data_buatan(), "chokepointX").empty


def test_bandingkan():
    b = portwatch.bandingkan(data_buatan(), 365)
    assert list(b["selat"]) == ["Selat Malaka", "Selat Sunda"]
    assert b.iloc[0]["persen_tanker"] == pytest.approx(40, abs=0.1)
    assert b.set_index("selat").loc["Selat Sunda", "alki"] == "ALKI I"


def test_bandingkan_selat_sepi_tidak_inf():
    d = data_buatan(30)
    d.loc[d["portid"] == "chokepoint19", ["n_total", "n_tanker"]] = 0
    b = portwatch.bandingkan(d, 30).set_index("selat")
    assert pd.isna(b.loc["Selat Sunda", "persen_tanker"])
    assert not np.isinf(b["persen_tanker"].fillna(0)).any()


def test_anomali_menemukan_lonjakan():
    a = portwatch.anomali(data_buatan(), "chokepoint5")
    assert len(a) == 1
    assert a.iloc[0]["n_total"] == 280
    # Deret yang benar-benar konstan tidak punya simpangan: tidak boleh ada anomali palsu
    assert portwatch.anomali(data_buatan(), "chokepoint19").empty


def test_snapshot_repo_valid():
    df = muat_data.muat_portwatch()
    if df.empty:
        pytest.skip("snapshot PortWatch belum diunduh")
    assert set(df["portid"]) <= set(portwatch.SELAT)
    assert (df["n_total"] >= 0).all()
    assert not df.duplicated(["portid", "tanggal"]).any()


def test_anomali_tidak_menghasilkan_z_tak_hingga():
    a = portwatch.anomali(data_buatan(), "chokepoint5")
    assert np.isfinite(a["z"]).all()
    assert a.iloc[0]["z"] == 60.0


def test_rapikan_tanggal_epoch_milidetik_arcgis():
    baris = [{"date": 1735689600000, "portid": "chokepoint5", "portname": "Malacca Strait", "n_tanker": 1,
              "n_container": 2, "n_dry_bulk": 0, "n_general_cargo": 0, "n_roro": 0, "n_total": 3,
              "capacity": 0, "capacity_tanker": 0}]
    d = portwatch.rapikan(pd.DataFrame(baris))
    assert d.loc[0, "tanggal"] == pd.Timestamp("2025-01-01")


def test_tren_jendela_berbasis_kalender_saat_ada_hari_bolong():
    tanggal = list(pd.date_range("2025-01-01", periods=4, freq="D")) + list(pd.date_range("2025-03-01", periods=2, freq="D"))
    df = pd.DataFrame({"tanggal": tanggal, "portid": "chokepoint5", "n_total": [100.0] * 4 + [10.0] * 2})
    t = portwatch.tren(df, "chokepoint5", jendela=4)
    # 2 Maret hanya dirata-rata dengan 1-2 Maret, bukan dengan hari-hari Januari (dulu hasilnya 55).
    assert t["rata_bergerak"].iloc[-1] == 10.0


def test_rapikan_kolom_jenis_hilang_diisi_nan():
    d = portwatch.rapikan(pd.DataFrame([{"date": "2025-01-01", "portid": "chokepoint5", "n_tanker": 5, "n_total": 9}]))
    assert list(d.columns) == portwatch.KOLOM
    assert d.loc[0, "n_tanker"] == 5 and d.loc[0, "n_total"] == 9
    assert np.isnan(d.loc[0, "n_roro"]) and np.isnan(d.loc[0, "capacity"])


def test_bandingkan_seri_diurutkan_menurut_nama_selat():
    tanggal = pd.Timestamp("2025-01-01")
    baris = [{"tanggal": tanggal, "portid": p, "selat": n, "n_total": 50.0, "n_tanker": 10.0}
             for p, n in [("chokepoint5", "Selat Malaka"), ("chokepoint15", "Selat Lombok"), ("chokepoint19", "Selat Sunda")]]
    hasil = portwatch.bandingkan(pd.DataFrame(baris), 30)
    assert hasil["selat"].tolist() == ["Selat Lombok", "Selat Malaka", "Selat Sunda"]


@pytest.mark.parametrize("hari", [0, -5])
def test_jendela_hari_kurang_dari_satu_ditolak(hari):
    d = data_buatan(10)
    with pytest.raises(ValueError):
        portwatch.komposisi(d, "chokepoint5", hari)
    with pytest.raises(ValueError):
        portwatch.bandingkan(d, hari)
