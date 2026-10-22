"""Shared connection settings for the Laravel-launched ETL scripts."""

import os
from datetime import date
from pathlib import Path

from sqlalchemy import URL, create_engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def _load_project_env():
    """Read basic Laravel .env values for ETL commands run directly in PowerShell."""
    if not ENV_FILE.is_file():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            quote = value[0]
            value = value[1:-1]
            if quote == '"':
                value = value.replace("\\n", "\n").replace("\\r", "\r")
        else:
            value = value.split(" #", 1)[0].strip()
        os.environ.setdefault(key, value)


def rentang_analisis_default():
    """Return the fixed annual analysis window as inclusive dates.

    Configure ANALYSIS_START_DATE and ANALYSIS_END_DATE in Laravel's .env.
    The SQL scripts convert the inclusive end date to an exclusive boundary.
    """
    _load_project_env()
    mulai = date.fromisoformat(os.getenv("ANALYSIS_START_DATE", "2025-07-01"))
    akhir = date.fromisoformat(os.getenv("ANALYSIS_END_DATE", "2026-07-31"))
    if mulai > akhir:
        raise ValueError("ANALYSIS_START_DATE harus sebelum atau sama dengan ANALYSIS_END_DATE.")
    return mulai, akhir


def buat_mysql_url():
    """Build a URL from database settings forwarded by Laravel."""
    _load_project_env()
    return URL.create(
        drivername=os.getenv("ETL_DB_DRIVER", "mysql+pymysql"),
        username=os.getenv("ETL_DB_USERNAME", os.getenv("DB_USERNAME", "root")),
        password=os.getenv("ETL_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        host=os.getenv("ETL_DB_HOST", os.getenv("DB_HOST", "127.0.0.1")),
        port=int(os.getenv("ETL_DB_PORT", os.getenv("DB_PORT", "3306"))),
        database=os.getenv(
            "ETL_DB_DATABASE", os.getenv("DB_DATABASE", "webskripsi")
        ),
    )


def buat_mysql_engine():
    return create_engine(buat_mysql_url())


def koneksi_sql_server():
    """Build a pyodbc connection string for Windows trusted or SQL authentication."""
    _load_project_env()
    driver = os.getenv("SQLSERVER_DRIVER", "SQL Server")
    server = os.getenv("SQLSERVER_SERVER", "SERVERBARU1")
    database = os.getenv("SQLSERVER_DATABASE", "dbGrosir")
    trusted = os.getenv("SQLSERVER_TRUSTED_CONNECTION", "yes").lower() in {"yes", "true", "1"}
    format_value = lambda value: "{" + str(value or "").replace("}", "}}") + "}"
    bagian = [
        f"DRIVER={format_value(driver)}",
        f"SERVER={format_value(server)}",
        f"DATABASE={format_value(database)}",
    ]
    if trusted:
        bagian.append("Trusted_Connection=yes")
    else:
        bagian.extend([
            f"UID={format_value(os.getenv('SQLSERVER_USERNAME', ''))}",
            f"PWD={format_value(os.getenv('SQLSERVER_PASSWORD', ''))}",
        ])
    return ";".join(bagian) + ";"
