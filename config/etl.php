<?php

return [
    'path' => env('ETL_PATH', base_path('etl')),
    'python_bin' => env('PYTHON_BIN', 'python'),
    'python_args' => array_values(array_filter(
        preg_split('/\s+/', trim((string) env('PYTHON_ARGS', ''))) ?: [],
        fn ($arg) => $arg !== ''
    )),
    'python_path' => env('PYTHONPATH', ''),
    'python_hash_seed' => env('PYTHONHASHSEED', '0'),

    'analysis_period' => [
        'start' => env('ANALYSIS_START_DATE', '2025-07-01'),
        'end' => env('ANALYSIS_END_DATE', '2026-07-31'),
    ],

    'rop_auto_refresh' => [
        'enabled' => filter_var(env('ROP_AUTO_REFRESH_ENABLED', false), FILTER_VALIDATE_BOOL),
        'interval_minutes' => max(1, (int) env('ROP_AUTO_REFRESH_INTERVAL_MINUTES', 15)),
    ],

    'sqlserver' => [
        'driver' => env('SQLSERVER_DRIVER', 'SQL Server'),
        'server' => env('SQLSERVER_SERVER', 'SERVERBARU1'),
        'database' => env('SQLSERVER_DATABASE', 'dbGrosir'),
        'trusted_connection' => env('SQLSERVER_TRUSTED_CONNECTION', 'yes'),
        'username' => env('SQLSERVER_USERNAME', ''),
        'password' => env('SQLSERVER_PASSWORD', ''),
    ],
];
