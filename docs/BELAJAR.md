# 📚 Belajar dari Strait Watch

Panduan ini membaca proyek dari bawah ke atas: dari sinyal radio di kapal, aliran WebSocket, standar yang membuat angka
mentah bermakna, sampai peta dan grafik. Setiap bagian menunjuk file dan fungsi yang bisa langsung dibuka.
Tidak perlu latar belakang pelayaran; yang diperlukan hanya Python dasar dan pandas.

## 1. Apa itu AIS, dan mengapa siapa saja bisa melihatnya

**AIS** (Automatic Identification System) adalah pemancar radio VHF di kapal. Konvensi SOLAS mewajibkannya pada kapal
niaga di atas 300 GT dan semua kapal penumpang; kapal kecil memakai **AIS kelas B** yang lebih sederhana. Setiap kapal
menyiarkan dua jenis pesan:

| Jenis | Isi | Seberapa sering |
|---|---|---|
| Laporan posisi (pesan 1/2/3 kelas A, pesan 18 kelas B) | posisi GPS, SOG (speed over ground), COG (course over ground), heading, status navigasi | tiap 2–10 detik saat bergerak, tiap 3 menit saat berlabuh |
| Data statis (pesan 5) | nama, callsign, nomor IMO, tipe kapal, tujuan, dimensi, sarat | tiap 6 menit |

Tujuannya keselamatan: kapal lain dan otoritas pantai tahu siapa yang ada di sekitar. Karena sinyalnya tidak terenkripsi,
penerima murah di pantai bisa menangkapnya, dan jaringan seperti **aisstream.io** mengumpulkan sinyal dari ribuan
penerima sukarelawan lalu menyiarkannya ulang lewat internet.

Dua konsekuensi yang menentukan bentuk aplikasi ini:

1. **Tidak ada "snapshot"**: aliran hanya meneruskan pesan saat tiba. Untuk mendapat "semua kapal sekarang", kita
   harus mendengarkan beberapa detik dan menyimpan pesan terakhir setiap kapal.
2. **Dua jenis pesan datang terpisah**: posisi hampir selalu tertangkap dalam 20 detik, data statis belum tentu.
   Karena itu "tipe kapal" sering kosong pada awalnya dan perlu digabung dengan data yang pernah diterima sebelumnya.

## 2. Mendengarkan WebSocket dengan batas waktu (`src/ais.py`)

Berbeda dengan `requests.get(url)` yang selesai setelah satu jawaban, WebSocket adalah sambungan dua arah yang tetap
terbuka. Alurnya:

```python
from websockets.sync.client import connect

with connect("wss://stream.aisstream.io/v0/stream", compression="deflate", open_timeout=15) as ws:
    ws.send(json.dumps({"APIKey": kunci, "BoundingBoxes": [[[-1.5, 95.0], [7.5, 105.5]]],
                        "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport", "ShipStaticData"]}))
    batas = time.monotonic() + durasi
    while time.monotonic() < batas:
        pesan = json.loads(ws.recv(timeout=5))
        ...
```

Hal yang perlu dicermati:

- **Pesan pertama adalah langganan**: kunci API, kotak batas (pasangan `[lat, lon]` sudut barat daya dan timur laut),
  dan jenis pesan yang diinginkan. Tanpa filter jenis, server mengirim semua 27 tipe pesan AIS.
- **`compression="deflate"`** diwajibkan server agar seluruh pesan terkirim; tanpa itu sebagian pesan dibuang.
- **Batas waktu dua lapis**: `open_timeout` untuk sambungan awal, `ws.recv(timeout=5)` agar loop tidak menggantung bila
  aliran sepi, dan `time.monotonic()` untuk total durasi. `monotonic` dipakai karena tidak terpengaruh perubahan jam
  sistem.
- **Posisi disimpan per MMSI** dalam `dict`: pesan baru menimpa pesan lama, sehingga di akhir hanya ada posisi terakhir
  setiap kapal. Ini cara paling sederhana membuat "snapshot" dari aliran.
- **Kesalahan dibungkus** menjadi `AisError` agar `app.py` cukup menangkap satu jenis kesalahan dan jatuh ke sampel.

Dalam pengujian (`tests/test_ais.py`), fungsi `kumpulkan` diuji dengan mengarahkan URL ke port yang pasti ditolak
(`ws://127.0.0.1:9`) dan memastikan hasilnya `AisError`, bukan traceback mentah. Parser `urai_pesan` diuji dengan
pesan JSON buatan yang meniru format aisstream, sehingga tes tidak memerlukan internet atau kunci API.

## 3. Membaca pesan AIS: nilai "tidak tersedia" bukan nol (`ais.urai_pesan`)

Standar AIS memakai angka khusus untuk "tidak tersedia", dan angka itu terlihat seperti data sungguhan:

| Kolom | Nilai "tidak tersedia" | Jika tidak dibuang |
|---|---|---|
| SOG | 102,3 knot | kapal berlabuh terlihat seperti kapal tercepat di selat |
| COG | 360° | ikon menghadap utara padahal tidak diketahui |
| Heading | 511 | rotasi SVG 511° = 151° yang menyesatkan |
| Lintang / bujur | 91 / 181 | titik di luar peta |

`urai_pesan` mengubah semuanya menjadi `None`, sehingga pandas menyimpannya sebagai `NaN` dan fungsi berikutnya cukup
memeriksa `pd.isna`. Nama kapal dan tujuan di AIS diisi dengan karakter `@` sampai 20 karakter (`"MAERSK@@@@@@"`), jadi
dibersihkan dengan `.replace("@", "").strip()`.

## 4. MMSI: 9 digit yang menyimpan negara (`src/mmsi.py`)

Setiap radio kapal memiliki **MMSI** 9 digit. Tiga digit pertama, **MID** (Maritime Identification Digits),
dialokasikan ITU per negara: `525` Indonesia, `533` Malaysia, `563`–`566` Singapura, `412`–`414` Tiongkok,
`351`–`357` dan `370`–`374` Panama. Awalan khusus menandai bukan-kapal: `00` stasiun pantai, `99` pelampung navigasi
(AtoN), `970` pemancar darurat AIS-SART.

```python
def negara_bendera(mmsi):
    s = str(mmsi)
    if len(s) != 9 or jenis_mmsi(s) != "Kapal":
        return "Tidak diketahui"
    return MID_NEGARA.get(int(s[:3]), "Tidak diketahui")
```

Dua hal yang sering disalahpahami:

- **Bendera bukan kepemilikan.** Panama, Liberia, dan Kepulauan Marshall adalah *bendera kemudahan*: pemilik kapal
  mendaftar di sana karena pajak dan aturan yang longgar. Itulah sebabnya tiga negara kecil ini hampir selalu memuncaki
  grafik "Who rules the strait". Data pemilik sebenarnya tidak ada di AIS.
- **Stasiun pantai dan pelampung ikut masuk aliran** karena mereka juga memancarkan AIS. `analisis.hanya_kapal`
  membuangnya agar KPI "kapal terdeteksi" benar-benar kapal.

## 5. Kode tipe kapal dan status navigasi (`mmsi.kategori_tipe`, `mmsi.status_navigasi`)

Pesan statis membawa **kode tipe 0–99** (ITU-R M.1371). Puluhan menunjukkan kelompok, satuan menunjukkan muatan
berbahaya: `70` kargo, `71` kargo dengan muatan berbahaya kategori A, `80`–`89` tanker, `60`–`69` penumpang, `30`
kapal ikan, `35` operasi militer, `55` penegak hukum, `52` kapal tunda. `kategori_tipe` memetakan rentang ke delapan
kategori yang cukup pendek untuk legenda, dan `nama_tipe` memberi nama rinci untuk popup.

**Status navigasi** (0–15) dilaporkan sendiri oleh awak kapal: `0` berlayar dengan mesin, `1` berlabuh jangkar, `5`
tertambat, `7` menangkap ikan. Karena ini diisi manual, kapal yang sudah berlabuh sering masih berstatus "berlayar".
Karena itu `analisis.fase_pelayaran` menggabungkan status dengan **SOG**: status 1/5/7 dipercaya, selebihnya ditentukan
dari kecepatan (< 0,5 knot diam, < 5 knot lambat, sisanya berlayar).

## 6. Memperkaya tabel (`analisis.perkaya`)

Setelah posisi dan data statis digabung menjadi satu baris per kapal (`ais.ke_dataframe`), `perkaya` menambah kolom
turunan. Pola yang dipakai sama untuk semua kolom: satu fungsi murni per baris, lalu `Series.map` atau list
comprehension.

Kolom `arah` (untuk rotasi ikon) memilih antara dua sumber:

```python
bergerak = sog >= 0.5
d["arah"] = np.where(bergerak & cog.notna(), cog, hdg.where(hdg.notna(), cog))
```

COG (arah gerak) akurat saat kapal bergerak, tetapi kapal yang berlabuh "bergerak" ke segala arah mengikuti arus,
sehingga COG-nya acak; untuk kapal diam, heading (arah haluan) lebih masuk akal. Kapal tanpa keduanya digambar sebagai
lingkaran.

**Pelabuhan terdekat** memakai rumus haversine dalam bentuk vektor: untuk setiap pelabuhan, jarak ke semua kapal dihitung
sekaligus dengan numpy, hasilnya ditumpuk menjadi matriks (kapal × pelabuhan), lalu `argmin(axis=1)` memilih pelabuhan
terdekat per kapal. Untuk 2.000 kapal dan 24 pelabuhan hanya 48.000 operasi, selesai dalam milidetik.

## 7. Menghitung kapal unik, bukan baris (`analisis.hitung_unik`)

Dalam rekaman multi-snapshot, satu kapal muncul berkali-kali. Jika yang dihitung baris, kapal yang berlabuh sepanjang
rekaman akan "mengalahkan" kapal yang lewat sekali. Semua grafik memakai `groupby(kolom)["mmsi"].nunique()`.

Hal kecil yang sering lupa: `groupby(..., dropna=False)` agar kapal tanpa tipe tetap dihitung sebagai "Tidak
diketahui", bukan hilang diam-diam. Persentase dihitung terhadap total kapal unik, bukan total baris.

## 8. Grid kepadatan dan heatmap (`analisis.grid_kepadatan`, `peta.peta_heatmap`)

Heatmap Folium (`folium.plugins.HeatMap`) hanya membutuhkan daftar `[lat, lon]`. Yang membuat jalur pelayaran terlihat
adalah **akumulasi**: sampel merekam posisi tiap kapal setiap 60 detik, sehingga kapal 20 knot meninggalkan satu titik
tiap 600 meter. Ratusan kapal menggambar **traffic separation scheme** (jalur ke tenggara di sisi Sumatera, jalur ke
barat laut di sisi Malaysia) dengan sendirinya.

Grid kepadatan bekerja lebih kasar tetapi bisa diurutkan dan diberi label:

```python
g["lat_sel"] = np.floor(g["lat"] / ukuran_deg)
g["lon_sel"] = np.floor(g["lon"] / ukuran_deg)
agg = g.groupby(["lat_sel", "lon_sel"]).agg(titik=("mmsi", "size"), kapal=("mmsi", "nunique"))
```

Perhatikan dua ukuran: `titik` (semua posisi) menyorot area labuh jangkar karena kapal yang diam menumpuk; `kapal`
(unik) menyorot jalur karena banyak kapal berbeda lewat. Di dekat khatulistiwa 0,25° ≈ 28 km.

## 9. Ikon kapal yang berputar (`peta.ikon_kapal`)

Folium tidak punya marker kapal, jadi dibuat **DivIcon**: potongan HTML berisi SVG yang diputar dengan CSS.

```python
svg = (f'<svg width="16" height="16" viewBox="0 0 24 24" style="transform: rotate({arah:.0f}deg)">'
       f'<path d="M12 1.5 L17.5 9 L17.5 20.5 Q12 23 6.5 20.5 L6.5 9 Z" fill="{warna}" stroke="{garis}"/></svg>')
folium.DivIcon(html=svg, icon_size=(16, 16), icon_anchor=(8, 8))
```

`path` menggambar lambung sederhana dengan haluan runcing menghadap ke atas (utara), sehingga nilai COG dalam derajat
searah jarum jam dari utara bisa langsung dipakai tanpa konversi. `icon_anchor` di tengah penting agar ikon berputar
pada porosnya. Garis tepi (`stroke`) dipakai untuk menandai bendera Indonesia tanpa menambah warna baru ke legenda.

Dengan ribuan kapal, setiap marker adalah elemen DOM; peta tetap lancar sampai sekitar 3.000 ikon. Untuk lebih dari itu,
latihan di `docs/LATIHAN.md` menyarankan `FastMarkerCluster` atau memfilter kapal berlabuh.

## 10. Menyusun aplikasi Streamlit (`app.py`)

Streamlit menjalankan ulang seluruh skrip setiap kali ada interaksi. Dua konsekuensi untuk aplikasi yang "mendengarkan"
20 detik:

- **Jangan mendengarkan ulang saat filter berubah.** Snapshot live disimpan di `st.session_state["snapshot_live"]`; aliran
  hanya dibuka saat pertama kali atau saat tombol Refresh ditekan. `st.cache_data` sengaja tidak dipakai di sini karena
  hasil pendengaran bergantung pada data statis yang terkumpul di sesi (sebuah `dict` yang berubah), bukan pada argumen
  fungsi.
- **Data statis dikumpulkan lintas snapshot** di `st.session_state["cache_statis"]`, sehingga setiap Refresh membuat
  tipe dan tujuan kapal makin lengkap.

Navigasi memakai `st.segmented_control`, bukan `st.tabs`: tab yang tersembunyi berukuran 0 piksel membuat Leaflet
(terutama HeatMap) gagal menggambar peta kedua. Dengan segmented control hanya satu halaman yang dirender.

Kunci API dibaca berurutan dari `st.secrets["aisstream"]["api_key"]` (Streamlit Cloud), variabel lingkungan
`AISSTREAM_API_KEY`, atau kotak teks di sidebar. Tanpa kunci, aplikasi memakai sampel offline dan menjelaskannya lewat
pesan oranye, bukan error.

## 11. Merekam sampel offline (`scripts/rekam_sampel.py`)

Agar aplikasi bisa dicoba tanpa kunci (dan agar heatmap punya jejak), skrip ini mendengarkan aliran selama N menit dan
menyimpan **satu posisi per kapal per bucket 60 detik**:

```python
bucket = int((time.time() - mulai) // interval)
posisi[(mmsi, bucket)] = baris
```

Kunci `(mmsi, bucket)` membuat pesan dalam satu menit saling menimpa, sehingga 10 menit aliran Selat Malaka (ratusan ribu
pesan) menyusut menjadi puluhan ribu baris yang muat di repositori. Data statis disimpan terpisah karena berlaku untuk
seluruh rekaman, bukan per snapshot.

## 12. Membaca hasilnya dengan jujur

Beberapa hal yang perlu diingat saat menafsirkan peta:

- **Yang terlihat adalah yang tertangkap penerima**, bukan seluruh lalu lintas. Pantai Malaysia dan Singapura punya
  penerima rapat; pantai Sumatera jarang. Kekosongan di sisi Indonesia sebagian adalah kekosongan penerima.
- **Kapal perang jarang memancarkan AIS**, dan halaman Chokepoints & bases hanya menunjukkan kapal yang memilih tampil.
  "Tidak terlihat" tidak berarti "tidak ada".
- **Angka berubah dari jam ke jam**: komposisi bendera siang hari berbeda dari malam, dan satu snapshot 20 detik bukan
  statistik lalu lintas tahunan.

## Bacaan lanjutan

- aisstream.io, dokumentasi API: https://aisstream.io/documentation
- ITU-R M.1371 (format pesan AIS) dan ITU-R M.585 (MID): https://www.itu.int/rec/R-REC-M.1371 dan https://www.itu.int/rec/R-REC-M.585
- Dokumentasi `websockets` (klien sinkron): https://websockets.readthedocs.io
- Folium DivIcon dan HeatMap: https://python-visualization.github.io/folium/
- Streamlit session state: https://docs.streamlit.io/develop/concepts/architecture/session-state
