<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('periode_analisis')) {
                    Schema::create('periode_analisis', function (Blueprint $table) {
                        $table->integer('id_periode')->autoIncrement()->primary();
                        $table->date('tanggal_mulai');
                        $table->date('tanggal_akhir');
                    });
                }
    }

    public function down(): void
    {
        Schema::dropIfExists('periode_analisis');
    }
};
