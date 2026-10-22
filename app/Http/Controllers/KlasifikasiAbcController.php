<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class KlasifikasiAbcController extends PersediaanBaseController
{
    public function index(Request $r)
    {
        $q = $this->cari(DB::table('klasifikasi_abc as a')->join('barang as b', function ($join) {
            $join->whereRaw('b.kode_produk COLLATE utf8mb4_unicode_ci = a.kode_produk COLLATE utf8mb4_unicode_ci');
        })
            ->where('a.id_periode', $this->id), $r)
            ->when($r->kelas, fn ($q, $k) => $q->where('a.kelas_abc', $k))
            ->orderByDesc('a.total_penjualan_produk')
            ->select('b.kode_produk', 'b.nama_produk', 'a.qty_terjual', 'a.total_penjualan_produk',
                'a.persentase_nilai', 'a.persentase_kumulatif', 'a.kelas_abc');

        return $this->tampil('Klasifikasi ABC', $q, [
            'kode_produk' => 'Kode', 'nama_produk' => 'Nama Produk', 'qty_terjual' => 'Qty Terjual',
            'total_penjualan_produk' => 'Nilai Penjualan (Rp)', 'persentase_nilai' => '% Kontribusi',
            'persentase_kumulatif' => '% Kumulatif', 'kelas_abc' => 'Kelas',
        ], ['qty_terjual', 'total_penjualan_produk', 'persentase_nilai', 'persentase_kumulatif'],
            ['filter' => ['kelas', ['A' => 'Kelas A', 'B' => 'Kelas B', 'C' => 'Kelas C']]]);
    }
}
