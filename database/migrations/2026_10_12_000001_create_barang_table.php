<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('barang')) {
                    Schema::create('barang', function (Blueprint $table) {
                        $table->string('kode_produk', 50)->collation('utf8mb4_0900_ai_ci')->primary();
                        $table->string('nama_produk', 150);
                        $table->string('satuan', 20)->nullable();
                        $table->string('satuan_2', 20)->nullable();
                        $table->string('satuan_3', 20)->nullable();
                        $table->decimal('nisi', 18, 2)->nullable();
                        $table->decimal('nisi_2', 18, 2)->nullable();
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('barang');
    }
};
