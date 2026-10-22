<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class RopController extends PersediaanBaseController
{
    public function index(Request $r)
    {
        $query = DB::table('rekomendasi_rop as r')
            ->join('barang as b', function ($join) {
                $join->on(
                    DB::raw('b.kode_produk COLLATE utf8mb4_unicode_ci'),
                    '=',
                    DB::raw('r.kode_produk COLLATE utf8mb4_unicode_ci')
                );
            })
            ->where('r.id_periode', $this->id);

        $query = $this->cari($query, $r)
            ->when(
                $r->filled('status'),
                fn ($q) => $q->where('r.status_reorder', $r->status)
            )
            ->orderByRaw("r.status_reorder = 'Reorder' DESC")
            ->orderBy('r.kategori_matriks')
            ->select(
                'b.kode_produk',
                'b.nama_produk',
                'r.kategori_matriks',
                'r.rata_rata_penjualan',
                'r.lead_time',
                'r.service_level',
                'r.safety_stock',
                'r.reorder_point',
                'r.stok_saat_ini',
                'r.stok_satuan',
                'r.status_reorder',
                'r.tanggal_mulai_data',
                'r.tanggal_akhir_data',
                'r.waktu_snapshot'
            );

        return $this->tampil(
            'Rekomendasi Reorder Point',
            $query,
            [
                'kode_produk' => 'Kode',
                'nama_produk' => 'Nama Produk',
                'kategori_matriks' => 'Kategori',
                'rata_rata_penjualan' => 'Rata-rata/hari',
                'lead_time' => 'Lead Time (hari)',
                'service_level' => 'Service Level',
                'safety_stock' => 'Safety Stock',
                'reorder_point' => 'ROP (pcs)',
                'stok_saat_ini' => 'Stok (pcs)',
                'stok_satuan' => 'Stok (satuan)',
                'status_reorder' => 'Status',
                'tanggal_mulai_data' => 'Data ROP Mulai',
                'tanggal_akhir_data' => 'Data ROP Sampai',
                'waktu_snapshot' => 'Terakhir Diperbarui',
            ],
            [
                'rata_rata_penjualan',
                'lead_time',
                'service_level',
                'safety_stock',
                'reorder_point',
                'stok_saat_ini',
            ],
            [
                'filter' => [
                    'status',
                    [
                        'Reorder' => 'Reorder',
                        'Aman' => 'Aman',
                        'Data stok tidak ada' => 'Data stok tidak ada',
                    ],
                ],
            ]
        );
    }
}