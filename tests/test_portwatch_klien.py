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

