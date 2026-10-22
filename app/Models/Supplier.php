<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Supplier extends Model
{
    protected $table = 'supplier';
    protected $primaryKey = 'kode_supplier';
    public $incrementing = false;
    protected $keyType = 'string';
    public $timestamps = false;
    protected $guarded = [];
    protected $casts = ['lead_time' => 'integer'];

    public function produkSupplier() { return $this->hasMany(ProdukSupplier::class, 'kode_supplier', 'kode_supplier'); }
}
