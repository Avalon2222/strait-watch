"""Memuat data: pelabuhan dan titik kunci (CSV statis), sampel offline, atau aliran live aisstream.io.

Prinsip: aplikasi tidak boleh gagal hanya karena tidak ada kunci API, internet mati, atau server
menolak. Setiap pemanggilan live mempunyai cadangan sampel offline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src import ais, analisis

DIR_PROYEK = Path(__file__).resolve().parent.parent
DIR_DATA = DIR_PROYEK / "data"
FILE_PELABUHAN = DIR_DATA / "pelabuhan.csv"
FILE_TITIK = DIR_DATA / "titik_kunci.csv"
FILE_SAMPEL = DIR_DATA / "sample" / "posisi.csv"
FILE_SAMPEL_STATIS = DIR_DATA / "sample" / "kapal_statis.csv"

KOLOM_WAJIB = ["mmsi", "lat", "lon", "sog_knot", "cog", "waktu_snapshot"]


def muat_pelabuhan(path: Path = FILE_PELABUHAN) -> pd.DataFrame:
    """Pelabuhan dan pangkalan AL di sekitar selat (kolom ``jenis``: pelabuhan / pangkalan_al)."""
    df = pd.read_csv(path)
    wajib = {"kode", "nama", "kota", "negara", "jenis", "lat", "lon"}
    hilang = wajib - set(df.columns)
    if hilang:
        raise ValueError(f"Kolom pelabuhan hilang: {sorted(hilang)}")
    return df.dropna(subset=["lat", "lon"]).reset_index(drop=True)


def muat_titik_kunci(path: Path = FILE_TITIK) -> pd.DataFrame:
    return pd.read_csv(path)


def muat_sampel(path: Path = FILE_SAMPEL, path_statis: Path = FILE_SAMPEL_STATIS) -> pd.DataFrame:
    """Sampel offline: rekaman posisi (satu baris = satu kapal pada satu snapshot) digabung data statis."""
    df = pd.read_csv(path, dtype={"mmsi": str, "nama": str})
    hilang = set(KOLOM_WAJIB) - set(df.columns)
    if hilang:
        raise ValueError(f"Kolom sampel hilang: {sorted(hilang)}")
    df["mmsi"] = df["mmsi"].astype(str).str.strip()
    df["nama"] = df["nama"].fillna("").astype(str).str.strip()
    df["waktu_snapshot"] = pd.to_datetime(df["waktu_snapshot"], utc=True)
    if "waktu_pesan" in df:
        df["waktu_pesan"] = pd.to_datetime(df["waktu_pesan"], utc=True, errors="coerce")
    for k in ("heading", "status_nav_kode"):
        if k not in df:
            df[k] = None
    if "kelas" not in df:
        df["kelas"] = "A"
    if path_statis and Path(path_statis).exists():
        statis = pd.read_csv(path_statis, dtype={"mmsi": str, "nama_statis": str, "callsign": str, "tujuan": str})
        statis["mmsi"] = statis["mmsi"].astype(str).str.strip()
        df = df.merge(statis.drop_duplicates("mmsi"), on="mmsi", how="left")
        nama_statis = df["nama_statis"].fillna("").astype(str).str.strip()
        df["nama"] = nama_statis.where(nama_statis != "", df["nama"])
        df = df.drop(columns=["nama_statis"])
    for k in ais.KOLOM_STATIS[1:]:
        if k not in df and k != "nama_statis":
            df[k] = None
    return df.dropna(subset=["lat", "lon"]).reset_index(drop=True)


def info_sampel(df: pd.DataFrame) -> dict:
    """Ringkasan rekaman: jumlah snapshot, rentang waktu, kapal unik, baris."""
    if df.empty:
        return {"snapshot": 0, "mulai": None, "selesai": None, "kapal": 0, "baris": 0}
    return {
        "snapshot": int(df["waktu_snapshot"].nunique()),
        "mulai": df["waktu_snapshot"].min(),
        "selesai": df["waktu_snapshot"].max(),
        "kapal": int(df["mmsi"].nunique()),
        "baris": int(len(df)),
    }


def snapshot_terakhir(df: pd.DataFrame) -> pd.DataFrame:
    """Posisi "sekarang" dalam sampel: hanya baris dari snapshot paling akhir."""
    if df.empty:
        return df
    t = df["waktu_snapshot"].max()
    return df[df["waktu_snapshot"] == t].reset_index(drop=True)


def posisi_terakhir(df: pd.DataFrame, menit: float | None = None) -> pd.DataFrame:
    """Posisi terakhir setiap kapal (MMSI) dalam rekaman, opsional hanya yang terlihat ``menit`` terakhir.

    Pada sumber dengan penerima jarang, satu snapshot 20-60 detik hanya menangkap sebagian kecil kapal.
    "Posisi terakhir per kapal" selama beberapa menit memberi gambaran yang jauh lebih utuh.
    """
    if df.empty:
        return df
    d = df
    if menit is not None:
        d = d[d["waktu_snapshot"] >= d["waktu_snapshot"].max() - pd.Timedelta(minutes=menit)]
    return d.sort_values("waktu_snapshot").drop_duplicates("mmsi", keep="last").reset_index(drop=True)


def muat_live(api_key: str, durasi: int = ais.DURASI_DEFAULT, cache_statis: dict | None = None) -> tuple[pd.DataFrame, int]:
    """Satu snapshot live: dengarkan aliran selama ``durasi`` detik lalu rapikan ke DataFrame."""
    posisi, statis, jumlah = ais.kumpulkan(api_key, durasi=durasi, cache_statis=cache_statis)
    df = ais.ke_dataframe(posisi, statis, datetime.now(timezone.utc))
    return analisis.di_dalam_kotak(df).reset_index(drop=True), jumlah


def muat_live_atau_sampel(api_key: str | None, durasi: int = ais.DURASI_DEFAULT,
                          cache_statis: dict | None = None) -> tuple[pd.DataFrame, str, str]:
    """Mencoba live bila ada kunci; jika tidak ada atau gagal, memakai snapshot terakhir sampel.

    Mengembalikan (DataFrame satu snapshot, sumber, pesan), ``sumber`` = "live" atau "sampel".
    """
    if not api_key:
        return snapshot_terakhir(muat_sampel()), "sampel", "Kunci API aisstream.io belum diisi, menampilkan sampel offline."
    try:
        df, jumlah = muat_live(api_key, durasi, cache_statis)
        if df.empty:
            raise ais.AisError("Terhubung, tetapi tidak ada posisi kapal dalam kotak pantau.")
        return df, "live", f"Data live aisstream.io: {len(df)} kapal dari {jumlah:,} pesan dalam {durasi} detik."
    except ais.AisError as exc:
        return snapshot_terakhir(muat_sampel()), "sampel", f"{exc} Menampilkan sampel offline."


FILE_PORTWATCH = DIR_DATA / "portwatch_harian.csv"
FILE_PORTWATCH_RINGKAS = DIR_DATA / "portwatch_chokepoint.csv"


def muat_portwatch(path: Path = FILE_PORTWATCH) -> pd.DataFrame:
    """Transit harian IMF PortWatch (snapshot di repo, diperbarui mingguan oleh GitHub Actions)."""
    from src import portwatch

    if not Path(path).exists():
        return pd.DataFrame(columns=portwatch.KOLOM)
    return portwatch.rapikan(pd.read_csv(path))


def muat_portwatch_ringkas(path: Path = FILE_PORTWATCH_RINGKAS) -> pd.DataFrame:
    """Ringkasan setahun 28 chokepoint dunia dari basis data PortWatch."""
    if not Path(path).exists():
        return pd.DataFrame()
    return pd.read_csv(path)
