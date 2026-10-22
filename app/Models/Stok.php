<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Stok extends Model
{
    protected $table = 'stok';
    protected $primaryKey = 'id_stok';
    public $timestamps = false;
    protected $guarded = [];
    protected $casts = ['tanggal' => 'date'];

    public function barang() { return $this->belongsTo(Barang::class, 'kode_produk', 'kode_produk'); }
}
