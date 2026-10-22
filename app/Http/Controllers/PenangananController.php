<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class PenangananController extends PersediaanBaseController
{
    // Tindakan penanganan produk slow/non-moving per kategori matriks
    private const TINDAKAN = [
        'AS' => 'Pantau, batasi volume pemesanan berikutnya',
        'AN' => 'Evaluasi penyebab, hentikan pembelian ulang, promosi atau bundling',
        'BS' => 'Evaluasi volume pesanan, pesan seperlunya',
        'BN' => 'Promosi atau bundling untuk menghabiskan stok, jangan pesan ulang',
        'CS' => 'Pesan seperlunya, kontrol longgar',
        'CN' => 'Kandidat retur ke supplier atau eliminasi dari daftar produk',
    ];

    public function index(Request $r)
    {
        $q = $this->cari($this->matriksDasar()
            ->leftJoin('rekomendasi_rop as r', function ($j) {
                $j->whereRaw('r.kode_produk COLLATE utf8mb4_unicode_ci = m.kode_produk COLLATE utf8mb4_unicode_ci')
                    ->where('r.id_periode', $this->id);
            })
            ->whereIn('f.kelas_fsn', ['S', 'N']), $r)
            ->when($r->kelas, fn ($q, $k) => $q->where('m.kategori_matriks', $k))
            ->orderByRaw("FIELD(f.kelas_fsn, 'N', 'S')")->orderByDesc('r.stok_saat_ini')
            ->selectRaw("b.kode_produk, b.nama_produk, m.kategori_matriks, f.tor, r.stok_saat_ini, r.stok_satuan,
                (SELECT s.nama_supplier FROM produk_supplier ps
                 JOIN supplier s ON s.kode_supplier COLLATE utf8mb4_unicode_ci = ps.kode_supplier COLLATE utf8mb4_unicode_ci
                 WHERE ps.kode_produk COLLATE utf8mb4_unicode_ci = m.kode_produk COLLATE utf8mb4_unicode_ci LIMIT 1) AS supplier");

        return $this->tampil('Rekomendasi Penanganan Produk', $q, [
            'kode_produk' => 'Kode', 'nama_produk' => 'Nama Produk', 'kategori_matriks' => 'Kategori', 'tor' => 'TOR',
            'stok_saat_ini' => 'Stok (pcs)', 'stok_satuan' => 'Stok (satuan)', 'supplier' => 'Supplier',
            'tindakan' => 'Rekomendasi Tindakan',
        ], ['tor', 'stok_saat_ini'],
            ['filter' => ['kelas', array_combine(array_keys(self::TINDAKAN), array_keys(self::TINDAKAN))]],
            function ($x) { $x->tindakan = self::TINDAKAN[$x->kategori_matriks] ?? '-'; return $x; });
    }
}
