import pytest

from src import mmsi


@pytest.mark.parametrize("nomor, negara", [
    (525019001, "Indonesia"),
    ("533130123", "Malaysia"),
    ("563001234", "Singapura"),
    ("566999999", "Singapura"),
    ("412345678", "Tiongkok"),
    ("371234567", "Panama"),
    ("636012345", "Liberia"),
    ("538001234", "Kepulauan Marshall"),
])
def test_negara_bendera_dikenal(nomor, negara):
    assert mmsi.negara_bendera(nomor) == negara


@pytest.mark.parametrize("nomor", ["002570100", "992571234", "970123456", "12345", "", None, "abc123456", "123456789"])
def test_negara_bendera_tidak_diketahui(nomor):
    assert mmsi.negara_bendera(nomor) == mmsi.TIDAK_DIKETAHUI


def test_jenis_mmsi():
    assert mmsi.jenis_mmsi("525019001") == "Kapal"
    assert mmsi.jenis_mmsi("002570100") == "Stasiun pantai"
    assert mmsi.jenis_mmsi("992571234") == "Alat bantu navigasi"
    assert mmsi.jenis_mmsi("970123456") == "Pemancar SAR (AIS-SART)"
    assert mmsi.jenis_mmsi("111234567") == "Pesawat SAR"
    assert mmsi.jenis_mmsi("1234") == mmsi.TIDAK_DIKETAHUI


def test_mid_unik_dan_valid():
    assert all(100 <= k <= 799 for k in mmsi.MID_NEGARA)
    assert mmsi.MID_NEGARA[466] == "Qatar"


@pytest.mark.parametrize("kode, kategori", [
    (70, "Kargo"), (79, "Kargo"), (80, "Tanker"), (89, "Tanker"), (60, "Penumpang"), (69, "Penumpang"),
    (30, "Nelayan"), (31, "Tunda & servis"), (52, "Tunda & servis"), (35, "Militer & penegak hukum"),
    (55, "Militer & penegak hukum"), (51, "Militer & penegak hukum"), (40, "Kecepatan tinggi"),
    (36, "Rekreasi"), (37, "Rekreasi"), (90, mmsi.KATEGORI_LAIN), (25, mmsi.KATEGORI_LAIN),
    (0, mmsi.TIDAK_DIKETAHUI), (None, mmsi.TIDAK_DIKETAHUI), (float("nan"), mmsi.TIDAK_DIKETAHUI),
    ("x", mmsi.TIDAK_DIKETAHUI), (70.0, "Kargo"),
])
def test_kategori_tipe(kode, kategori):
    assert mmsi.kategori_tipe(kode) == kategori


def test_nama_tipe():
    assert mmsi.nama_tipe(81) == "Tanker (kargo berbahaya A)"
    assert mmsi.nama_tipe(70) == "Kargo"
    assert mmsi.nama_tipe(52) == "Kapal tunda"
    assert mmsi.nama_tipe(22) == "Wing in ground (WIG)"
    assert mmsi.nama_tipe(None) == mmsi.TIDAK_DIKETAHUI


def test_semua_kategori_ada_di_urutan():
    for nama in list(mmsi.KATEGORI_TIPE) + list(mmsi.KODE_TUNGGAL.values()):
        assert nama in mmsi.URUTAN_KATEGORI


def test_status_navigasi():
    assert mmsi.status_navigasi(0) == "Berlayar dengan mesin"
    assert mmsi.status_navigasi(1) == "Berlabuh jangkar"
    assert mmsi.status_navigasi(5) == "Tertambat"
    assert mmsi.status_navigasi(99) == "Tidak tersedia"
    assert mmsi.status_navigasi(None) == "Tidak tersedia"
    assert mmsi.status_navigasi(float("nan")) == "Tidak tersedia"
