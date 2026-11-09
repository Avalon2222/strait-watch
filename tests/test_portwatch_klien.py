"""Tes klien HTTP PortWatch (src/portwatch.py) tanpa internet: server dipalsukan lewat monkeypatch."""

import io
import json
import urllib.error

import pytest

from src import portwatch


class _Jawaban(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _server(monkeypatch, jawaban: list):
    """Pasang urlopen palsu yang menjawab berurutan; item Exception dilempar."""
    alamat = []

    def urlopen(url, timeout):
        alamat.append(url)
        isi = jawaban.pop(0)
        if isinstance(isi, Exception):
            raise isi
        return _Jawaban(json.dumps(isi).encode())

    monkeypatch.setattr(portwatch.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(portwatch.time, "sleep", lambda s: None)
    return alamat


def test_minta_ulang_saat_server_error_lalu_berhasil(monkeypatch):
    alamat = _server(monkeypatch, [{"error": {"message": "Invalid URL"}},
                                   urllib.error.URLError("putus"),
                                   {"features": []}])
    assert portwatch._minta("https://contoh/query", {"where": "1=1"}) == {"features": []}
    assert len(alamat) == 3
    assert alamat[0] == "https://contoh/query?where=1%3D1"


def test_minta_menyerah_dengan_pesan_terakhir(monkeypatch):
    _server(monkeypatch, [{"error": {"message": "Invalid URL"}}] * 3)
    with pytest.raises(portwatch.PortWatchError, match="3 percobaan.*Invalid URL"):
        portwatch._minta("https://contoh/query", {}, percobaan=3)


def test_ambil_halaman_kirim_parameter_yang_benar(monkeypatch):
    alamat = _server(monkeypatch, [{"features": []}])
    portwatch.ambil_halaman("chokepoint5", offset=2000, ukuran=500)
    url = alamat[0]
    assert "where=portid%3D%27chokepoint5%27" in url
    assert "resultOffset=2000" in url and "resultRecordCount=500" in url
    assert "returnGeometry=false" in url


def _fitur(portid, tanggal, n):
    return {"attributes": {"date": tanggal, "portid": portid, "portname": "x", "n_tanker": n, "n_container": 0,
                           "n_dry_bulk": 0, "n_general_cargo": 0, "n_roro": 0, "n_total": n,
                           "capacity": 0, "capacity_tanker": 0}}


def test_ambil_harian_ikuti_halaman_dan_ulang_yang_gagal(monkeypatch):
    panggilan = []
    sudah_gagal = set()

    def halaman_palsu(portid, offset, ukuran, percobaan):
        panggilan.append((portid, offset))
        if portid == "chokepoint19" and portid not in sudah_gagal:
            sudah_gagal.add(portid)                      # gagal sekali, berhasil di putaran kedua
            raise portwatch.PortWatchError("sibuk")
        if portid == "chokepoint5" and offset == 0:
            return {"features": [_fitur(portid, "2018-12-31", 1), _fitur(portid, "2024-01-01", 70)],
                    "exceededTransferLimit": True}
        if portid == "chokepoint5":
            return {"features": [_fitur(portid, "2024-01-02", 72)]}
        return {"features": [_fitur(portid, "2024-01-01", 40)]}

    monkeypatch.setattr(portwatch, "ambil_halaman", halaman_palsu)
    monkeypatch.setattr(portwatch.time, "sleep", lambda s: None)
    df = portwatch.ambil_harian(["chokepoint5", "chokepoint19"], sejak="2019-01-01", ukuran_halaman=2)
    assert ("chokepoint5", 2) in panggilan                 # halaman kedua diambil dari offset yang benar
    assert panggilan.count(("chokepoint5", 0)) == 1         # halaman yang sudah berhasil tidak diulang
    assert len(df) == 3 and df["tanggal"].min().year == 2024   # baris sebelum `sejak` dibuang
    assert set(df["selat"]) == {"Selat Malaka", "Selat Sunda"}


def test_ambil_harian_gagal_terus(monkeypatch):
    def selalu_gagal(*a, **k):
        raise portwatch.PortWatchError("mati")

    monkeypatch.setattr(portwatch, "ambil_halaman", selalu_gagal)
    monkeypatch.setattr(portwatch.time, "sleep", lambda s: None)
    with pytest.raises(portwatch.PortWatchError, match="tetap gagal"):
        portwatch.ambil_harian(["chokepoint5"], putaran=2)

