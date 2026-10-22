# Sistem Pengendalian Persediaan — CV Jaya Abadi Jaya

Aplikasi Laravel 11 untuk laporan persediaan, klasifikasi ABC, analisis FSN, matriks ABC-FSN, dan rekomendasi reorder point (ROP). Skrip ETL berada di `etl/` dan mengambil data sumber dari SQL Server POS.

## Persyaratan

- PHP 8.2 atau lebih baru, Composer, dan ekstensi `pdo_mysql`, `mbstring`, `openssl`.
- MySQL Laragon dengan database `webskripsi`. Jika memakai dump `tugas_akhir.sql`, impor isinya ke database `webskripsi`.
- Python 3.11 x64, driver ODBC SQL Server yang cocok bitness-nya, serta dependensi di `etl/requirements.txt`.
- SQL Server POS yang berisi database `dbGrosir` (atau konfigurasi sesuai server Anda).

## Menyiapkan aplikasi

1. Buat database MySQL `webskripsi`, lalu impor isi dump SQL yang disediakan. Dump tersebut memuat data penjualan sampai 31 Juli 2026.
2. Salin `.env.example` menjadi `.env` jika belum ada. Pertahankan `.env` lokal yang sudah berisi APP_KEY; jangan membagikannya.
3. Pastikan `DB_DATABASE=webskripsi`. Sesuaikan kredensial MySQL dan nilai SQL Server pada `.env`.
4. Jalankan `composer install`, lalu `php artisan key:generate` hanya jika APP_KEY masih kosong.
5. Aktifkan ekstensi PHP `pdo_mysql`, kemudian jalankan `php artisan migrate` setelah memastikan backup database tersedia. Migration menyiapkan tabel aplikasi yang belum ada.
6. Pastikan Python 3.11 dan `pyodbc` tersedia: `py -3.11 -m pip install -r etl/requirements.txt`.
7. Konfigurasi default memakai `PYTHON_BIN=py` dan `PYTHON_ARGS=-3.11`. Jika PHP tidak dapat menemukan `py`, isi `PYTHON_BIN` dengan path penuh `python.exe` dan kosongkan `PYTHON_ARGS`.
8. Jalankan `php artisan config:clear`, lalu `php artisan serve` dan buka `http://127.0.0.1:8000`.

ETL membaca koneksi MySQL langsung dari `.env` Laravel saat dijalankan manual, atau menerima konfigurasi yang diteruskan Laravel. Database tujuan ETL sama dengan `DB_DATABASE` (`webskripsi`). Untuk SQL Server, gunakan Windows Trusted Connection (`SQLSERVER_TRUSTED_CONNECTION=yes`) atau isi username/password dan set nilainya ke `no`.

## Simulasi ROP Agustus

Masuk sebagai admin stok, lalu gunakan **Tarik & Simulasikan ROP**. Rentang awalnya 1–19 Agustus 2026 dan bisa diubah. Sistem menarik penjualan dan pergerakan stok dari SQL Server untuk rentang itu. ROP simulasi memakai baseline tahunan yang tersimpan: hanya stok terbaru dan status reorder yang diperbarui. Rata-rata tahunan, Safety Stock, nilai ROP, klasifikasi ABC, FSN, dan matriks tetap.

Proses simulasi memeriksa dulu apakah hasil ABC, FSN, matriks, dan baseline ROP tahunan periode aktif sudah tersedia. Skrip ABC, FSN, dan matriks tidak dijalankan atau ditulis saat simulasi. Rentang stok yang dipakai ditampilkan di kolom **Data ROP Mulai** dan **Data ROP Sampai**. Gunakan **Kembalikan ROP ke Periode ABC Aktif** untuk menghitung ulang baseline ROP tahunan dari periode klasifikasi yang tersimpan.

**Analisis Ulang ABC, FSN, Matriks & ROP** menjalankan seluruh analisis. **Tarik Data + Analisis** menjalankan impor penuh dan seluruh analisis. Hindari kedua proses tersebut saat ingin mempertahankan hasil klasifikasi yang ada.

## Struktur penting

- `app/Models/` — model Eloquent untuk data persediaan dan akun.
- `app/Http/Controllers/` — halaman laporan, login, supplier, dan orkestrasi ETL.
- `database/migrations/` — satu migration untuk setiap tabel (`users`, `log_etl`, barang, transaksi, klasifikasi, supplier, dan ROP), dengan urutan mengikuti foreign key.
- `resources/views/` — tampilan Laravel.
- `etl/data/` — pengambilan data SQL Server ke MySQL.
- `etl/analisis/` — perhitungan klasifikasi dan ROP.

CSV di `etl/` adalah keluaran/cadangan analisis; data aplikasi utama disimpan di MySQL.

## Pembaruan status ROP otomatis setiap 15/20 menit

Fitur otomatis mengambil ulang pergerakan stok hari ini dari SQL Server, menghitung saldo stok dari riwayat yang sudah diimpor, lalu memperbarui hanya stok dan status Reorder/Aman terhadap ROP tahunan tersimpan. Nilai rata-rata tahunan, Safety Stock, ROP, ABC, FSN, dan matriks tidak dihitung ulang. Halaman ROP menampilkan waktu snapshot terakhir.

1. Jalankan migration baru: `php artisan migrate` (menambahkan kolom `waktu_snapshot`).
2. Di `.env`, atur `ROP_AUTO_REFRESH_ENABLED=true` dan `ROP_AUTO_REFRESH_INTERVAL_MINUTES=15` atau `20`.
3. Jalankan `php artisan config:clear`.
4. Pastikan baseline tahunan dan koneksi SQL Server sudah berfungsi, lalu jalankan scheduler Laravel. Untuk pengujian saat development, biarkan terminal server menjalankan `php artisan schedule:work`. Di komputer Windows yang dipakai terus-menerus, buat tugas Windows Task Scheduler yang menjalankan `php artisan schedule:run` setiap satu menit.

Jam **Terakhir Diperbarui** menunjukkan saat data diperiksa dan disimpan oleh aplikasi. Kolom transaksi sumber saat ini disimpan sebagai tanggal, jadi fitur ini menjalankan pemeriksaan berkala atas data yang sudah tersedia di SQL Server; ia tidak menciptakan riwayat jam transaksi yang tidak disediakan oleh sumber.
