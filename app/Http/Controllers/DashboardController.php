<?php

namespace App\Http\Controllers;

use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Process;
use Illuminate\Support\Facades\View;

class DashboardController extends PersediaanBaseController
{
    public function dashboard()
    {
        $mulai = config('etl.analysis_period.start', '2025-07-01');
        $akhir = config('etl.analysis_period.end', '2026-07-31');
        $idTahunan = DB::table('periode_analisis')
            ->whereDate('tanggal_mulai', $mulai)
            ->whereDate('tanggal_akhir', $akhir)
            ->orderByDesc('id_periode')
            ->value('id_periode');

        if (!$this->baselineTahunanLengkap($idTahunan)) {
            $gagal = $this->tarikDanAnalisisTahunan();
            if ($gagal === null) {
                return redirect()->route('dashboard')->with(
                    'ok', "Data ditarik dari SQL Server dan analisis tahunan {$mulai} s/d {$akhir} selesai."
                );
            }
            $notice = "Analisis tahunan belum berhasil. Pengambilan dari SQL Server gagal: {$gagal}";
        } else {
            $notice = null;
        }

        // Constructor parent sudah berjalan sebelum dashboard menyiapkan baseline.
        // Paksa view ini tetap memakai periode tahunan yang dikonfigurasi.
        $this->id = $idTahunan;
        $this->p = DB::table('periode_analisis')->where('id_periode', $this->id)->first();
        View::share('periode', $this->p);

        $hitung = fn ($tabel, $kol) => DB::table($tabel)->where('id_periode', $this->id)
            ->selectRaw("$kol k, COUNT(*) n")->groupBy($kol)->pluck('n', 'k');

        $matriks = DB::table('matriks_abc_fsn as m')->join('klasifikasi_abc as a', 'a.id_abc', '=', 'm.id_abc')
            ->where('a.id_periode', $this->id)->selectRaw('m.kategori_matriks k, COUNT(*) n')
            ->groupBy('m.kategori_matriks')->pluck('n', 'k');

        $perlu = DB::table('rekomendasi_rop as r')->join('barang as b', function ($join) {
            $join->whereRaw('b.kode_produk COLLATE utf8mb4_unicode_ci = r.kode_produk COLLATE utf8mb4_unicode_ci');
        })
            ->where('r.id_periode', $this->id)->where('r.status_reorder', 'Reorder')
            ->orderBy('r.kategori_matriks')->orderByDesc('r.reorder_point')
            ->select('r.kode_produk', 'b.nama_produk', 'r.kategori_matriks', 'r.stok_satuan', 'r.reorder_point')
            ->limit(10)->get();

        $top = DB::table('klasifikasi_abc as a')->join('klasifikasi_fsn as f', function ($j) {
                $j->whereRaw('f.kode_produk COLLATE utf8mb4_unicode_ci = a.kode_produk COLLATE utf8mb4_unicode_ci')
                    ->on('f.id_periode', '=', 'a.id_periode');
            })->join('barang as b', function ($join) {
                $join->whereRaw('b.kode_produk COLLATE utf8mb4_unicode_ci = a.kode_produk COLLATE utf8mb4_unicode_ci');
            })
            ->where('a.id_periode', $this->id)->where('a.kelas_abc', 'A')->where('f.kelas_fsn', 'F')
            ->orderByDesc('a.total_penjualan_produk')->limit(10)
            ->select('b.nama_produk', 'a.total_penjualan_produk')->get();

        return view('dashboard', ['top' => $top, 'analisisNotice' => $notice] + [
            'abc' => $hitung('klasifikasi_abc', 'kelas_abc'), 'fsn' => $hitung('klasifikasi_fsn', 'kelas_fsn'),
            'rop' => $hitung('rekomendasi_rop', 'status_reorder'), 'matriks' => $matriks, 'perlu' => $perlu,
        ]);
    }

    private function baselineTahunanLengkap($idPeriode): bool
    {
        if (!$idPeriode) return false;

        return DB::table('klasifikasi_abc')->where('id_periode', $idPeriode)->exists()
            && DB::table('klasifikasi_fsn')->where('id_periode', $idPeriode)->exists()
            && DB::table('matriks_abc_fsn as m')
                ->join('klasifikasi_abc as a', 'a.id_abc', '=', 'm.id_abc')
                ->where('a.id_periode', $idPeriode)->exists()
            && DB::table('rekomendasi_rop')->where('id_periode', $idPeriode)->exists();
    }

    /** Pull source data from SQL Server and build annual reports on first dashboard load. */
    private function tarikDanAnalisisTahunan(): ?string
    {
        $etlPath = config('etl.path', base_path('etl'));
        if (!is_dir($etlPath)) return "folder ETL tidak ditemukan: {$etlPath}";

        $python = array_merge(
            [config('etl.python_bin', 'python')],
            config('etl.python_args', [])
        );
        $environment = [
            'PATH' => (string) (getenv('PATH') ?: ($_SERVER['PATH'] ?? 'C:\\Windows\\System32;C:\\Windows')),
            'SYSTEMROOT' => (string) (getenv('SYSTEMROOT') ?: getenv('SystemRoot') ?: 'C:\\Windows'),
            'WINDIR' => (string) (getenv('WINDIR') ?: getenv('windir') ?: 'C:\\Windows'),
            'TEMP' => (string) (getenv('TEMP') ?: getenv('TMP') ?: sys_get_temp_dir()),
            'TMP' => (string) (getenv('TMP') ?: getenv('TEMP') ?: sys_get_temp_dir()),
            'USERPROFILE' => (string) (getenv('USERPROFILE') ?: ''),
            'LOCALAPPDATA' => (string) (getenv('LOCALAPPDATA') ?: ''),
            'APPDATA' => (string) (getenv('APPDATA') ?: ''),
            'PYTHONNOUSERSITE' => '0',
            'PYTHONPATH' => config('etl.python_path', ''),
            'PYTHONHASHSEED' => config('etl.python_hash_seed', '0'),
            'ETL_DB_DRIVER' => 'mysql+pymysql',
            'ETL_DB_HOST' => config('database.connections.mysql.host', '127.0.0.1'),
            'ETL_DB_PORT' => (string) config('database.connections.mysql.port', 3306),
            'ETL_DB_DATABASE' => config('database.connections.mysql.database', 'webskripsi'),
            'ETL_DB_USERNAME' => config('database.connections.mysql.username', 'root'),
            'ETL_DB_PASSWORD' => config('database.connections.mysql.password', ''),
            'ANALYSIS_START_DATE' => config('etl.analysis_period.start', '2025-07-01'),
            'ANALYSIS_END_DATE' => config('etl.analysis_period.end', '2026-07-31'),
            'SQLSERVER_DRIVER' => config('etl.sqlserver.driver', 'SQL Server'),
            'SQLSERVER_SERVER' => config('etl.sqlserver.server', 'SERVERBARU1'),
            'SQLSERVER_DATABASE' => config('etl.sqlserver.database', 'dbGrosir'),
            'SQLSERVER_TRUSTED_CONNECTION' => config('etl.sqlserver.trusted_connection', 'yes'),
            'SQLSERVER_USERNAME' => config('etl.sqlserver.username', ''),
            'SQLSERVER_PASSWORD' => config('etl.sqlserver.password', ''),
        ];

        $scripts = [
            'data/barang.py',
            'data/supplier.py',
            'data/barang_dtl.py',
            'data/penjualan.py',
            'data/stok.py',
            'data/produk_supplier.py',
            'analisis/klasifikasi_abc.py',
            'analisis/klasifikasi_fsn.py',
            'analisis/matriks_abc_fsn.py',
            'analisis/analisisrop.py',
        ];
        foreach ($scripts as $script) {
            if (!is_file($etlPath . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $script))) {
                return "skrip tidak ditemukan: {$script}";
            }
        }

        set_time_limit(0);
        $cek = Process::timeout(30)->path($etlPath)->env($environment)
            ->run(array_merge($python, ['-c', 'import pandas, numpy, sqlalchemy, pymysql, pyodbc']));
        if (!$cek->successful()) {
            return trim($cek->errorOutput() ?: $cek->output()) ?: 'Python atau dependensi ETL termasuk pyodbc tidak tersedia.';
        }

        foreach ($scripts as $script) {
            $result = Process::timeout(1800)->path($etlPath)->env($environment)
                ->run(array_merge($python, [$script]));
            if (!$result->successful()) {
                return trim($result->errorOutput() ?: $result->output()) ?: "{$script} gagal.";
            }
        }

        return null;
    }
}
