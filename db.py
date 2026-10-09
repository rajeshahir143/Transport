"""Database layer for Radhe Radhe Developer app.
SQLite file is stored next to the executable so data stays on the local computer.
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "radhe_radhe.db"


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
            created_at TEXT DEFAULT (datetime('now','localtime'))
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
    # Backward-compatible migration for databases created by older builds.
    existing = {row[1] for row in con.execute("PRAGMA table_info(dos)")}
    if "gmdc_do_no" not in existing:
        con.execute("ALTER TABLE dos ADD COLUMN gmdc_do_no TEXT")
    con.commit()
    con.close()


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
