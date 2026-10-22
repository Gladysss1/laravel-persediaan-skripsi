<?php

namespace App\Models;

use Illuminate\Foundation\Auth\User as Authenticatable;

class User extends Authenticatable
{
    protected $table = 'users';
    protected $primaryKey = 'id_user';
    public $timestamps = false;
    protected $guarded = ['id_user'];
    protected $hidden = ['password'];

    public function logEtl() { return $this->hasMany(LogEtl::class, 'id_user', 'id_user'); }
}
