"""Tes ``ais.kumpulkan`` tanpa jaringan: WebSocket diganti tiruan yang memutar pesan siap pakai."""

import json

import pytest
from websockets.exceptions import ConnectionClosedError

from src import ais
from tests.test_ais import pesan_posisi, pesan_statis


class WsTiruan:
    """Pengganti ``websockets.sync.client.connect``: kirim pesan berurutan, lalu TimeoutError atau galat."""

    def __init__(self, pesan, galat=None):
        self.pesan = list(pesan)
        self.galat = galat
        self.terkirim = []

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send(self, data):
        self.terkirim.append(json.loads(data))

    def recv(self, timeout=None):
        if self.pesan:
            p = self.pesan.pop(0)
            return p if isinstance(p, str) else json.dumps(p)
        if self.galat is not None:
            raise self.galat
        raise TimeoutError


@pytest.fixture
def pasang_ws(monkeypatch):
    def _pasang(pesan, galat=None):
        ws = WsTiruan(pesan, galat)
        monkeypatch.setattr("websockets.sync.client.connect", ws)
        return ws
    return _pasang


def test_kumpulkan_pisahkan_posisi_dan_statis(pasang_ws):
    ws = pasang_ws([pesan_posisi(lat=1.1), pesan_statis(), "{rusak", pesan_posisi(lat=1.3)])
    posisi, statis, jumlah = ais.kumpulkan("kunci", durasi=0.2)
    assert ws.terkirim[0]["APIKey"] == "kunci"
    assert jumlah == 3  # JSON rusak tidak dihitung
    assert posisi["525019001"]["lat"] == 1.3  # posisi terakhir menang
    assert statis["525019001"]["tujuan"] == "BELAWAN"


def test_kumpulkan_perbarui_cache_statis(pasang_ws):
    cache = {"111111111": {"mmsi": "111111111", "nama_statis": "LAMA"}}
    pasang_ws([pesan_statis()])
    _, statis, _ = ais.kumpulkan("kunci", durasi=0.2, cache_statis=cache)
    assert statis is cache
    assert set(cache) == {"111111111", "525019001"}


def test_kumpulkan_berhenti_di_maks_pesan(pasang_ws):
    pasang_ws([pesan_posisi()] * 10)
    _, _, jumlah = ais.kumpulkan("kunci", durasi=5, maks_pesan=4)
    assert jumlah == 4


def test_kumpulkan_pesan_error_server(pasang_ws):
    pasang_ws([{"error": "Api Key Is Not Valid"}])
    with pytest.raises(ais.AisError, match="menolak"):
        ais.kumpulkan("salah", durasi=1)


def test_kumpulkan_tanpa_pesan(pasang_ws):
    pasang_ws([])
    with pytest.raises(ais.AisError, match="tidak ada pesan diterima"):
        ais.kumpulkan("kunci", durasi=0.1)


def test_kumpulkan_koneksi_putus(pasang_ws):
    pasang_ws([], galat=ConnectionClosedError(None, None))
    with pytest.raises(ais.AisError, match="Tidak dapat terhubung"):
        ais.kumpulkan("kunci", durasi=1)


def test_kumpulkan_putus_setelah_ada_pesan_tetap_kembalikan_data(pasang_ws):
    pasang_ws([pesan_posisi()], galat=ConnectionClosedError(None, None))
    posisi, _, jumlah = ais.kumpulkan("kunci", durasi=1)
    assert jumlah == 1 and "525019001" in posisi
