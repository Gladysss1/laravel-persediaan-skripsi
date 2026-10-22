<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('produk_supplier')) {
                    Schema::create('produk_supplier', function (Blueprint $table) {
                        $table->integer('id_produk_supplier')->autoIncrement()->primary();
                        $table->string('kode_produk', 50);
                        $table->string('kode_supplier', 50);
                        $table->integer('lead_time')->nullable();
                        $table->unique(['kode_produk', 'kode_supplier'], 'uq_produk_supplier');
                        $table->foreign('kode_produk')->references('kode_produk')->on('barang');
                        $table->foreign('kode_supplier')->references('kode_supplier')->on('supplier');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('produk_supplier');
    }
};
