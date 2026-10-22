# Catatan revisi Laravel dan simulasi ROP

Dokumen ini menjelaskan file yang direvisi dan cara menjalankan simulasi data Agustus 2026. Paket source tidak menyertakan `.env`, folder `vendor`, session, cache, log runtime, CSV hasil ETL, maupun dump SQL. Gunakan `.env.example` sebagai template konfigurasi. Buat database MySQL `webskripsi`, lalu jika menggunakan dump `tugas_akhir.sql`, impor isinya ke database tersebut. CSV keluaran dibuat ulang oleh ETL saat proses dijalankan.

## Migration PHP

Setiap tabel aplikasi mempunyai file migration sendiri di `database/migrations/`:

1. `2026_10_06_000000_create_users_table.php` — akun aplikasi.
2. `2026_10_12_000000_create_log_etl_table.php` — riwayat proses ETL.
3. `2026_10_12_000001_create_barang_table.php` — master produk.
4. `2026_10_12_000002_create_supplier_table.php` — master supplier.
5. `2026_10_12_000003_create_barang_detail_table.php` — satuan/kemasan produk.
6. `2026_10_12_000004_create_detail_penjualan_table.php` — detail transaksi penjualan.
7. `2026_10_12_000005_create_stok_table.php` — pergerakan stok.
8. `2026_10_12_000006_create_periode_analisis_table.php` — periode klasifikasi.
9. `2026_10_12_000007_create_klasifikasi_abc_table.php` — hasil ABC.
10. `2026_10_12_000008_create_klasifikasi_fsn_table.php` — hasil FSN.
11. `2026_10_12_000009_create_matriks_abc_fsn_table.php` — gabungan klasifikasi.
12. `2026_10_12_000010_create_produk_supplier_table.php` — relasi produk dan supplier.
13. `2026_10_12_000011_create_rekomendasi_rop_table.php` — rekomendasi reorder point, termasuk rentang data simulasi.

Migration memakai pemeriksaan keberadaan tabel supaya tabel dari dump SQL yang sudah diimpor tidak dibuat ulang. Migration ROP menambahkan kolom `tanggal_mulai_data` dan `tanggal_akhir_data` jika tabel lama belum memilikinya. Jalankan migration setelah ekstensi PHP `pdo_mysql` tersedia:

```powershell
php artisan migrate
```

## Model Eloquent

`app/Models/` berisi model untuk seluruh entitas aplikasi: `User`, `LogEtl`, `Barang`, `BarangDetail`, `DetailPenjualan`, `Stok`, `Supplier`, `ProdukSupplier`, `PeriodeAnalisis`, `KlasifikasiAbc`, `KlasifikasiFsn`, `MatriksAbcFsn`, dan `RekomendasiRop`. Primary key, tabel non-konvensional, relasi foreign key, dan cast tanggal ditetapkan secara eksplisit agar sesuai dengan skema database.

## Cara kerja simulasi Agustus

1. Dump SQL berisi data sampai 31 Juli 2026. Data 1–19 Agustus harus tersedia di SQL Server `dbGrosir`; simulasi tidak membuat atau mengarang transaksi Agustus.
2. Dari aplikasi, login sebagai admin stok. Di form **Simulasi ROP per rentang tanggal**, pilih 1 Agustus sampai 19 Agustus 2026 lalu klik **Tarik & Simulasikan ROP**.
3. Laravel memastikan hasil ABC, FSN, dan matriks untuk periode aktif tersedia.
4. `etl/data/penjualan.py` menarik penjualan dari SQL Server dalam rentang tanggal inklusif dan mengganti hanya baris MySQL pada rentang yang sama. Data tanggal lain tetap dipertahankan.
5. `etl/data/stok.py` menarik pergerakan stok pada rentang simulasi dan mengganti slice tanggal tersebut bila sumber mengembalikan data valid. Jika tidak ada stok valid, slice stok lama dipertahankan.
6. `etl/analisis/analisisrop.py` memakai snapshot stok simulasi untuk menghitung status. Rata-rata tahunan, Safety Stock, dan ROP dari baseline aktif dipertahankan tanpa dihitung ulang.
7. Script simulasi memakai kategori ABC/FSN dan matriks yang sudah tersimpan. Mode simulasi tidak menjalankan script klasifikasi ABC, FSN, atau matriks, dan tidak mengubah tabel klasifikasi tersebut.
8. Hasil simulasi hanya memperbarui stok saat ini, stok dalam satuan, status reorder, dan metadata rentang simulasi. Klik **Kembalikan ROP ke Periode ABC Aktif** hanya jika memang ingin membentuk ulang baseline ROP dari periode tahunan.

## Konfigurasi dan menjalankan

- Salin `.env.example` ke `.env`, lalu isi koneksi MySQL dan SQL Server.
- Pastikan `SQLSERVER_SERVER`, `SQLSERVER_DATABASE`, driver ODBC, dan metode autentikasi sesuai mesin sumber.
- Pastikan Python serta paket pada `etl/requirements.txt` terpasang.
- `ETL_PATH`, `PYTHON_BIN`, dan `PYTHON_ARGS` dapat diarahkan ke lokasi ETL dan Python yang digunakan. Python Install Manager dapat memakai `PYTHON_BIN=py` dan `PYTHON_ARGS=-3.11`; Python tradisional dapat memakai path penuh ke `python.exe` dengan `PYTHON_ARGS` kosong. Nilai ini dibaca dari `config/etl.php`, sehingga tetap benar saat Laravel menggunakan config cache.
- Sebelum memulai proses, Laravel memeriksa bahwa `pandas`, `numpy`, `SQLAlchemy`, `PyMySQL`, dan `pyodbc` tersedia pada interpreter yang dipilih. Jika belum, alert akan menyebut interpreter yang harus dipakai untuk memasang `etl/requirements.txt`.
- Controller mengirim `PYTHONHASHSEED=0` ke proses ETL. Ini menghindari kegagalan startup Python yang terjadi pada sebagian konfigurasi Windows ketika proses anak meminta random bytes untuk hash initialization.
- Setelah dependency Composer tersedia, jalankan `php artisan serve`.

Pemeriksaan yang dilakukan untuk paket revisi: lint sintaks pada file PHP, pemeriksaan parse Python, dan daftar route Laravel. Simulasi belum dieksekusi pada SQL Server pengguna karena memerlukan koneksi database sumber yang aktif.
