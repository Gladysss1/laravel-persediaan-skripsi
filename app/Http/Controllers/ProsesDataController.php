<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Process;

class ProsesDataController extends PersediaanBaseController
{
    // Urutan skrip Python; folder = ETL_PATH
    private const TARIK = ['data/barang.py', 'data/supplier.py', 'data/barang_dtl.py', 'data/penjualan.py',
        'data/stok.py', 'data/produk_supplier.py'];
    private const ANALISIS = ['analisis/klasifikasi_abc.py', 'analisis/klasifikasi_fsn.py',
        'analisis/matriks_abc_fsn.py', 'analisis/analisisrop.py'];

    // Riwayat proses data (log_etl)
    public function log()
    {
        $q = DB::table('log_etl as l')->leftJoin('users as u', 'u.id_user', '=', 'l.id_user')->orderByDesc('l.id_log')
            ->select('l.waktu_mulai', 'l.waktu_selesai', 'u.nama', 'l.status', 'l.jumlah_data');

        return $this->tampil('Riwayat Proses Data', $q, [
            'waktu_mulai' => 'Mulai', 'waktu_selesai' => 'Selesai', 'nama' => 'Dijalankan Oleh',
            'status' => 'Status', 'jumlah_data' => 'Jumlah Data',
        ], ['jumlah_data'], ['tanpaCari' => true]);
    }

    // Jalankan skrip Python lewat subprocess
    public function jalankan(Request $r)
    {
        set_time_limit(0);
        $r->validate([
            'mode' => ['required', 'in:analisis,penuh,simulasi_rop,rop_aktif'],
            'tanggal_mulai' => ['required_if:mode,simulasi_rop', 'nullable', 'date'],
            'tanggal_akhir' => ['required_if:mode,simulasi_rop', 'nullable', 'date', 'after_or_equal:tanggal_mulai'],
        ]);
        $simulasi = $r->mode === 'simulasi_rop';
        $ropAktif = $r->mode === 'rop_aktif';
        if ($simulasi) {
            // Simulasi hanya sah jika klasifikasi yang akan dipakai sudah tersedia.
            // Pemeriksaan ini mencegah data Agustus terlanjur diimpor tanpa hasil ROP.
            $idPeriodeAktif = DB::table('periode_analisis')
                ->whereDate('tanggal_mulai', config('etl.analysis_period.start', '2025-07-01'))
                ->whereDate('tanggal_akhir', config('etl.analysis_period.end', '2026-07-31'))
                ->orderByDesc('id_periode')
                ->value('id_periode');
            if (!$idPeriodeAktif
                || !DB::table('klasifikasi_fsn')->where('id_periode', $idPeriodeAktif)->exists()
                || !DB::table('matriks_abc_fsn as m')
                    ->join('klasifikasi_abc as a', 'a.id_abc', '=', 'm.id_abc')
                    ->where('a.id_periode', $idPeriodeAktif)->exists()) {
                return back()->with('gagal', 'Simulasi ROP memerlukan hasil ABC, FSN, dan matriks periode aktif. Jalankan analisis periode dasar terlebih dahulu.');
            }

            $skrip = [
                // Simulasi status cukup memperbarui pergerakan stok pada rentang
                // yang dipilih. Penjualan/angka tahunan tidak disentuh.
                ['data/stok.py', $r->tanggal_mulai, $r->tanggal_akhir],
                ['analisis/analisisrop.py', '--tanggal-mulai', $r->tanggal_mulai, '--tanggal-akhir', $r->tanggal_akhir],
            ];
        } elseif ($ropAktif) {
            // Refresh ROP aktif saja; tidak menarik sumber dan tidak menjalankan ulang ABC/FSN/matriks.
            $skrip = [['analisis/analisisrop.py']];
        } elseif ($r->mode === 'analisis') {
            // Buat/perbarui baseline analisis tahunan dari data MySQL yang sudah ada.
            // Tidak menjalankan skrip ETL penarikan dari SQL Server.
            $skrip = array_map(fn ($path) => [$path], self::ANALISIS);
        } else {
            $skrip = array_map(fn ($path) => [$path], array_merge(self::TARIK, self::ANALISIS));
        }
        $mulai = now();
        $gagal = null;
        $pythonBin = config('etl.python_bin', 'python');
        $pythonArgs = config('etl.python_args', []);
        $pythonCommand = array_merge([$pythonBin], $pythonArgs);
        $etlPath = config('etl.path', base_path('etl'));

        if (!is_dir($etlPath)) {
            return back()->with('gagal', "Folder ETL tidak ditemukan: {$etlPath}. Periksa ETL_PATH di .env dan jalankan php artisan config:clear.");
        }

        $environment = [
            // Preserve the Windows runtime environment for Python launched by PHP's
            // built-in web server. In CGI/cli-server contexts Symfony may filter
            // server variables; Winsock can fail to initialize without these paths.
            'PATH' => (string) (getenv('PATH') ?: ($_SERVER['PATH'] ?? 'C:\\Windows\\System32;C:\\Windows')),
            'SYSTEMROOT' => (string) (getenv('SYSTEMROOT') ?: getenv('SystemRoot') ?: 'C:\\Windows'),
            'WINDIR' => (string) (getenv('WINDIR') ?: getenv('windir') ?: 'C:\\Windows'),
            'TEMP' => (string) (getenv('TEMP') ?: getenv('TMP') ?: sys_get_temp_dir()),
            'TMP' => (string) (getenv('TMP') ?: getenv('TEMP') ?: sys_get_temp_dir()),
            'USERPROFILE' => (string) (getenv('USERPROFILE') ?: getenv('USER') ?: ''),
            'LOCALAPPDATA' => (string) (getenv('LOCALAPPDATA') ?: ''),
            'APPDATA' => (string) (getenv('APPDATA') ?: ''),
            'PYTHONNOUSERSITE' => '0',
            'ETL_DB_DRIVER' => 'mysql+pymysql',
            'ETL_DB_HOST' => config('database.connections.mysql.host', '127.0.0.1'),
            'ETL_DB_PORT' => (string) config('database.connections.mysql.port', 3306),
            'ETL_DB_DATABASE' => config('database.connections.mysql.database', 'webskripsi'),
            'ETL_DB_USERNAME' => config('database.connections.mysql.username', 'root'),
            'ETL_DB_PASSWORD' => config('database.connections.mysql.password', ''),
            'ANALYSIS_START_DATE' => config('etl.analysis_period.start', '2025-07-01'),
            'ANALYSIS_END_DATE' => config('etl.analysis_period.end', '2026-07-31'),
            // Make user-installed Python packages visible to the Laravel subprocess.
            'PYTHONPATH' => config('etl.python_path', ''),
            'SQLSERVER_DRIVER' => config('etl.sqlserver.driver', 'SQL Server'),
            'SQLSERVER_SERVER' => config('etl.sqlserver.server', 'SERVERBARU1'),
            'SQLSERVER_DATABASE' => config('etl.sqlserver.database', 'dbGrosir'),
            'SQLSERVER_TRUSTED_CONNECTION' => config('etl.sqlserver.trusted_connection', 'yes'),
            'SQLSERVER_USERNAME' => config('etl.sqlserver.username', ''),
            'SQLSERVER_PASSWORD' => config('etl.sqlserver.password', ''),
            'PYTHONHASHSEED' => config('etl.python_hash_seed', '0'),
        ];

        // Analisis dari MySQL tidak memerlukan pyodbc. Simulasi dan impor penuh
        // mengambil stok/penjualan dari SQL Server.
        $butuhSqlServer = $r->mode === 'penuh' || $simulasi;
        $modulPython = $butuhSqlServer
            ? 'import pandas, numpy, sqlalchemy, pymysql, pyodbc'
            : 'import pandas, numpy, sqlalchemy, pymysql';

        // Pastikan semua file skrip ada sebelum menjalankan ETL, agar tidak gagal di tengah proses.
        foreach ($skrip as $perintah) {
            $fileSkrip = $etlPath . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $perintah[0]);
            if (!is_file($fileSkrip)) {
                return back()->with('gagal', "Skrip ETL tidak ditemukan: {$fileSkrip}");
            }
        }

        // Fail early with a useful message if packages were installed into a different Python.
        $cekPython = Process::timeout(30)->path($etlPath)
            ->env($environment)
            ->run(array_merge($pythonCommand, ['-c', $modulPython]));
        if (!$cekPython->successful()) {
            $detail = trim($cekPython->errorOutput() ?: $cekPython->output());
            $detail = $detail !== '' ? substr($detail, -1200) : 'Python gagal dijalankan atau tidak dapat mengimpor modul ETL.';
            return back()->with('gagal', "Pemeriksaan Python gagal. Interpreter: '{$pythonBin}'. Pastikan path Python benar dan dependensi tersedia; untuk tarik data, modul pyodbc juga diperlukan. Detail: {$detail}");
        }

        foreach ($skrip as $perintah) {
            $s = array_shift($perintah);
            $argumen = $perintah;
            $h = Process::timeout(1800)->path($etlPath)
                ->env($environment)
                ->run(array_merge($pythonCommand, [$s], $argumen));
            if (!$h->successful()) {
                $detail = trim($h->errorOutput() ?: $h->output());
                $detail = $detail !== '' ? substr($detail, -2000) : 'Proses Python berhenti tanpa memberikan pesan error.';
                $gagal = "$s gagal menggunakan Python '{$pythonBin}' (exit code {$h->exitCode()}): {$detail}";
                break;
            }
        }

        try {
            DB::table('log_etl')->insert([
                'id_user' => session('user.id'), 'waktu_mulai' => $mulai, 'waktu_selesai' => now(),
                'status' => $gagal ? 'Gagal' : 'Berhasil', 'jumlah_data' => DB::table('rekomendasi_rop')->count(),
            ]);
        } catch (\Throwable $e) {
        }

        if ($simulasi) {
            $pesan = "Simulasi stok {$r->tanggal_mulai} s/d {$r->tanggal_akhir} selesai. Stok dan status reorder diperbarui; data penjualan, rata-rata tahunan, Safety Stock, ROP, ABC, FSN, dan matriks tetap.";
        } elseif ($ropAktif) {
            $pesan = 'ROP dihitung ulang memakai periode ABC aktif. ABC, FSN, dan matriks tidak dijalankan.';
        } elseif ($r->mode === 'analisis') {
            $pesan = 'Analisis tahunan ABC, FSN, matriks, dan ROP selesai memakai data yang sudah ada di MySQL. Tidak ada data ditarik dari SQL Server.';
        } else {
            $pesan = 'Proses selesai. Data sudah diperbarui.';
        }
        return back()->with($gagal ? 'gagal' : 'ok', $gagal ?: $pesan);
    }
}
