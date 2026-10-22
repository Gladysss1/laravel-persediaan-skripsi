<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class MatriksController extends PersediaanBaseController
{    private const STRATEGI = [
        'AF' => 'Kontrol ketat, prioritas pengadaan tertinggi, jaga ketersediaan',
        'AS' => 'Pantau rutin, batasi volume pemesanan',
        'AN' => 'Evaluasi, hindari pembelian ulang, promosi atau bundling',
        'BF' => 'Pantau rutin, reorder berkala',
        'BS' => 'Kontrol moderat, evaluasi volume pesanan',
        'BN' => 'Kurangi stok, promosi atau bundling',
        'CF' => 'Kontrol sederhana, pesan dalam lot',
        'CS' => 'Kontrol longgar, pesan seperlunya',
        'CN' => 'Kandidat eliminasi atau retur ke supplier',
    ];

    public function index(Request $r)
    {
        $q = $this->cari($this->matriksDasar(), $r)
            ->when($r->kelas, fn ($q, $k) => $q->where('m.kategori_matriks', $k))
            ->orderBy('m.kategori_matriks')->orderByDesc('a.total_penjualan_produk')
            ->select('b.kode_produk', 'b.nama_produk', 'a.kelas_abc', 'f.kelas_fsn', 'f.tor',
                'm.kategori_matriks', 'm.prioritas_kontrol');

        return $this->tampil('Matriks ABC-FSN', $q, [
            'kode_produk' => 'Kode', 'nama_produk' => 'Nama Produk', 'kelas_abc' => 'ABC', 'kelas_fsn' => 'FSN',
            'tor' => 'TOR', 'kategori_matriks' => 'Kategori', 'prioritas_kontrol' => 'Prioritas', 'strategi' => 'Rekomendasi Strategi',
        ], ['tor'], ['filter' => ['kelas', array_combine(array_keys(self::STRATEGI), array_keys(self::STRATEGI))]],
            function ($x) { $x->strategi = self::STRATEGI[$x->kategori_matriks] ?? '-'; return $x; });
    }
}