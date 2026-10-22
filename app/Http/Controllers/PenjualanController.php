<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class PenjualanController extends PersediaanBaseController
{
    // Laporan penjualan per produk
    public function index(Request $r)
    {
        $query = DB::table('detail_penjualan as d')
            ->join('barang as b', function ($join) {
                $join->on(
                    DB::raw('b.kode_produk COLLATE utf8mb4_unicode_ci'),
                    '=',
                    DB::raw('d.kode_produk COLLATE utf8mb4_unicode_ci')
                );
            })
            ->whereBetween('d.tanggal', [
                $this->p->tanggal_mulai ?? '1900-01-01',
                $this->p->tanggal_akhir ?? '2999-12-31',
            ])
            ->groupBy('b.kode_produk', 'b.nama_produk')
            ->orderByDesc('nilai')
            ->selectRaw(
                'b.kode_produk,
                 b.nama_produk,
                 COUNT(DISTINCT d.no_penjualan) AS transaksi,
                 SUM(d.total_qty) AS total_qty,
                 SUM(d.subtotal) AS nilai'
            );

        $query = $this->cari($query, $r);

        return $this->tampil(
            'Laporan Penjualan',
            $query,
            [
                'kode_produk' => 'Kode',
                'nama_produk' => 'Nama Produk',
                'transaksi' => 'Jml Nota',
                'total_qty' => 'Total Qty (pcs)',
                'nilai' => 'Nilai Penjualan (Rp)',
            ],
            ['transaksi', 'total_qty', 'nilai']
        );
    }
}