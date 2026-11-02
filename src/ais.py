"""Klien aisstream.io: membuka WebSocket, mengumpulkan pesan AIS selama beberapa detik, lalu merapikannya.

aisstream.io menyiarkan pesan AIS mentah (yang sudah di-decode menjadi JSON) dari ribuan
penerima sukarelawan. Tidak ada endpoint "snapshot": satu-satunya cara mendapat posisi adalah
mendengarkan aliran selama beberapa detik dan menyimpan posisi terakhir setiap kapal (MMSI).

Dua jenis pesan yang dipakai:
- PositionReport / StandardClassBPositionReport: posisi, kecepatan (SOG), haluan (COG), status navigasi.
  Dikirim tiap 2-10 detik oleh kapal yang bergerak, tiap 3 menit oleh kapal yang berlabuh.
- ShipStaticData: nama, tipe kapal, tujuan, dimensi, sarat. Dikirim hanya tiap 6 menit,
  sehingga pada pendengaran singkat banyak kapal belum punya tipe. Data statis disimpan antar
  pemanggilan (``cache_statis``) agar makin lama makin lengkap.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import pandas as pd

URL_STREAM = "wss://stream.aisstream.io/v0/stream"

# Kotak batas Selat Malaka dan Selat Singapura: dari Sabang (ujung utara Sumatera) sampai
# pintu timur Selat Singapura. Format aisstream: [[lat, lon] sudut barat daya, [lat, lon] sudut timur laut].
BBOX_SELAT = {"lamin": -1.5, "lamax": 7.5, "lomin": 95.0, "lomax": 105.5}
BOUNDING_BOXES = [[[BBOX_SELAT["lamin"], BBOX_SELAT["lomin"]], [BBOX_SELAT["lamax"], BBOX_SELAT["lomax"]]]]

TIPE_PESAN = ["PositionReport", "StandardClassBPositionReport", "ShipStaticData"]
DURASI_DEFAULT = 20  # detik mendengarkan per snapshot

KOLOM_POSISI = ["mmsi", "nama", "lat", "lon", "sog_knot", "cog", "heading", "status_nav_kode",
                "kelas", "waktu_pesan", "waktu_snapshot"]
KOLOM_STATIS = ["mmsi", "nama_statis", "callsign", "imo", "tipe_kode", "tujuan", "panjang_m", "lebar_m", "sarat_m"]


class AisError(RuntimeError):
    """Gagal terhubung atau tidak menerima pesan dari aisstream.io."""


def ambil_api_key() -> str | None:
    """Kunci API dari variabel lingkungan ``AISSTREAM_API_KEY`` (app.py mengisinya dari st.secrets)."""
    kunci = os.environ.get("AISSTREAM_API_KEY", "").strip()
    return kunci or None


def pesan_langganan(api_key: str, bounding_boxes=None, tipe_pesan=None) -> dict:
    """Pesan JSON pertama yang dikirim ke server untuk memilih wilayah dan jenis pesan."""
    return {
        "APIKey": api_key,
        "BoundingBoxes": bounding_boxes or BOUNDING_BOXES,
        "FilterMessageTypes": tipe_pesan or TIPE_PESAN,
    }


def _angka(v, default=None):
    try:
        if v is None:
            return default
        f = float(v)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def _bersihkan_teks(v) -> str:
    """Nama/tujuan AIS diisi dengan '@' atau spasi sampai 20 karakter; buang semuanya."""
    return str(v or "").replace("@", "").strip()


def _waktu_meta(meta: dict) -> pd.Timestamp | None:
    """``time_utc`` aisstream berbentuk '2024-01-01 12:34:56.123456789 +0000 UTC'; ambil detiknya saja."""
    teks = str(meta.get("time_utc", ""))[:19]
    try:
        return pd.Timestamp(teks, tz="UTC")
    except (ValueError, TypeError):
        return None


def urai_pesan(pesan: dict) -> tuple[str, dict] | None:
    """Satu pesan aisstream menjadi ('posisi', {...}) atau ('statis', {...}); None jika tidak dipakai.

    Nilai "tidak tersedia" menurut standar AIS (SOG 102,3; COG 360; heading 511; lat 91; lon 181)
    diubah menjadi None agar tidak merusak peta dan statistik.
    """
    tipe = pesan.get("MessageType")
    meta = pesan.get("MetaData") or {}
    isi = (pesan.get("Message") or {}).get(tipe) or {}
    mmsi = meta.get("MMSI") or isi.get("UserID")
    if not mmsi:
        return None
    mmsi = str(mmsi)

    if tipe in ("PositionReport", "StandardClassBPositionReport"):
        lat = _angka(isi.get("Latitude", meta.get("latitude")))
        lon = _angka(isi.get("Longitude", meta.get("longitude")))
        if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
            return None
        sog = _angka(isi.get("Sog"))
        cog = _angka(isi.get("Cog"))
        heading = _angka(isi.get("TrueHeading"))
        return "posisi", {
            "mmsi": mmsi,
            "nama": _bersihkan_teks(meta.get("ShipName")),
            "lat": lat,
            "lon": lon,
            "sog_knot": None if sog is None or sog >= 102.3 else sog,
            "cog": None if cog is None or cog >= 360 else cog,
            "heading": None if heading is None or heading >= 360 else heading,
            "status_nav_kode": None if tipe != "PositionReport" else _angka(isi.get("NavigationalStatus")),
            "kelas": "A" if tipe == "PositionReport" else "B",
            "waktu_pesan": _waktu_meta(meta),
        }

    if tipe == "ShipStaticData":
        dim = isi.get("Dimension") or {}
        a, b, c, d = (_angka(dim.get(k), 0) for k in ("A", "B", "C", "D"))
        panjang = (a or 0) + (b or 0)
        lebar = (c or 0) + (d or 0)
        sarat = _angka(isi.get("MaximumStaticDraught"))
        return "statis", {
            "mmsi": mmsi,
            "nama_statis": _bersihkan_teks(isi.get("Name") or meta.get("ShipName")),
            "callsign": _bersihkan_teks(isi.get("CallSign")),
            "imo": int(isi["ImoNumber"]) if _angka(isi.get("ImoNumber")) else None,
            "tipe_kode": int(isi["Type"]) if _angka(isi.get("Type")) is not None else None,
            "tujuan": _bersihkan_teks(isi.get("Destination")),
            "panjang_m": panjang or None,
            "lebar_m": lebar or None,
            "sarat_m": sarat if sarat else None,
        }
    return None


def kumpulkan(api_key: str, durasi: int = DURASI_DEFAULT, bounding_boxes=None,
              cache_statis: dict[str, dict] | None = None, maks_pesan: int = 200_000) -> tuple[dict, dict, int]:
    """Mendengarkan aisstream.io selama ``durasi`` detik.

    Mengembalikan (posisi_per_mmsi, statis_per_mmsi, jumlah_pesan). ``cache_statis`` yang diberikan
    akan diperbarui di tempat sehingga data statis dari pemanggilan sebelumnya tidak hilang.
    """
    try:
        from websockets.sync.client import connect
        from websockets.exceptions import WebSocketException
    except ImportError as exc:  # pragma: no cover
        raise AisError("Paket 'websockets' belum terpasang.") from exc

    posisi: dict[str, dict] = {}
    statis: dict[str, dict] = cache_statis if cache_statis is not None else {}
    jumlah = 0
    batas = time.monotonic() + durasi
    try:
        with connect(URL_STREAM, compression="deflate", open_timeout=15, close_timeout=3) as ws:
            ws.send(json.dumps(pesan_langganan(api_key, bounding_boxes)))
            while True:
                sisa = batas - time.monotonic()
                if sisa <= 0 or jumlah >= maks_pesan:
                    break
                try:
                    mentah = ws.recv(timeout=min(sisa, 5))
                except TimeoutError:
                    continue
                try:
                    pesan = json.loads(mentah)
                except json.JSONDecodeError:
                    continue
                if "error" in pesan and "MessageType" not in pesan:
                    raise AisError(f"aisstream.io menolak: {pesan['error']}")
                hasil = urai_pesan(pesan)
                jumlah += 1
                if hasil is None:
                    continue
                jenis, baris = hasil
                if jenis == "posisi":
                    posisi[baris["mmsi"]] = baris
                else:
                    statis[baris["mmsi"]] = baris
    except AisError:
        raise
    except (WebSocketException, OSError, TimeoutError) as exc:
        if jumlah == 0:
            raise AisError(f"Tidak dapat terhubung ke aisstream.io ({type(exc).__name__}: {exc}).") from exc
    if jumlah == 0:
        raise AisError("Terhubung, tetapi tidak ada pesan diterima. Kunci API mungkin salah atau kuota habis.")
    return posisi, statis, jumlah


def ke_dataframe(posisi: dict[str, dict], statis: dict[str, dict] | None = None,
                 waktu_snapshot: datetime | None = None) -> pd.DataFrame:
    """Gabungkan posisi terakhir dan data statis menjadi satu baris per kapal."""
    waktu_snapshot = waktu_snapshot or datetime.now(timezone.utc)
    if not posisi:
        return pd.DataFrame(columns=KOLOM_POSISI + KOLOM_STATIS[1:])
    df = pd.DataFrame(list(posisi.values()))
    df["waktu_snapshot"] = pd.Timestamp(waktu_snapshot).tz_convert("UTC") if pd.Timestamp(waktu_snapshot).tzinfo \
        else pd.Timestamp(waktu_snapshot, tz="UTC")
    if statis:
        ds = pd.DataFrame(list(statis.values()))
        df = df.merge(ds, on="mmsi", how="left")
    else:
        for k in KOLOM_STATIS[1:]:
            df[k] = None
    # Nama: utamakan dari pesan statis, lalu dari MetaData.
    nama_statis = df["nama_statis"].fillna("").astype(str)
    df["nama"] = nama_statis.where(nama_statis != "", df["nama"].fillna("").astype(str))
    df = df.drop(columns=["nama_statis"])
    df["waktu_pesan"] = pd.to_datetime(df["waktu_pesan"], utc=True, errors="coerce")
    return df.reset_index(drop=True)
