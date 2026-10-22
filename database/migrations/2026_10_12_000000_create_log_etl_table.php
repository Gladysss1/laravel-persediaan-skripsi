<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration {
    public function up(): void
    {
        if (!Schema::hasTable('log_etl')) {
            Schema::create('log_etl', function (Blueprint $table) {
                $table->increments('id_log');
                $table->unsignedInteger('id_user')->nullable();
                $table->dateTime('waktu_mulai');
                $table->dateTime('waktu_selesai')->nullable();
                $table->string('status', 20);
                $table->integer('jumlah_data')->nullable();
            });
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('log_etl');
    }
};
