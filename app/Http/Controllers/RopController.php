<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class RopController extends PersediaanBaseController
{
    public function index(Request $r)
    {
        $q = $this->cari(DB::table('rekomendasi_rop as r')->leftJoin('barang as b', function ($join) {
            $join->whereRaw('b.kode_produk COLLATE utf8mb4_unicode_ci = r.kode_produk COLLATE utf8mb4_unicode_ci');
        })
            ->where('r.id_periode', $this->id), $r)
            ->when($r->status, function ($q, $filter) {
                if ($filter === 'stok_nol') {
                    return $q->where('r.stok_saat_ini', 0);
                }
                if ($filter === 'stok_negatif') {
                    return $q->where('r.stok_saat_ini', '<', 0);
                }
                if ($filter === 'Data stok tidak ada') {
                    return $q->whereNull('r.stok_saat_ini');
                }
                return $q->where('r.status_reorder', $filter);
            })
            ->when($r->filled('kategori'), function ($q) use ($r) {
                $kategori = strtoupper($r->input('kategori'));
                $kategoriValid = ['AF', 'AS', 'AN', 'BF', 'BS', 'BN', 'CF', 'CS', 'CN'];
                return in_array($kategori, $kategoriValid, true)
                    ? $q->where('r.kategori_matriks', $kategori)
                    : $q->whereRaw('1 = 0');
            })
            ->orderByRaw("r.status_reorder = 'Reorder' DESC")->orderBy('r.kategori_matriks')
            ->selectRaw("r.kode_produk, COALESCE(b.nama_produk, '(Nama produk tidak tersedia)') AS nama_produk")
            ->addSelect('r.kategori_matriks', 'r.rata_rata_penjualan', 'r.lead_time',
                'r.service_level', 'r.safety_stock', 'r.reorder_point', 'r.stok_saat_ini', 'r.stok_satuan',
                'r.status_reorder', 'r.tanggal_mulai_data', 'r.tanggal_akhir_data', 'r.waktu_snapshot');

        return $this->tampil('Rekomendasi Reorder Point', $q, [
            'kode_produk' => 'Kode', 'nama_produk' => 'Nama Produk', 'kategori_matriks' => 'Kategori',
            'rata_rata_penjualan' => 'Rata-rata/hari', 'lead_time' => 'Lead Time (hari)', 'service_level' => 'Service Level',
            'safety_stock' => 'Safety Stock', 'reorder_point' => 'ROP (pcs)', 'stok_saat_ini' => 'Stok (pcs)',
            'stok_satuan' => 'Stok (satuan)', 'status_reorder' => 'Status',
            'tanggal_mulai_data' => 'Data ROP Mulai', 'tanggal_akhir_data' => 'Data ROP Sampai',
            'waktu_snapshot' => 'Terakhir Diperbarui',
        ], ['rata_rata_penjualan', 'lead_time', 'service_level', 'safety_stock', 'reorder_point', 'stok_saat_ini'],
            ['filters' => [
                ['status', 'status', [
                    'Reorder' => 'Reorder',
                    'Aman' => 'Aman',
                    'stok_nol' => 'Stok = 0',
                    'stok_negatif' => 'Stok negatif',
                    'Data stok tidak ada' => 'Data stok tidak ada',
                ]],
                ['kategori', 'kategori matriks', [
                    'AF' => 'AF', 'AS' => 'AS', 'AN' => 'AN',
                    'BF' => 'BF', 'BS' => 'BS', 'BN' => 'BN',
                    'CF' => 'CF', 'CS' => 'CS', 'CN' => 'CN',
                ]],
            ]]);
    }
}
