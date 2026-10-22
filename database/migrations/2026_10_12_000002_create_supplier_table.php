<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('supplier')) {
                    Schema::create('supplier', function (Blueprint $table) {
                        $table->string('kode_supplier', 50)->collation('utf8mb4_0900_ai_ci')->primary();
                        $table->string('nama_supplier', 150)->nullable();
                        $table->string('alamat', 255)->nullable();
                        $table->string('kota', 100)->nullable();
                        $table->string('telepon', 30)->nullable();
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('supplier');
    }
};
