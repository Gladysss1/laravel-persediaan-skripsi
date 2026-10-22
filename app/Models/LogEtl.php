<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class LogEtl extends Model
{
    protected $table = 'log_etl';
    protected $primaryKey = 'id_log';
    public $timestamps = false;
    protected $guarded = [];
    protected $casts = ['waktu_mulai' => 'datetime', 'waktu_selesai' => 'datetime'];

    public function user() { return $this->belongsTo(User::class, 'id_user', 'id_user'); }
}
