<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;

class RefreshRopSnapshot extends Command
{
    protected $signature = 'rop:refresh-snapshot';
    protected $description = 'Tarik pergerakan stok terbaru dan perbarui status reorder terhadap ROP tahunan.';

    public function handle(): int
    {
        $idPeriode = DB::table('periode_analisis')
            ->whereDate('tanggal_mulai', config('etl.analysis_period.start', '2025-07-01'))
            ->whereDate('tanggal_akhir', config('etl.analysis_period.end', '2026-07-31'))
            ->orderByDesc('id_periode')
            ->value('id_periode');
        if (!$idPeriode
            || !DB::table('klasifikasi_fsn')->where('id_periode', $idPeriode)->exists()
            || !DB::table('matriks_abc_fsn as m')
                ->join('klasifikasi_abc as a', 'a.id_abc', '=', 'm.id_abc')
                ->where('a.id_periode', $idPeriode)->exists()) {
            $this->error('Belum ada klasifikasi ABC, FSN, dan matriks periode aktif.');
            return self::FAILURE;
        }

        $baselineAda = DB::table('rekomendasi_rop as r')
            ->join('periode_analisis as p', 'p.id_periode', '=', 'r.id_periode')
            ->where('r.id_periode', $idPeriode)
            ->whereRaw('DATE(r.tanggal_mulai_data) = DATE(p.tanggal_mulai)')
            ->whereRaw('DATE(r.tanggal_akhir_data) = DATE(p.tanggal_akhir)')
            ->exists();
        if (!$baselineAda) {
            $this->error('Baseline ROP tahunan belum ada atau tidak sesuai periode ABC aktif. Jalankan Analisis Ulang ROP Saja terlebih dahulu.');
            return self::FAILURE;
        }

        $pythonCommand = array_merge(
            [config('etl.python_bin', 'python')],
            config('etl.python_args', [])
        );
        $etlPath = config('etl.path', base_path('etl'));
        if (!is_dir($etlPath)) {
            $this->error("Folder ETL tidak ditemukan: {$etlPath}");
            return self::FAILURE;
        }

        $environment = [
            'PATH' => (string) (getenv('PATH') ?: ($_SERVER['PATH'] ?? 'C:\\Windows\\System32;C:\\Windows')),
            'SYSTEMROOT' => (string) (getenv('SYSTEMROOT') ?: getenv('SystemRoot') ?: 'C:\\Windows'),
            'WINDIR' => (string) (getenv('WINDIR') ?: getenv('windir') ?: 'C:\\Windows'),
            'TEMP' => (string) (getenv('TEMP') ?: getenv('TMP') ?: sys_get_temp_dir()),
            'TMP' => (string) (getenv('TMP') ?: getenv('TEMP') ?: sys_get_temp_dir()),
            'USERPROFILE' => (string) (getenv('USERPROFILE') ?: getenv('USER') ?: ''),
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

        // Perbarui data pergerakan stok tanggal hari ini. Analisis memakai seluruh
        // riwayat stok yang sudah tersimpan dan hanya menulis stok/status snapshot.
        $tanggal = now()->toDateString();
        $commands = [
            array_merge($pythonCommand, ['data/stok.py', $tanggal, $tanggal]),
            array_merge($pythonCommand, [
                'analisis/analisisrop.py', '--tanggal-mulai', $tanggal, '--tanggal-akhir', $tanggal,
            ]),
        ];

        foreach ($commands as $arguments) {
            $result = Process::timeout(1800)->path($etlPath)->env($environment)->run($arguments);
            if (!$result->successful()) {
                $detail = trim($result->errorOutput() ?: $result->output());
                $detail = $detail !== '' ? substr($detail, -2500) : 'Subproses ETL gagal tanpa detail.';
                Log::error('Refresh snapshot ROP otomatis gagal.', ['command' => $arguments, 'detail' => $detail]);
                $this->error($detail);
                return self::FAILURE;
            }
        }

        Log::info('Snapshot stok dan status ROP diperbarui otomatis.', ['tanggal' => $tanggal]);
        $this->info("Snapshot stok/status diperbarui untuk {$tanggal}; ROP tahunan dan klasifikasi tetap.");
        return self::SUCCESS;
    }
}
