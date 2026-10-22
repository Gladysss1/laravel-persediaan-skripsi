<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class BarangDetail extends Model
{
    protected $table = 'barang_detail';
    protected $primaryKey = 'id_barang_detail';
    public $timestamps = false;
    protected $guarded = [];

    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
}
