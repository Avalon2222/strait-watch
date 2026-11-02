from datetime import datetime, timezone

import pandas as pd
import pytest

from src import ais


def pesan_posisi(mmsi=525019001, lat=1.2, lon=103.9, sog=12.3, cog=245.5, heading=511, status=0, nama="KM SINABUNG@@@"):
    return {
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": mmsi, "ShipName": nama, "latitude": lat, "longitude": lon,
                     "time_utc": "2026-11-02 17:00:01.123456789 +0000 UTC"},
        "Message": {"PositionReport": {"UserID": mmsi, "Latitude": lat, "Longitude": lon, "Sog": sog, "Cog": cog,
                                       "TrueHeading": heading, "NavigationalStatus": status}},
    }


def pesan_statis(mmsi=525019001, tipe=60, nama="KM SINABUNG", tujuan="BELAWAN   "):
    return {
        "MessageType": "ShipStaticData",
        "MetaData": {"MMSI": mmsi, "ShipName": nama},
        "Message": {"ShipStaticData": {"UserID": mmsi, "Name": nama, "Type": tipe, "Destination": tujuan,
                                       "Dimension": {"A": 100, "B": 46, "C": 10, "D": 12},
                                       "ImoNumber": 9123456, "CallSign": "YBAB2", "MaximumStaticDraught": 5.9}},
    }


def test_pesan_langganan():
    p = ais.pesan_langganan("kunci")
    assert p["APIKey"] == "kunci"
    assert p["BoundingBoxes"] == ais.BOUNDING_BOXES
    assert "PositionReport" in p["FilterMessageTypes"] and "ShipStaticData" in p["FilterMessageTypes"]
    (sw, ne), = p["BoundingBoxes"]
    assert sw[0] < ne[0] and sw[1] < ne[1]  # [lat, lon] barat daya lalu timur laut


def test_urai_posisi():
    jenis, b = ais.urai_pesan(pesan_posisi())
    assert jenis == "posisi"
    assert b["mmsi"] == "525019001"
    assert b["nama"] == "KM SINABUNG"
    assert b["sog_knot"] == 12.3 and b["cog"] == 245.5
    assert b["heading"] is None  # 511 = tidak tersedia
    assert b["status_nav_kode"] == 0
    assert b["kelas"] == "A"
    assert b["waktu_pesan"] == pd.Timestamp("2026-11-02 17:00:01", tz="UTC")


def test_urai_nilai_tidak_tersedia_dan_kelas_b():
    jenis, b = ais.urai_pesan(pesan_posisi(sog=102.3, cog=360.0))
    assert b["sog_knot"] is None and b["cog"] is None
    p = pesan_posisi()
    p["MessageType"] = "StandardClassBPositionReport"
    p["Message"] = {"StandardClassBPositionReport": p["Message"].pop("PositionReport")}
    jenis, b = ais.urai_pesan(p)
    assert jenis == "posisi" and b["kelas"] == "B" and b["status_nav_kode"] is None


def test_urai_posisi_tidak_valid():
    assert ais.urai_pesan(pesan_posisi(lat=91.0)) is None
    assert ais.urai_pesan({"MessageType": "PositionReport", "MetaData": {}, "Message": {}}) is None
    assert ais.urai_pesan({"MessageType": "AidsToNavigationReport", "MetaData": {"MMSI": 992571234}, "Message": {}}) is None


def test_urai_statis():
    jenis, s = ais.urai_pesan(pesan_statis())
    assert jenis == "statis"
    assert s["tipe_kode"] == 60 and s["tujuan"] == "BELAWAN"
    assert s["panjang_m"] == 146 and s["lebar_m"] == 22 and s["sarat_m"] == 5.9
    assert s["imo"] == 9123456 and s["callsign"] == "YBAB2"


def test_ke_dataframe_gabung_statis():
    _, p = ais.urai_pesan(pesan_posisi())
    _, s = ais.urai_pesan(pesan_statis(nama="SINABUNG LENGKAP"))
    _, p2 = ais.urai_pesan(pesan_posisi(mmsi=563000001, nama="TANPA STATIS"))
    df = ais.ke_dataframe({p["mmsi"]: p, p2["mmsi"]: p2}, {s["mmsi"]: s}, datetime(2026, 11, 2, tzinfo=timezone.utc))
    assert len(df) == 2
    baris = df.set_index("mmsi")
    assert baris.loc["525019001", "nama"] == "SINABUNG LENGKAP"  # nama statis diutamakan
    assert baris.loc["525019001", "tipe_kode"] == 60
    assert baris.loc["563000001", "nama"] == "TANPA STATIS"
    assert pd.isna(baris.loc["563000001", "tipe_kode"])
    assert str(df["waktu_snapshot"].dt.tz) == "UTC"


def test_ke_dataframe_kosong():
    df = ais.ke_dataframe({}, {})
    assert df.empty and "mmsi" in df.columns and "tipe_kode" in df.columns


def test_kumpulkan_tanpa_server_menjadi_aiserror(monkeypatch):
    monkeypatch.setattr(ais, "URL_STREAM", "ws://127.0.0.1:9")  # port discard: koneksi pasti ditolak
    with pytest.raises(ais.AisError):
        ais.kumpulkan("kunci", durasi=1)
