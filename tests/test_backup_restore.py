"""Isolated integration tests for SQLite backup and restore.

All test databases live in a temporary directory. No user/company database is touched.
"""
import importlib.util
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB_MODULE = REPO_ROOT / "db.py"


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rr_backup_restore_test_")
        self.root = Path(self.temp.name)
        # Import a copy so db.py's BASE resolves to the isolated temporary directory.
        isolated_module = self.root / "db.py"
        shutil.copy2(SOURCE_DB_MODULE, isolated_module)
        spec = importlib.util.spec_from_file_location("rr_test_db", isolated_module)
        self.dbmod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.dbmod)
        self.dbmod.BASE = self.root
        self.dbmod.COMPANIES_DIR = self.root / "Companies"
        self.dbmod.ACTIVE_COMPANY_FILE = self.root / "active_company.txt"
        self.dbmod.ACTIVE_COMPANY_FILE.write_text("Radhe Radhe Developer", encoding="utf-8")
        self.dbmod.DB_PATH = self.root / "radhe_radhe.db"
        self.dbmod.BACKUP_DIR = self.root / "Backup"
        self.dbmod.TEMP_BACKUP_DIR = self.root / "temp"
        self.dbmod.init_db()
        # init_db() opens/closes its own connection, but restore tests use only
        # isolated temp paths; keep all test data separated from real company DBs.
        self._insert_linked_sample("BEFORE")

    def tearDown(self):
        self.temp.cleanup()

    def _insert_linked_sample(self, suffix):
        con = self.dbmod.db()
        try:
            cur = con.execute(
                "INSERT INTO dos(do_no, customer_name, qty, remaining_qty) VALUES(?,?,?,?)",
                ("DO-" + suffix, "Test Customer", 10, 7),
            )
            do_id = cur.lastrowid
            cur = con.execute(
                "INSERT INTO builtys(builty_no, do_id, qty) VALUES(?,?,?)",
                ("BLT-" + suffix, do_id, 3),
            )
            builty_id = cur.lastrowid
            cur = con.execute(
                "INSERT INTO bills(bill_no, customer_name, total_qty, total) VALUES(?,?,?,?)",
                ("BILL-" + suffix, "Test Customer", 3, 300),
            )
            bill_id = cur.lastrowid
            con.execute(
                "INSERT INTO bill_builtys(bill_id, builty_id) VALUES(?,?)",
                (bill_id, builty_id),
            )
            con.commit()
        finally:
            con.close()

    def _assert_sample(self, suffix):
        con = sqlite3.connect(str(self.dbmod.DB_PATH))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM dos WHERE do_no=?", ("DO-" + suffix,)).fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM builtys WHERE builty_no=?", ("BLT-" + suffix,)).fetchone()[0], 1)
            self.assertEqual(con.execute(
                """SELECT COUNT(*) FROM bill_builtys bb
                   JOIN bills b ON b.id=bb.bill_id
                   JOIN builtys y ON y.id=bb.builty_id
                   JOIN dos d ON d.id=y.do_id
                   WHERE b.bill_no=? AND y.builty_no=? AND d.do_no=?""",
                ("BILL-" + suffix, "BLT-" + suffix, "DO-" + suffix),
            ).fetchone()[0], 1)
            self.assertEqual(con.execute("PRAGMA quick_check").fetchone()[0], "ok")
        finally:
            con.close()

    def test_db_backup_restore_preserves_records_and_links(self):
        backups = self.dbmod.backup_database()
        db_backup = next(p for p in backups if p.suffix == ".db" and "latest" not in p.name)
        self._insert_linked_sample("AFTER")
        self.dbmod.restore_database(db_backup)
        self._assert_sample("BEFORE")
        con = sqlite3.connect(str(self.dbmod.DB_PATH))
        try:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM dos WHERE do_no='DO-AFTER'").fetchone()[0], 0)
        finally:
            con.close()
        self.assertTrue(list(self.root.glob("*_before_restore_*.db")))

    def test_sql_backup_restore_preserves_records_and_links(self):
        backups = self.dbmod.backup_database()
        sql_backup = next(p for p in backups if p.suffix == ".sql" and "latest" not in p.name)
        self._insert_linked_sample("AFTER")
        self.dbmod.restore_database(sql_backup)
        self._assert_sample("BEFORE")
        self.assertTrue(list(self.root.glob("*_before_restore_*.db")))

    def test_corrupt_sql_restore_does_not_change_live_data(self):
        bad_sql = self.root / "corrupt.sql"
        bad_sql.write_text("CREATE TABLE broken(;", encoding="utf-8")
        with self.assertRaises(Exception):
            self.dbmod.restore_database(bad_sql)
        self._assert_sample("BEFORE")

    def test_invalid_sqlite_restore_does_not_change_live_data(self):
        bad_db = self.root / "corrupt.db"
        bad_db.write_bytes(b"not a sqlite database")
        with self.assertRaises(Exception):
            self.dbmod.restore_database(bad_db)
        self._assert_sample("BEFORE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
