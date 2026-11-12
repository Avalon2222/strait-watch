"""Jalur cadangan ``muat_live_atau_sampel``: live berhasil, live kosong, dan live gagal."""

import pandas as pd

from src import ais, muat_data
from tests.test_ais import pesan_posisi


def _palsukan_kumpulkan(monkeypatch, posisi=None, galat=None, jumlah=5):
    def palsu(api_key, durasi=0, cache_statis=None, **kw):
        if galat is not None:
            raise galat
        return posisi or {}, {}, jumlah
    monkeypatch.setattr(ais, "kumpulkan", palsu)


def test_live_berhasil(monkeypatch):
    _, baris = ais.urai_pesan(pesan_posisi(lat=1.25, lon=103.9))
    _palsukan_kumpulkan(monkeypatch, posisi={baris["mmsi"]: baris}, jumlah=1234)
    df, sumber, pesan = muat_data.muat_live_atau_sampel("kunci", durasi=10)
    assert sumber == "live"
    assert list(df["mmsi"]) == ["525019001"]
    assert "1,234 pesan" in pesan and "10 detik" in pesan


def test_live_di_luar_kotak_jatuh_ke_sampel(monkeypatch):
    _, baris = ais.urai_pesan(pesan_posisi(lat=-30.0, lon=20.0))  # jauh dari Selat Malaka
    _palsukan_kumpulkan(monkeypatch, posisi={baris["mmsi"]: baris})
    df, sumber, pesan = muat_data.muat_live_atau_sampel("kunci", durasi=10)
    assert sumber == "sampel" and not df.empty
    assert "tidak ada posisi kapal dalam kotak pantau" in pesan


def test_live_gagal_jatuh_ke_sampel(monkeypatch):
    _palsukan_kumpulkan(monkeypatch, galat=ais.AisError("Tidak dapat terhubung."))
    df, sumber, pesan = muat_data.muat_live_atau_sampel("kunci", durasi=10)
    assert sumber == "sampel"
    assert df["waktu_snapshot"].nunique() == 1
    assert pesan.startswith("Tidak dapat terhubung.") and pesan.endswith("sampel offline.")


def test_portwatch_file_tidak_ada(tmp_path):
    assert muat_data.muat_portwatch(tmp_path / "tidak_ada.csv").empty
    assert muat_data.muat_portwatch_ringkas(tmp_path / "tidak_ada.csv").empty


def test_portwatch_ringkas_dari_repo():
    df = muat_data.muat_portwatch_ringkas()
    assert isinstance(df, pd.DataFrame) and not df.empty
