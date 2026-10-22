<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\View;
use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

// Induk semua controller persediaan: periode aktif, pencarian, tabel + ekspor Excel.
abstract class PersediaanBaseController extends Controller
{
    protected $id;
    protected $p;

    public function __construct()
    {
        // Semua halaman memakai baseline tahunan yang dikonfigurasi, bukan
        // periode simulasi atau periode lain yang kebetulan dibuat belakangan.
        $this->id = DB::table('periode_analisis')
            ->whereDate('tanggal_mulai', config('etl.analysis_period.start', '2025-07-01'))
            ->whereDate('tanggal_akhir', config('etl.analysis_period.end', '2026-07-31'))
            ->orderByDesc('id_periode')
            ->value('id_periode');
        $this->p = DB::table('periode_analisis')->where('id_periode', $this->id)->first();
        View::share('periode', $this->p);
    }

    protected function cari($query, Request $r)
    {
        return $query->when($r->q, fn ($q, $s) => $q->where(
            fn ($w) => $w->where('b.kode_produk', 'like', "%$s%")->orWhere('b.nama_produk', 'like', "%$s%")
        ));
    }

    // Query dasar matriks (dipakai MatriksController & PenangananController)
    protected function matriksDasar()
    {
        return DB::table('matriks_abc_fsn as m')
            ->join('klasifikasi_abc as a', 'a.id_abc', '=', 'm.id_abc')
            ->join('klasifikasi_fsn as f', 'f.id_fsn', '=', 'm.id_fsn')
            ->join('barang as b', function ($join) {
                $join->on(
                    DB::raw('b.kode_produk COLLATE utf8mb4_unicode_ci'),
                    '=',
                    DB::raw('m.kode_produk COLLATE utf8mb4_unicode_ci')
                );
            })
            ->where('a.id_periode', $this->id);
    }

    // Tampilkan tabel berhalaman, atau unduh Excel kalau ada ?export=1
    protected function tampil($judul, $query, $kolom, $angka = [], $extra = [], $ubah = null)
    {
        if (request('export')) {
            $data = $query->get();
            if ($ubah) $data = $data->map($ubah);
            $ss = new Spreadsheet();
            $ss->getActiveSheet()->fromArray(array_values($kolom), null, 'A1');
            $ss->getActiveSheet()->fromArray(
                $data->map(fn ($r) => array_map(fn ($k) => $r->$k ?? '', array_keys($kolom)))->all(), null, 'A2'
            );
            return response()->streamDownload(
                fn () => (new Xlsx($ss))->save('php://output'),
                'Laporan_' . str_replace(' ', '_', $judul) . '.xlsx'
            );
        }
        $rows = $query->paginate(25)->withQueryString();
        if ($ubah) $rows->getCollection()->transform($ubah);
        return view('tabel', compact('judul', 'rows', 'kolom', 'angka') + $extra);
    }
}
