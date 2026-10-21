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

COMPANY_DISPLAY_NAMES = {
    "E": "NILKANTH LOGISTICS",
    "K": "K. D. ENTERPRISE",
    "N": "M R ENTERPRISE",
    "R": "SHREE RAMDEV ENTERPRISE",
    "S": "SHIVAY LOGISTICS",
    "P": "PARTH ENTERPRISE",
    "M": "MANSI COAL CAREER",
}
_DISPLAY_TO_CODE = {label.casefold(): code for code, label in COMPANY_DISPLAY_NAMES.items()}


def _safe_company(name):
    value = str(name or "").strip()
    # Accept either the user-facing company label or its stable storage code.
    if value.casefold() in _DISPLAY_TO_CODE:
        return _DISPLAY_TO_CODE[value.casefold()]
    value = re.sub(r"[^A-Za-z0-9 _-]", "", value).strip()
    return value[:60] or "Radhe Radhe Developer"


def display_company_name(name):
    code = _safe_company(name)
    return COMPANY_DISPLAY_NAMES.get(code, code)


def list_companies():
    names = ["Radhe Radhe Developer"]
    # Always expose the seven configured company names, while retaining their
    # existing code-named storage directories (E/K/N/R/S/P/M).
    names.extend(COMPANY_DISPLAY_NAMES[code] for code in ("E", "K", "N", "R", "S", "P", "M"))
    if COMPANIES_DIR.exists():
        for p in COMPANIES_DIR.iterdir():
            if p.is_dir() and p.name not in COMPANY_DISPLAY_NAMES:
                names.append(p.name)
    return list(dict.fromkeys(names))


def get_active_company():
    try:
        name = ACTIVE_COMPANY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        name = "Radhe Radhe Developer"
    code = _safe_company(name)
    return "Radhe Radhe Developer" if code == "Radhe Radhe Developer" else display_company_name(code)


def set_active_company(name):
    global DB_PATH, BACKUP_DIR, TEMP_BACKUP_DIR
    code = _safe_company(name)
    if code == "Radhe Radhe Developer":
        DB_PATH = BASE / "radhe_radhe.db"
        ACTIVE_COMPANY_FILE.write_text("Radhe Radhe Developer", encoding="utf-8")
    else:
        DB_PATH = COMPANIES_DIR / code / "radhe_radhe.db"
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_COMPANY_FILE.write_text(code, encoding="utf-8")
    BACKUP_DIR = DB_PATH.parent / "Backup"
    TEMP_BACKUP_DIR = DB_PATH.parent / "temp"
    return display_company_name(code)


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
    """Copy SQLite safely on Windows: close all handles before replacing destination."""
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
    """Execute a SQL dump in an isolated DB and close every SQLite handle (Windows-safe)."""
    import os
    import tempfile
    fd, temp_name = tempfile.mkstemp(prefix="rr_sql_validate_", suffix=".db", dir=str(BASE))
    os.close(fd)
    test = None
    try:
        test = sqlite3.connect(temp_name)
        test.executescript(Path(sql_path).read_text(encoding="utf-8"))
        test.commit()
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
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                for line in source.iterdump():
                    stream.write(line + "\n")
            _validate_sql_dump(temp_name)
            os.replace(temp_name, daily_sql)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
        fd, temp_name = tempfile.mkstemp(prefix=latest_sql.name + ".", suffix=".tmp", dir=str(temp_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                for line in source.iterdump():
                    stream.write(line + "\n")
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


def init_db():
    con = db()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS dos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            do_no TEXT UNIQUE,
            gmdc_do_no TEXT,
            do_date TEXT,
            customer_no TEXT,
            customer_name TEXT,
            customer_gstin TEXT,
            order_type TEXT,
            bill_to TEXT,
            ship_to TEXT,
            state TEXT,
            hsn TEXT,
            material TEXT,
            schedule_date TEXT,
            qty REAL DEFAULT 0,
            uom TEXT,
            unit_price REAL DEFAULT 0,
            extended_price REAL DEFAULT 0,
            transporter_code TEXT,
            transporter_name TEXT,
            order_total REAL DEFAULT 0,
            remaining_qty REAL DEFAULT 0,
            source_pdf TEXT,
            from_place TEXT DEFAULT 'BHAVNAGAR',
            to_place TEXT,
            to_ma_dist TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS do_schedules(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            do_id INTEGER NOT NULL,
            schedule_date TEXT NOT NULL,
            qty REAL NOT NULL DEFAULT 0,
            remaining_qty REAL NOT NULL DEFAULT 0,
            uom TEXT DEFAULT 'TON',
            unit_price REAL DEFAULT 0,
            extended_price REAL DEFAULT 0,
            UNIQUE(do_id, schedule_date),
            FOREIGN KEY(do_id) REFERENCES dos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS builtys(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            builty_no TEXT UNIQUE,
            do_id INTEGER NOT NULL,
            truck_no TEXT,
            date TEXT,
            qty REAL NOT NULL DEFAULT 0,
            freight_rate REAL DEFAULT 0,
            freight_amount REAL DEFAULT 0,
            from_place TEXT,
            to_place TEXT,
            consignor TEXT,
            consignee TEXT,
            driver_name TEXT,
            ewaybill TEXT,
            remarks TEXT,
            billed INTEGER NOT NULL DEFAULT 0,
            freight_paid INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(do_id) REFERENCES dos(id)
        );

        CREATE TABLE IF NOT EXISTS bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_no TEXT UNIQUE,
            bill_date TEXT,
            bill_type TEXT DEFAULT 'MATERIAL',
            customer_name TEXT,
            customer_gstin TEXT,
            total_qty REAL NOT NULL DEFAULT 0,
            rate_per_ton REAL DEFAULT 0,
            subtotal REAL DEFAULT 0,
            cgst REAL DEFAULT 0,
            sgst REAL DEFAULT 0,
            igst REAL DEFAULT 0,
            total REAL DEFAULT 0,
            remarks TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS bill_builtys(
            bill_id INTEGER NOT NULL,
            builty_id INTEGER NOT NULL,
            PRIMARY KEY(bill_id,builty_id),
            FOREIGN KEY(bill_id) REFERENCES bills(id),
            FOREIGN KEY(builty_id) REFERENCES builtys(id)
        );

        CREATE TABLE IF NOT EXISTS freight_paid(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            builty_id INTEGER NOT NULL,
            pay_date TEXT,
            amount REAL NOT NULL DEFAULT 0,
            mode TEXT,
            reference_no TEXT,
            remarks TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(builty_id) REFERENCES builtys(id)
        );

        CREATE TABLE IF NOT EXISTS debit_notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dn_no TEXT UNIQUE,
            dn_date TEXT,
            party TEXT,
            amount REAL DEFAULT 0,
            reason TEXT,
            builty_ids TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS freight_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_place TEXT,
            to_place TEXT,
            material TEXT,
            rate_per_ton REAL NOT NULL DEFAULT 0,
            effective_date TEXT,
            remarks TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    # Preserve the full Builty form across app restarts and when editing old records.
    builty_columns = {
        "mobile_no": "TEXT", "owner_name": "TEXT", "address": "TEXT",
        "challan_no": "TEXT", "quota_date": "TEXT", "pay_status": "TEXT",
        "cgst_rate": "REAL DEFAULT 0", "sgst_rate": "REAL DEFAULT 0",
        "sale_party": "TEXT", "supply_party": "TEXT", "center_name": "TEXT",
        "quota_select": "TEXT", "vehicle_no": "TEXT", "sale_rate": "REAL DEFAULT 0",
        "sale_amount": "REAL DEFAULT 0", "despatch_weight": "REAL DEFAULT 0",
        "receipt_weight": "REAL DEFAULT 0", "freight_type": "TEXT",
        "commission": "REAL DEFAULT 0", "driver_payable": "REAL DEFAULT 0", "receipt_date": "TEXT",
        "driver_mobile": "TEXT", "voucher_remarks": "TEXT", "blt_print": "TEXT",
    }
    existing_builty = {row[1] for row in con.execute("PRAGMA table_info(builtys)")}
    for column, sql_type in builty_columns.items():
        if column not in existing_builty:
            con.execute(f"ALTER TABLE builtys ADD COLUMN {column} {sql_type}")

    # Backward-compatible migration for databases created by older builds.
    existing = {row[1] for row in con.execute("PRAGMA table_info(dos)")}
    if "gmdc_do_no" not in existing:
        con.execute("ALTER TABLE dos ADD COLUMN gmdc_do_no TEXT")
    con.commit()
    con.close()
    backup_database()


def lookup_rate(from_place, to_place, material):
    """Return latest matching freight rate (or 0 when nothing matches)."""
    if not (from_place or to_place or material):
        return 0.0
    con = db()
    row = con.execute(
        """SELECT rate_per_ton FROM freight_rates
           WHERE (from_place = ? OR ? = '')
             AND (to_place = ? OR ? = '')
             AND (material = ? OR ? = '')
           ORDER BY date(effective_date) DESC, id DESC LIMIT 1""",
        (from_place or "", from_place or "", to_place or "", to_place or "",
         material or "", material or ""),
    ).fetchone()
    con.close()
    return float(row["rate_per_ton"]) if row else 0.0


def restore_database(backup_path):
    """Validate a .db or .sql backup, save current data, then atomically restore it."""
    import os
    import tempfile
    source = Path(backup_path)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, staged_name = tempfile.mkstemp(prefix="radhe_restore_", suffix=".db", dir=str(DB_PATH.parent))
    os.close(fd)
    staged = Path(staged_name)
    try:
        if source.suffix.lower() == ".sql":
            target = sqlite3.connect(str(staged))
            try:
                target.executescript(source.read_text(encoding="utf-8"))
                target.commit()
            finally:
                target.close()
            _validate_database_file(staged)
        else:
            check = sqlite3.connect(str(source))
            try:
                result = check.execute("PRAGMA quick_check").fetchone()
                if not result or result[0] != "ok":
                    raise ValueError("Selected file is not a valid SQLite database backup.")
                tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not {"dos", "builtys", "bills"}.issubset(tables):
                    raise ValueError("This file is missing required DO, Builty and Bill tables.")
                target = sqlite3.connect(str(staged))
                try:
                    check.backup(target)
                    target.commit()
                finally:
                    target.close()
            finally:
                check.close()
            _validate_database_file(staged)
        if DB_PATH.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            safety = DB_PATH.with_name(DB_PATH.stem + "_before_restore_" + stamp + DB_PATH.suffix)
            _atomic_sqlite_copy(DB_PATH, safety)
        # Ensure the staged file has no open SQLite handles before Windows os.replace.
        os.replace(staged, DB_PATH)
        return DB_PATH
    finally:
        try:
            if staged.exists():
                staged.unlink()
        except OSError:
            pass
