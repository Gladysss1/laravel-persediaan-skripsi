<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class RekomendasiRop extends Model
{
    protected $table = 'rekomendasi_rop';
    protected $primaryKey = 'id_rop';
    public $timestamps = false;
    protected $guarded = [];
    protected $casts = [
        'tanggal_mulai_data' => 'date',
        'tanggal_akhir_data' => 'date',
    ];

    public function periode() { return $this->belongsTo(PeriodeAnalisis::class, 'id_periode', 'id_periode'); }
    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
    public function matriks() { return $this->belongsTo(MatriksAbcFsn::class, 'id_matriks', 'id_matriks'); }
    public function produkSupplier() { return $this->belongsTo(ProdukSupplier::class, 'id_produk_supplier', 'id_produk_supplier'); }
}
