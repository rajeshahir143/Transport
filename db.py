"""Database layer for Radhe Radhe Developer app.
SQLite file is stored next to the executable so data stays on the local computer.
"""
import sqlite3
import sys
from datetime import date
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


def backup_database():
    """Create a dated daily backup and refresh a temporary latest backup."""
    if not DB_PATH.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    daily = BACKUP_DIR / f"radhe_radhe_{date.today().isoformat()}.db"
    latest = TEMP_BACKUP_DIR / "radhe_radhe_latest_backup.db"
    source = sqlite3.connect(DB_PATH)
    try:
        for destination in (daily, latest):
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                target.commit()
            finally:
                target.close()
    finally:
        source.close()



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
    """Restore a SQLite backup after validating it and saving the current database."""
    import shutil
    source = Path(backup_path)
    if not source.is_file():
        raise FileNotFoundError(str(source))
    test = sqlite3.connect(str(source))
    try:
        result = test.execute("PRAGMA quick_check").fetchone()
        if not result or result[0] != "ok":
            raise ValueError("Selected file is not a valid SQLite database backup.")
    finally:
        test.close()
    if DB_PATH.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety = DB_PATH.with_name(DB_PATH.stem + "_before_restore_" + stamp + DB_PATH.suffix)
        shutil.copy2(DB_PATH, safety)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, DB_PATH)
    return DB_PATH
