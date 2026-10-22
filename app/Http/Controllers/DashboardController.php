<?php

namespace App\Http\Controllers;

use Illuminate\Support\Facades\DB;

class DashboardController extends PersediaanBaseController
{
    public function dashboard()
    {
        $hitung = fn ($tabel, $kol) => DB::table($tabel)->where('id_periode', $this->id)
            ->selectRaw("$kol k, COUNT(*) n")->groupBy($kol)->pluck('n', 'k');

        $matriks = DB::table('matriks_abc_fsn as m')->join('klasifikasi_abc as a', 'a.id_abc', '=', 'm.id_abc')
            ->where('a.id_periode', $this->id)->selectRaw('m.kategori_matriks k, COUNT(*) n')
            ->groupBy('m.kategori_matriks')->pluck('n', 'k');

        $perlu = DB::table('rekomendasi_rop as r')->join('barang as b', 'b.kode_produk', '=', 'r.kode_produk')
            ->where('r.id_periode', $this->id)->where('r.status_reorder', 'Reorder')
            ->orderBy('r.kategori_matriks')->orderByDesc('r.reorder_point')
            ->select('r.kode_produk', 'b.nama_produk', 'r.kategori_matriks', 'r.stok_satuan', 'r.reorder_point')
            ->limit(10)->get();

        $top = DB::table('klasifikasi_abc as a')->join('klasifikasi_fsn as f', function ($j) {
                $j->on('f.kode_produk', '=', 'a.kode_produk')->on('f.id_periode', '=', 'a.id_periode');
            })->join('barang as b', 'b.kode_produk', '=', 'a.kode_produk')
            ->where('a.id_periode', $this->id)->where('a.kelas_abc', 'A')->where('f.kelas_fsn', 'F')
            ->orderByDesc('a.total_penjualan_produk')->limit(10)
            ->select('b.nama_produk', 'a.total_penjualan_produk')->get();

        return view('dashboard', ['top' => $top] + [
            'abc' => $hitung('klasifikasi_abc', 'kelas_abc'), 'fsn' => $hitung('klasifikasi_fsn', 'kelas_fsn'),
            'rop' => $hitung('rekomendasi_rop', 'status_reorder'), 'matriks' => $matriks, 'perlu' => $perlu,
        ]);
    }
}