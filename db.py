"""Database layer for Radhe Radhe Developer app.
SQLite file is stored next to the executable so data stays on the local computer.
"""
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
import re

# In a PyInstaller one-file EXE, __file__ points inside a temporary extraction
# folder. Keep the live database beside the EXE so it persists between launches.
BASE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
COMPANIES_DIR = BASE / "Companies"
COMPANIES_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_COMPANY_FILE = BASE / "active_company.txt"

def _safe_company(name):
    name = re.sub(r"[^A-Za-z0-9 _-]", "", str(name or "")).strip()
    return name[:60] or "Radhe Radhe Developer"

def list_companies():
    names = ["Radhe Radhe Developer"]
    if COMPANIES_DIR.exists():
        names.extend(p.name for p in COMPANIES_DIR.iterdir() if p.is_dir())
    return list(dict.fromkeys(names))

def get_active_company():
    try:
        name = ACTIVE_COMPANY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        name = "Radhe Radhe Developer"
    return _safe_company(name)

def set_active_company(name):
    global DB_PATH, BACKUP_DIR, TEMP_BACKUP_DIR
    name = _safe_company(name)
    if name == "Radhe Radhe Developer":
        DB_PATH = BASE / "radhe_radhe.db"
    else:
        DB_PATH = COMPANIES_DIR / name / "radhe_radhe.db"
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR = DB_PATH.parent / "Backup"
    TEMP_BACKUP_DIR = DB_PATH.parent / "temp"
    ACTIVE_COMPANY_FILE.write_text(name, encoding="utf-8")
    return name

DB_PATH = BASE / "radhe_radhe.db"
BACKUP_DIR = BASE / "Backup"
TEMP_BACKUP_DIR = BASE / "temp"
set_active_company(get_active_company())


def _company_backup_slug():
    name = get_active_company()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return (slug or "RadheRadheDeveloper")[:60]


def _validate_database_file(path):
    con = sqlite3.connect(str(path))
    try:
        check = con.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise ValueError("SQLite integrity check failed.")
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"dos", "builtys", "bills"}.issubset(tables):
            raise ValueError("Backup is missing required DO, Builty and Bill tables.")
    finally:
        con.close()


def _atomic_sqlite_copy(source_path, destination):
    """Copy a SQLite database and close every handle before atomic replace (Windows-safe)."""
    import os
    import tempfile
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=str(destination.parent))
    os.close(fd)
    source = target = None
    try:
        source = sqlite3.connect(str(source_path))
        target = sqlite3.connect(temp_name)
        source.backup(target)
        target.commit()
        target.close()
        target = None
        source.close()
        source = None
        _validate_database_file(temp_name)
        os.replace(temp_name, destination)
    finally:
        if target is not None:
            target.close()
        if source is not None:
            source.close()
        try:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        except OSError:
            pass


def _validate_sql_dump(sql_path):
    import os
    import tempfile
    fd, temp_name = tempfile.mkstemp(prefix="rr_sql_validate_", suffix=".db", dir=str(BASE))
    os.close(fd)
    test = None
    try:
        test = sqlite3.connect(temp_name)
        test.executescript(Path(sql_path).read_text(encoding="utf-8"))
        test.close()
        test = None
        _validate_database_file(temp_name)
    finally:
        if test is not None:
            test.close()
        try:
            os.remove(temp_name)
        except OSError:
            pass


def backup_database():
    """Create retained daily .db/.sql backups beside the EXE and refresh company-specific temp copies."""
    import os
    import tempfile
    if not DB_PATH.exists():
        return []
    slug = _company_backup_slug()
    stamp = date.today().isoformat()
    daily_db = BASE / f"RadheRadhe_{slug}_{stamp}.db"
    daily_sql = BASE / f"RadheRadhe_{slug}_{stamp}.sql"
    temp_dir = BASE / "temp" / slug
    temp_dir.mkdir(parents=True, exist_ok=True)
    latest_db = temp_dir / "RadheRadhe_latest.db"
    latest_sql = temp_dir / "RadheRadhe_latest.sql"
    # Refresh today's snapshot each time; previous dates remain untouched.
    _atomic_sqlite_copy(DB_PATH, daily_db)
    _atomic_sqlite_copy(DB_PATH, latest_db)
    source = sqlite3.connect(str(DB_PATH))
    try:
        fd, temp_name = tempfile.mkstemp(prefix=daily_sql.name + ".", suffix=".tmp", dir=str(BASE))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\\n") as stream:
                for line in source.iterdump():
                    stream.write(line + "\\n")
            _validate_sql_dump(temp_name)
            os.replace(temp_name, daily_sql)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        fd, temp_name = tempfile.mkstemp(prefix=latest_sql.name + ".", suffix=".tmp", dir=str(temp_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\\n") as stream:
                for line in source.iterdump():
                    stream.write(line + "\\n")
            _validate_sql_dump(temp_name)
            os.replace(temp_name, latest_sql)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
    finally:
        source.close()
    return [daily_db, daily_sql, latest_db, latest_sql]

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
