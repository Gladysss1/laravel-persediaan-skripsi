<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class ProdukSupplier extends Model
{
    protected $table = 'produk_supplier';
    protected $primaryKey = 'id_produk_supplier';
    public $timestamps = false;
    protected $guarded = [];

    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
    public function supplier() { return $this->belongsTo(Supplier::class, 'kode_supplier', 'kode_supplier'); }
}
