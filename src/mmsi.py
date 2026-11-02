"""Kamus AIS: negara bendera dari MMSI, kategori tipe kapal, dan status navigasi.

Semua pemetaan di sini berasal dari standar publik ITU-R M.585 (Maritime Identification Digits)
dan ITU-R M.1371 (tipe kapal dan status navigasi), bukan dari basis data registrasi kapal.
"""

from __future__ import annotations

TIDAK_DIKETAHUI = "Tidak diketahui"

# Tiga digit pertama MMSI (MID) menunjukkan negara yang mengeluarkan identitas kapal.
# Daftar ini mencakup negara yang lazim terlihat di Selat Malaka dan bendera kemudahan
# (flag of convenience) utama; MID lain diberi label "Tidak diketahui".
MID_NEGARA: dict[int, str] = {
    # Asia Tenggara
    525: "Indonesia",
    533: "Malaysia",
    563: "Singapura", 564: "Singapura", 565: "Singapura", 566: "Singapura",
    567: "Thailand",
    574: "Vietnam",
    548: "Filipina",
    514: "Kamboja", 515: "Kamboja",
    506: "Myanmar",
    508: "Brunei",
    # Asia Timur & Selatan
    412: "Tiongkok", 413: "Tiongkok", 414: "Tiongkok",
    477: "Hong Kong",
    453: "Makau",
    416: "Taiwan",
    431: "Jepang", 432: "Jepang",
    440: "Korea Selatan", 441: "Korea Selatan",
    445: "Korea Utara",
    419: "India",
    463: "Pakistan",
    405: "Bangladesh",
    417: "Sri Lanka",
    455: "Maladewa",
    # Timur Tengah
    403: "Arab Saudi",
    470: "Uni Emirat Arab", 471: "Uni Emirat Arab",
    422: "Iran",
    425: "Irak",
    466: "Qatar",
    438: "Yordania",
    436: "Kuwait",
    408: "Bahrain",
    461: "Oman",
    473: "Yaman", 475: "Yaman",
    428: "Israel",
    271: "Turki",
    # Bendera kemudahan utama
    351: "Panama", 352: "Panama", 353: "Panama", 354: "Panama", 355: "Panama", 356: "Panama",
    357: "Panama", 370: "Panama", 371: "Panama", 372: "Panama", 373: "Panama", 374: "Panama",
    636: "Liberia", 637: "Liberia",
    538: "Kepulauan Marshall",
    209: "Siprus", 210: "Siprus", 212: "Siprus",
    215: "Malta", 229: "Malta", 248: "Malta", 249: "Malta", 256: "Malta",
    308: "Bahama", 309: "Bahama", 311: "Bahama",
    377: "Saint Vincent & Grenadines",
    375: "Saint Vincent & Grenadines", 376: "Saint Vincent & Grenadines",
    341: "Saint Kitts & Nevis",
    314: "Barbados",
    304: "Antigua & Barbuda", 305: "Antigua & Barbuda",
    312: "Belize",
    667: "Sierra Leone",
    677: "Tanzania", 674: "Tanzania",
    620: "Komoro",
    572: "Tuvalu",
    518: "Kepulauan Cook",
    529: "Kiribati",
    536: "Kepulauan Mariana Utara",
    319: "Kepulauan Cayman",
    378: "Kepulauan Virgin Britania",
    339: "Jamaika",
    613: "Kamerun",
    616: "Komoro",
    611: "Guinea",
    657: "Nigeria",
    654: "Mauritania",
    659: "Gabon",
    642: "Libya",
    619: "Pantai Gading",
    # Eropa & lainnya
    232: "Britania Raya", 233: "Britania Raya", 234: "Britania Raya", 235: "Britania Raya",
    227: "Prancis", 228: "Prancis",
    211: "Jerman", 218: "Jerman",
    244: "Belanda", 245: "Belanda", 246: "Belanda",
    219: "Denmark", 220: "Denmark",
    257: "Norwegia", 258: "Norwegia", 259: "Norwegia",
    231: "Kepulauan Faroe",
    265: "Swedia", 266: "Swedia",
    230: "Finlandia",
    237: "Yunani", 239: "Yunani", 240: "Yunani", 241: "Yunani",
    247: "Italia",
    224: "Spanyol", 225: "Spanyol",
    255: "Portugal (Madeira)", 263: "Portugal",
    205: "Belgia",
    253: "Luksemburg",
    269: "Swiss",
    273: "Rusia",
    272: "Ukraina",
    261: "Polandia",
    275: "Latvia", 276: "Estonia", 277: "Lituania",
    338: "Amerika Serikat", 366: "Amerika Serikat", 367: "Amerika Serikat", 368: "Amerika Serikat", 369: "Amerika Serikat",
    316: "Kanada",
    345: "Meksiko",
    503: "Australia",
    512: "Selandia Baru",
    553: "Papua Nugini",
    601: "Afrika Selatan",
    622: "Mesir",
    710: "Brasil",
    725: "Chili",
    701: "Argentina",
}

# Awalan MMSI khusus (bukan kapal biasa), lihat ITU-R M.585.
AWALAN_KHUSUS: dict[str, str] = {
    "00": "Stasiun pantai",
    "0": "Kelompok kapal",
    "111": "Pesawat SAR",
    "99": "Alat bantu navigasi",
    "98": "Kapal tender",
    "970": "Pemancar SAR (AIS-SART)",
    "972": "Pemancar MOB",
    "974": "EPIRB-AIS",
}


def jenis_mmsi(mmsi: int | str | None) -> str:
    """Membedakan MMSI kapal dari stasiun pantai, pelampung navigasi, atau pemancar darurat."""
    s = str(mmsi or "").strip()
    if not s.isdigit() or len(s) != 9:
        return TIDAK_DIKETAHUI
    for awalan in ("970", "972", "974", "111", "00", "99", "98", "0"):
        if s.startswith(awalan):
            return AWALAN_KHUSUS[awalan]
    return "Kapal"


def negara_bendera(mmsi: int | str | None) -> str:
    """Negara bendera dari tiga digit pertama MMSI; MMSI khusus dan tidak valid menjadi 'Tidak diketahui'."""
    s = str(mmsi or "").strip()
    if not s.isdigit() or len(s) != 9 or jenis_mmsi(s) != "Kapal":
        return TIDAK_DIKETAHUI
    return MID_NEGARA.get(int(s[:3]), TIDAK_DIKETAHUI)


# Kategori tipe kapal dari kode AIS 0-99 (ITU-R M.1371, pesan 5).
KATEGORI_LAIN = "Lainnya"
KATEGORI_TIPE: dict[str, tuple[int, int]] = {
    "Kargo": (70, 79),
    "Tanker": (80, 89),
    "Penumpang": (60, 69),
    "Nelayan": (30, 30),
    "Tunda & servis": (31, 32),  # kapal tunda yang menarik (towing)
    "Militer & penegak hukum": (35, 35),
    "Kecepatan tinggi": (40, 49),
    "Rekreasi": (36, 37),
}
# Beberapa kode tunggal yang tidak membentuk rentang rapi.
KODE_TUNGGAL: dict[int, str] = {
    33: "Tunda & servis",     # dredging / underwater ops
    34: "Tunda & servis",     # diving ops
    50: "Tunda & servis",     # pilot vessel
    51: "Militer & penegak hukum",  # SAR
    52: "Tunda & servis",     # tug
    53: "Tunda & servis",     # port tender
    54: "Tunda & servis",     # anti-pollution
    55: "Militer & penegak hukum",  # law enforcement
    56: "Tunda & servis", 57: "Tunda & servis",
    58: "Tunda & servis",     # medical transport
    59: "Lainnya",            # non-combatant ship (RR Resolution 18)
}
# Kode pesan "WIG" (20-29) jarang: dianggap "Lainnya".

URUTAN_KATEGORI = ["Kargo", "Tanker", "Penumpang", "Nelayan", "Tunda & servis",
                   "Kecepatan tinggi", "Rekreasi", "Militer & penegak hukum", KATEGORI_LAIN, TIDAK_DIKETAHUI]

# Nama rinci untuk kode tertentu agar popup lebih informatif.
NAMA_TIPE: dict[int, str] = {
    0: "Tidak tersedia", 30: "Kapal ikan", 31: "Kapal tunda (menarik)", 32: "Kapal tunda (tarikan panjang)",
    33: "Kapal keruk", 34: "Operasi penyelaman", 35: "Operasi militer", 36: "Kapal layar", 37: "Kapal pesiar",
    50: "Kapal pandu", 51: "Kapal SAR", 52: "Kapal tunda", 53: "Tender pelabuhan", 54: "Anti-polusi",
    55: "Penegak hukum", 58: "Transportasi medis", 59: "Kapal non-tempur",
}


def kategori_tipe(kode: int | float | None) -> str:
    """Kode tipe kapal AIS (0-99) menjadi kategori ringkas untuk legenda."""
    if kode is None or kode != kode:  # None atau NaN
        return TIDAK_DIKETAHUI
    try:
        k = int(kode)
    except (TypeError, ValueError):
        return TIDAK_DIKETAHUI
    if k <= 0:
        return TIDAK_DIKETAHUI
    if k in KODE_TUNGGAL:
        return KODE_TUNGGAL[k]
    for nama, (lo, hi) in KATEGORI_TIPE.items():
        if lo <= k <= hi:
            return nama
    return KATEGORI_LAIN


def nama_tipe(kode: int | float | None) -> str:
    """Nama tipe yang lebih rinci, misalnya 'Tanker (kargo berbahaya kategori A)'."""
    if kode is None or kode != kode:
        return TIDAK_DIKETAHUI
    k = int(kode)
    if k in NAMA_TIPE:
        return NAMA_TIPE[k]
    kategori = kategori_tipe(k)
    if kategori in ("Kargo", "Tanker", "Penumpang", "Kecepatan tinggi"):
        akhiran = {1: " (kargo berbahaya A)", 2: " (kargo berbahaya B)", 3: " (kargo berbahaya C)", 4: " (kargo berbahaya D)"}
        return f"{kategori}{akhiran.get(k % 10, '')}"
    if 20 <= k <= 29:
        return "Wing in ground (WIG)"
    return f"{kategori} (kode {k})"


# Status navigasi (pesan 1/2/3 AIS).
STATUS_NAVIGASI: dict[int, str] = {
    0: "Berlayar dengan mesin",
    1: "Berlabuh jangkar",
    2: "Tidak terkendali",
    3: "Olah gerak terbatas",
    4: "Terbatas oleh sarat",
    5: "Tertambat",
    6: "Kandas",
    7: "Sedang menangkap ikan",
    8: "Berlayar dengan layar",
    9: "Cadangan (HSC)",
    10: "Cadangan (WIG)",
    11: "Mesin mundur",
    12: "Mesin maju",
    13: "Cadangan",
    14: "AIS-SART aktif",
    15: "Tidak tersedia",
}


def status_navigasi(kode: int | float | None) -> str:
    if kode is None or kode != kode:
        return STATUS_NAVIGASI[15]
    try:
        return STATUS_NAVIGASI.get(int(kode), STATUS_NAVIGASI[15])
    except (TypeError, ValueError):
        return STATUS_NAVIGASI[15]
