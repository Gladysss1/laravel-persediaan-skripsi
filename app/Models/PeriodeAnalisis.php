<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class PeriodeAnalisis extends Model
{
    protected $table = 'periode_analisis';
    protected $primaryKey = 'id_periode';
    public $timestamps = false;
    protected $guarded = [];
    protected $casts = ['tanggal_mulai' => 'date', 'tanggal_akhir' => 'date'];

    public function klasifikasiAbc() { return $this->hasMany(KlasifikasiAbc::class, 'id_periode', 'id_periode'); }
    public function klasifikasiFsn() { return $this->hasMany(KlasifikasiFsn::class, 'id_periode', 'id_periode'); }
    public function rekomendasiRop() { return $this->hasMany(RekomendasiRop::class, 'id_periode', 'id_periode'); }
}
