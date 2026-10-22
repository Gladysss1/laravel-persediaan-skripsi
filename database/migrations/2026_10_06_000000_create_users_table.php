<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('users')) {
            Schema::create('users', function (Blueprint $table) {
                $table->increments('id_user');
                $table->string('nama', 100);
                $table->string('username', 50)->unique();
                $table->string('password');
                $table->string('role', 30);
            });
            foreach ([['Owner', 'owner', 'owner'], ['Admin Pembelian', 'pembelian', 'admin_pembelian'], ['Admin Stok', 'stok', 'admin_stok']] as [$nama, $username, $role]) {
                DB::table('users')->insert(['nama' => $nama, 'username' => $username, 'password' => Hash::make('admin123'), 'role' => $role]);
            }
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('users');
    }
};
