"""Tes perekam sampel offline (scripts/rekam_sampel.py), tanpa koneksi ke aisstream.io."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "scripts" / "rekam_sampel.py"
spec = importlib.util.spec_from_file_location("rekam_sampel", PATH)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

T0 = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 11, 13, 15, 1, tzinfo=timezone.utc)


def test_rapikan_posisi_saring_kotak_urut_dan_bulatkan():
    baris = [
        {"mmsi": "2", "lat": 1.2345678, "lon": 103.9, "waktu_snapshot": T1},
        {"mmsi": "1", "lat": 2.0, "lon": 101.123456789, "waktu_snapshot": T1},
        {"mmsi": "3", "lat": 1.3, "lon": 103.8, "waktu_snapshot": T0},
        {"mmsi": "9", "lat": -6.1, "lon": 106.8, "waktu_snapshot": T0},   # Jakarta, di luar kotak Selat
    ]
    df = rs.rapikan_posisi(baris)
    assert df["mmsi"].tolist() == ["3", "1", "2"]
    assert df.loc[2, "lat"] == 1.23457 and df.loc[1, "lon"] == 101.12346


def test_rapikan_posisi_rekaman_kosong_tetap_berkolom():
    df = rs.rapikan_posisi([])
    assert df.empty
    assert {"mmsi", "lat", "lon", "waktu_snapshot"} <= set(df.columns)


def test_rekam_dengan_websocket_tiruan(tmp_path, monkeypatch):
    import json

    import websockets.sync.client as klien

    from test_ais import pesan_posisi, pesan_statis

    antrean = [pesan_statis(), pesan_posisi(lat=1.2, lon=103.9), pesan_posisi(mmsi=533000001, lat=-6.1, lon=106.8)]
    terkirim = []

    class WsPalsu:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def send(self, teks):
            terkirim.append(json.loads(teks))

        def recv(self, timeout):
            if antrean:
                return json.dumps(antrean.pop(0))
            raise TimeoutError

    monkeypatch.setattr(klien, "connect", lambda *a, **k: WsPalsu())
    df_pos, df_stat = rs.rekam("kunci-uji", durasi=0.3, interval=60, keluaran=tmp_path)
    assert terkirim and terkirim[0]["APIKey"] == "kunci-uji"
    assert df_pos["mmsi"].tolist() == ["525019001"]       # kapal di Jakarta tersaring keluar
    assert df_stat["mmsi"].tolist() == ["525019001"]
    assert (tmp_path / "posisi.csv").exists() and (tmp_path / "kapal_statis.csv").exists()
