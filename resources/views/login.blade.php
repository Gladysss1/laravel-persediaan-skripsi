<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Masuk</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-slate-100 min-h-screen flex items-center justify-center">
<form method="POST" action="{{ route('login.masuk') }}" class="bg-white rounded shadow p-8 w-96">
    @csrf
    <h1 class="text-xl font-semibold mb-1">CV Jaya Abadi Jaya</h1>
    <p class="text-sm text-slate-500 mb-6">Sistem Pengendalian Persediaan</p>
    @if (session('gagal')) <div class="mb-4 p-3 rounded bg-red-100 text-red-800 text-sm">{{ session('gagal') }}</div> @endif
    @if ($errors->any()) <div class="mb-4 p-3 rounded bg-red-100 text-red-800 text-sm" role="alert">{{ $errors->first() }}</div> @endif
    <label class="text-sm">Username</label>
    <input name="username" value="{{ old('username') }}" class="w-full border rounded px-3 py-2 mb-3" autofocus required>
    <label class="text-sm">Password</label>
    <input type="password" name="password" class="w-full border rounded px-3 py-2 mb-5" required>
    <button class="w-full bg-blue-600 hover:bg-blue-700 text-white rounded py-2">Masuk</button>
</form>
</body></html>
