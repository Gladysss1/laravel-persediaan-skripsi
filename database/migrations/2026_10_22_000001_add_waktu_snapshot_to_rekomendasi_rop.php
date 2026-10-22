<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (Schema::hasTable('rekomendasi_rop') && !Schema::hasColumn('rekomendasi_rop', 'waktu_snapshot')) {
            Schema::table('rekomendasi_rop', function (Blueprint $table) {
                $table->dateTime('waktu_snapshot')->nullable();
            });
        }
    }

    public function down(): void
    {
        if (Schema::hasTable('rekomendasi_rop') && Schema::hasColumn('rekomendasi_rop', 'waktu_snapshot')) {
            Schema::table('rekomendasi_rop', function (Blueprint $table) {
                $table->dropColumn('waktu_snapshot');
            });
        }
    }
};
