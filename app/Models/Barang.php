<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Barang extends Model
{
    protected $table = 'barang';
    protected $primaryKey = 'kode_produk';
    public $incrementing = false;
    protected $keyType = 'string';
    public $timestamps = false;
    protected $guarded = [];

    public function detail() { return $this->hasMany(BarangDetail::class, 'kode_produk', 'kode_produk'); }
    public function detailPenjualan() { return $this->hasMany(DetailPenjualan::class, 'kode_produk', 'kode_produk'); }
    public function stok() { return $this->hasMany(Stok::class, 'kode_produk', 'kode_produk'); }
    public function klasifikasiAbc() { return $this->hasMany(KlasifikasiAbc::class, 'kode_produk', 'kode_produk'); }
    public function klasifikasiFsn() { return $this->hasMany(KlasifikasiFsn::class, 'kode_produk', 'kode_produk'); }
    public function produkSupplier() { return $this->hasMany(ProdukSupplier::class, 'kode_produk', 'kode_produk'); }
}
