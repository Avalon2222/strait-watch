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
