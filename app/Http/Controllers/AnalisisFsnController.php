<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class AnalisisFsnController extends PersediaanBaseController
{
    public function index(Request $r)
    {
        $q = $this->cari(DB::table('klasifikasi_fsn as f')->join('barang as b', function ($join) {
            $join->whereRaw('b.kode_produk COLLATE utf8mb4_unicode_ci = f.kode_produk COLLATE utf8mb4_unicode_ci');
        })
            ->where('f.id_periode', $this->id), $r)
            ->when($r->kelas, fn ($q, $k) => $q->where('f.kelas_fsn', $k))
            ->orderByDesc('f.tor')
            ->select('b.kode_produk', 'b.nama_produk', 'f.total_kuantitas_penjualan', 'f.rata_rata_persediaan', 'f.tor', 'f.kelas_fsn');

        return $this->tampil('Analisis FSN', $q, [
            'kode_produk' => 'Kode', 'nama_produk' => 'Nama Produk', 'total_kuantitas_penjualan' => 'Qty Jual (pcs)',
            'rata_rata_persediaan' => 'Rata-rata Persediaan', 'tor' => 'TOR', 'kelas_fsn' => 'Kelas',
        ], ['total_kuantitas_penjualan', 'rata_rata_persediaan', 'tor'],
            ['filter' => ['kelas', ['F' => 'Fast Moving', 'S' => 'Slow Moving', 'N' => 'Non-Moving']]]);
    }
}
