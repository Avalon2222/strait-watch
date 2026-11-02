# 🏋️ Latihan

Diurutkan dari yang mudah ke yang lebih menantang. Setiap latihan dilengkapi petunjuk dan kunci jawaban yang dapat
dibuka. Usahakan mencoba minimal 10 menit sebelum membuka kunci. Setelah setiap latihan, jalankan
`python -m pytest tests/ -v` dan `streamlit run app.py`.

Tingkat: ⭐ cukup edit data/teks · ⭐⭐ ubah kode yang ada · ⭐⭐⭐ tulis fungsi dan tes baru

---

### Latihan 1 — Menambah pelabuhan (cukup edit CSV) ⭐

Tambahkan **Pelabuhan Tanjung Buton** di Siak, Riau (kode `IDTBN`, kota `Siak`, lat `0.92`, lon `102.15`) ke
`data/pelabuhan.csv`. Buka halaman Data & sources dan pastikan ia muncul di tabel titik acuan, lalu cek peta: ada titik
putih baru di pantai timur Sumatera.

<details><summary>Petunjuk</summary>
Satu baris baru dengan urutan kolom <code>kode,nama,kota,negara,jenis,lat,lon</code>; nilai <code>jenis</code> adalah <code>pelabuhan</code>. Tidak ada koma di dalam nilai, jadi tidak perlu tanda kutip.
</details>

<details><summary>Kunci</summary>

```
IDTBN,Pelabuhan Tanjung Buton,Siak,Indonesia,pelabuhan,0.92,102.15
```
Tes `test_pelabuhan_csv_valid` memeriksa koordinat masih di dalam kotak dan kode tetap unik.
</details>

---

### Latihan 2 — Menambah negara ke tabel MID ⭐

Kapal berbendera **Vanuatu** (MID `576`) cukup sering terlihat di Asia. Tambahkan ke `MID_NEGARA` di `src/mmsi.py`
agar MMSI seperti `576123456` tidak lagi "Tidak diketahui".

<details><summary>Petunjuk</summary>
Format tiap entri: <code>576: "Vanuatu",</code>. Letakkan di blok bendera kemudahan. Periksa dengan <code>python -c "from src import mmsi; print(mmsi.negara_bendera('576123456'))"</code>.
</details>

<details><summary>Kunci</summary>

```python
576: "Vanuatu",
```
Tambahkan juga satu kasus ke `test_negara_bendera_dikenal` di `tests/test_mmsi.py`: `("576123456", "Vanuatu")`.
</details>

---

### Latihan 3 — Mengubah ambang fase pelayaran ⭐

Ambang "Lambat" saat ini 5 knot. Ubah `AMBANG_LAMBAT` di `src/analisis.py` menjadi 3 knot dan lihat berapa banyak kapal
yang berpindah dari "Lambat" ke "Berlayar" di halaman Who rules the strait (mode sampel). Lalu kembalikan ke 5.

<details><summary>Petunjuk</summary>
Konstanta ada di bagian atas file. Tes <code>test_fase_pelayaran</code> memakai 3,0 knot sebagai contoh "Lambat", jadi tes itu akan gagal pada ambang 3 (3,0 tidak lagi &lt; 3). Pikirkan: apakah tes perlu diubah, atau ambangnya yang salah?
</details>

<details><summary>Kunci</summary>
Dengan ambang 3, kasus uji <code>(3.0, 0, "Lambat")</code> harus menjadi <code>"Berlayar"</code>. Pelajarannya: tes yang memakai nilai tepat di ambang sensitif terhadap perubahan ambang; nilai uji yang jauh dari ambang (misalnya 1,5 dan 8) lebih tahan lama.
</details>

---

### Latihan 4 — KPI baru: kecepatan rata-rata kapal bergerak ⭐⭐

Tambahkan kartu metrik ketujuh di `app.py`: **kecepatan rata-rata (knot)** kapal yang sedang berlayar atau lambat dalam
snapshot terkini.

<details><summary>Petunjuk</summary>
Ubah <code>st.columns([...])</code> menjadi 7 kolom. Saring <code>terkini_f[terkini_f["fase"].isin(["Berlayar", "Lambat"])]</code>, lalu <code>["sog_knot"].mean()</code>. Tangani hasil kosong (NaN) dengan menampilkan "-".
</details>

<details><summary>Kunci</summary>

```python
bergerak = terkini_f[terkini_f["fase"].isin(["Berlayar", "Lambat"])].drop_duplicates("mmsi")
rata = pd.to_numeric(bergerak["sog_knot"], errors="coerce").mean()
k7.metric("Kecepatan rata-rata", f"{rata:.1f} knot" if pd.notna(rata) else "-")
```
</details>

---

### Latihan 5 — Filter "hanya kapal besar" ⭐⭐

Tambahkan slider **Panjang minimum (m)** di sidebar yang menyembunyikan kapal dengan `panjang_m` di bawah nilai itu.
Kapal tanpa data dimensi (NaN) harus tetap tampil saat slider di 0, dan disembunyikan saat slider di atas 0.

<details><summary>Petunjuk</summary>
Tambahkan slider di blok Filter dan satu cabang baru di <code>terapkan_filter</code>. <code>pd.to_numeric(..., errors="coerce").fillna(0) >= minimum</code> membuat NaN menjadi 0, sehingga perilaku "tampil hanya di 0" otomatis terpenuhi.
</details>

<details><summary>Kunci</summary>

```python
panjang_min = st.slider("Min. length (m)", 0, 400, 0, 10)
...
if panjang_min > 0:
    hasil = hasil[pd.to_numeric(hasil["panjang_m"], errors="coerce").fillna(0) >= panjang_min]
```
</details>

---

### Latihan 6 — Kapal "diam di tengah jalur" ⭐⭐

Di halaman Chokepoints & bases, tambahkan tabel kapal yang **diam** (fase Diam/Berlabuh jangkar) dalam radius 15 km dari
titik "Bagian tersempit (Selat Phillip)". Kapal berlabuh di jalur tersempit adalah hal yang pantas dilihat.

<details><summary>Petunjuk</summary>
Ambil baris titik dari <code>titik_kunci</code> dengan <code>kode == "SEMPIT"</code>, panggil <code>analisis.kapal_di_sekitar(terkini_f, lat, lon, 15)</code>, lalu saring fase. Tampilkan kolom label, bendera, kategori, fase, jarak_km.
</details>

<details><summary>Kunci</summary>

```python
sempit = titik_kunci[titik_kunci["kode"] == "SEMPIT"].iloc[0]
diam = analisis.kapal_di_sekitar(terkini_f, sempit["lat"], sempit["lon"], 15)
diam = diam[diam["fase"].isin(["Diam", "Berlabuh jangkar", "Tertambat"])]
st.dataframe(diam[["label", "bendera", "kategori", "fase", "jarak_km"]], hide_index=True)
```
Catatan: area labuh jangkar resmi Singapura memang berada di dekat sini, jadi daftar ini normalnya tidak kosong.
</details>

---

### Latihan 7 — Tes untuk `ke_dataframe` saat nama statis kosong ⭐⭐

`ais.ke_dataframe` mengutamakan nama dari pesan statis. Apa yang terjadi bila pesan statis ada tetapi `Name`-nya kosong
(`"@@@@@@@@"`)? Tulis tes di `tests/test_ais.py` yang memastikan nama dari MetaData tetap dipakai.

<details><summary>Petunjuk</summary>
Pakai <code>pesan_statis(nama="@@@@@@@@")</code> dan <code>pesan_posisi(nama="DARI META")</code>, gabungkan lewat <code>ke_dataframe</code>, lalu periksa kolom <code>nama</code>.
</details>

<details><summary>Kunci</summary>

```python
def test_nama_statis_kosong_pakai_meta():
    _, p = ais.urai_pesan(pesan_posisi(nama="DARI META"))
    _, s = ais.urai_pesan(pesan_statis(nama="@@@@@@@@"))
    df = ais.ke_dataframe({p["mmsi"]: p}, {s["mmsi"]: s})
    assert df.loc[0, "nama"] == "DARI META"
```
Tes ini lulus karena `_bersihkan_teks` mengubah `"@@@@@@@@"` menjadi `""`, dan `ke_dataframe` memakai nama MetaData bila nama statis kosong.
</details>

---

### Latihan 8 — Arah dominan lalu lintas per sel ⭐⭐⭐

Buat fungsi `arah_dominan(df, ukuran_deg)` di `src/analisis.py` yang, untuk setiap sel grid, menghitung **arah
rata-rata** kapal yang bergerak (SOG ≥ 5 knot). Hasilnya menunjukkan jalur ke tenggara dan ke barat laut dari traffic
separation scheme. Tulis tesnya.

<details><summary>Petunjuk</summary>
Rata-rata sudut tidak boleh dihitung dengan <code>mean()</code> biasa (rata-rata 350° dan 10° adalah 0°, bukan 180°). Ubah ke vektor: <code>x = cos(rad)</code>, <code>y = sin(rad)</code>, rata-ratakan, lalu <code>atan2(y, x)</code> kembali ke derajat dan <code>% 360</code>.
</details>

<details><summary>Kunci</summary>

```python
def arah_dominan(df, ukuran_deg=0.25, sog_min=5.0):
    g = df[(pd.to_numeric(df["sog_knot"], errors="coerce") >= sog_min) & df["cog"].notna()].copy()
    if g.empty:
        return pd.DataFrame(columns=["lat_tengah", "lon_tengah", "arah", "kapal"])
    rad = np.radians(g["cog"].astype(float))
    g["x"], g["y"] = np.cos(rad), np.sin(rad)
    g["lat_sel"] = np.floor(g["lat"] / ukuran_deg)
    g["lon_sel"] = np.floor(g["lon"] / ukuran_deg)
    agg = g.groupby(["lat_sel", "lon_sel"]).agg(x=("x", "mean"), y=("y", "mean"), kapal=("mmsi", "nunique")).reset_index()
    agg["arah"] = (np.degrees(np.arctan2(agg["y"], agg["x"])) % 360).round(0)
    agg["lat_tengah"] = (agg["lat_sel"] + 0.5) * ukuran_deg
    agg["lon_tengah"] = (agg["lon_sel"] + 0.5) * ukuran_deg
    return agg[["lat_tengah", "lon_tengah", "arah", "kapal"]]
```
Tes: dua kapal di sel yang sama dengan COG 350 dan 10 harus menghasilkan arah 0 (bukan 180). Bonus: gambar panah per sel dengan `ikon_kapal` di peta heatmap.
</details>

---

### Latihan 9 — Deteksi kapal yang "menghilang" antar snapshot ⭐⭐⭐

Dalam mode live, buat fungsi `hilang_antara(sebelum, sesudah, sog_min=5)` yang mengembalikan kapal yang ada di snapshot
sebelumnya **sedang bergerak** tetapi tidak muncul di snapshot berikutnya. Ini pendekatan paling sederhana untuk
"AIS gap" yang dipakai analis maritim, dengan semua keterbatasannya.

<details><summary>Petunjuk</summary>
<code>set(sebelum["mmsi"]) - set(sesudah["mmsi"])</code> memberi MMSI yang hilang; saring yang SOG-nya ≥ 5 pada snapshot sebelum. Pikirkan mengapa kapal berlabuh (melapor tiap 3 menit) harus dikecualikan: pada pendengaran 20 detik mereka wajar tidak terdengar.
</details>

<details><summary>Kunci</summary>

```python
def hilang_antara(sebelum, sesudah, sog_min=5.0):
    bergerak = sebelum[pd.to_numeric(sebelum["sog_knot"], errors="coerce") >= sog_min]
    hilang = set(bergerak["mmsi"]) - set(sesudah["mmsi"])
    return bergerak[bergerak["mmsi"].isin(hilang)].drop_duplicates("mmsi")
```
Peringatan untuk dituliskan di UI: kapal yang keluar dari kotak batas, keluar dari jangkauan penerima, atau sekadar tidak tertangkap dalam 20 detik juga akan "hilang". Ini petunjuk, bukan bukti.
</details>

---

### Latihan 10 — Peta lebih ringan dengan clustering ⭐⭐⭐

Pada jam sibuk Selat Malaka bisa menampilkan 3.000+ kapal, dan 3.000 DivIcon membuat peta berat. Tambahkan opsi
**Cluster markers** di sidebar yang mengganti marker individual dengan `folium.plugins.MarkerCluster` saat jumlah kapal
di atas 1.500, sambil mempertahankan popup.

<details><summary>Petunjuk</summary>
<code>from folium.plugins import MarkerCluster</code>; buat <code>MarkerCluster(name=kategori)</code> sebagai pengganti <code>FeatureGroup</code> di <code>peta.peta_kapal</code> ketika parameter baru <code>cluster=True</code>. Marker ditambahkan ke cluster dengan cara yang sama (<code>.add_to(cluster)</code>).
</details>

<details><summary>Kunci</summary>

```python
def peta_kapal(df, pelabuhan=None, titik_kunci=None, pusat=PUSAT_SELAT, zoom=ZOOM_AWAL, sorot_indonesia=True, cluster=False):
    ...
    Wadah = MarkerCluster if cluster else folium.FeatureGroup
    fg = lapisan.setdefault(kategori, Wadah(name=kategori))
```
Di `app.py`: `cluster = st.checkbox("Cluster markers", value=len(terkini_f) > 1500)`. Ikon yang berputar hilang saat ter-cluster (digantikan angka), tetapi muncul kembali saat diperbesar.
</details>

---

### Latihan 11 — Menambah Selat Balabac ke data transit ⭐⭐

PortWatch juga menghitung **Balabac Strait** (`chokepoint25`), jalur antara Kalimantan utara dan Palawan yang dipakai
kapal yang menghindari Laut Cina Selatan bagian tengah. Tambahkan ke kamus `SELAT` di `src/portwatch.py` sebagai
pembanding, jalankan `python scripts/perbarui_portwatch.py`, dan lihat apakah ia muncul di halaman Strait traffic.

<details><summary>Petunjuk</summary>
Format entri: <code>"chokepoint25": {"nama": "Selat Balabac", "grup": "Pembanding", "alki": "-"}</code>. Tes <code>test_snapshot_repo_valid</code> memeriksa bahwa setiap <code>portid</code> di CSV ada di kamus <code>SELAT</code>.
</details>

<details><summary>Kunci</summary>
Satu baris di kamus sudah cukup karena <code>ambil_harian</code> mengulang semua kunci <code>SELAT</code>. Pikirkan juga: mengapa lebih baik data diunduh lewat skrip dan disimpan sebagai CSV daripada diambil langsung setiap kali aplikasi dibuka?
</details>
