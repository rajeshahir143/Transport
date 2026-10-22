"""Radhe Radhe Developer — Desktop app (Tkinter + SQLite).

Workflow:
    PDF -> DO (auto-fill, Save, Edit/Update)
    DO -> Builty (pending DO, remaining qty auto, SWASTIK-style PDF print)
    Builty -> Bill (multi-select same party, Material + GST)
    Freight Paid / Debit Note (Freight) / Freight Rate Master
Data is stored locally in radhe_radhe.db next to this script.
"""
import os
import csv
from datetime import datetime
import platform
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from db import db, init_db, lookup_rate, DB_PATH, list_companies, get_active_company, set_active_company, BASE
from pdf_parser import parse_pdf
from pdf_render import generate_builty_pdf, generate_bill_pdf

APP = "Radhe Radhe Developer — PDF DO / Builty / Bill"
BASE = Path(__file__).resolve().parent
EXPORT_DIR = BASE / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

# Firm details used on printed stationery. Edit here as needed.
FIRM = {
    "name": "RADHE RADHE DEVELOPER",
    "address": "Bhavnagar, Gujarat",
    "gstin": "",
    "phone": "",
}


def open_file(path):
    """Open a file with the OS default handler so the user can print it."""
    path = str(path)
    try:
        if platform.system() == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showwarning("Open file", f"Could not open the file automatically.\n{e}")


def _f(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry("1240x760")
        self.minsize(1080, 660)
        init_db()
        self._style()
        self._build()
        # init_db creates a startup backup; refresh latest copies hourly while app stays open.
        self.after(60 * 60 * 1000, self._automatic_backup_tick)

    # ---------- styling ----------
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground="#B22222")
        s.configure("Head.TLabel", font=("Segoe UI", 11, "bold"))
        s.configure("TNotebook.Tab", padding=(14, 7), font=("Segoe UI", 10, "bold"))
        s.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Radhe Radhe Developer", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="   PDF → DO → Builty → Bill",
                  font=("Segoe UI", 11)).pack(side="left")
        ttk.Label(top, text="Company:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(24, 4))
        self.company_var = tk.StringVar(value=get_active_company())
        self.company_combo = ttk.Combobox(top, textvariable=self.company_var, values=list_companies(), width=22, state="readonly")
        self.company_combo.pack(side="left")
        self.company_combo.bind("<<ComboboxSelected>>", self.switch_company)
        ttk.Button(top, text="＋ Add Company", command=self.add_company).pack(side="left", padx=5)
        ttk.Label(top, text=f"DB: {DB_PATH.name}",
                  font=("Segoe UI", 9), foreground="#666").pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=5)
        # Keep the main workspace limited to the requested daily workflow tabs.
        self.do_tab(nb)
        self.builty_tab(nb)
        self.bill_tab(nb)
        self.freight_paid_tab(nb)
        self.export_tab(nb)
        self.dashboard_tab(nb)
        self.swastik_import_tab(nb)

    # ===================== DASHBOARD =====================
    def dashboard_tab(self, nb):
        from datetime import date, timedelta
        f = ttk.Frame(nb, padding=14)
        nb.add(f, text="Dashboard")
        ttk.Label(f, text="Company Dashboard", style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(f, text="Summary for the currently selected company database.").pack(anchor="w")

        filters = ttk.Frame(f)
        filters.pack(fill="x", pady=(10, 4))
        ttk.Label(filters, text="Period:").pack(side="left", padx=(0, 6))
        self.dashboard_period = tk.StringVar(value="Today")
        for title in ("Today", "Last 7 Days", "Manual Date"):
            ttk.Radiobutton(
                filters, text=title, value=title, variable=self.dashboard_period,
                command=self._dashboard_period_changed
            ).pack(side="left", padx=5)
        self.dashboard_start_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        self.dashboard_end_var = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        ttk.Label(filters, text="From (DD/MM/YYYY):").pack(side="left", padx=(14, 4))
        self.dashboard_start_entry = ttk.Entry(filters, textvariable=self.dashboard_start_var, width=12)
        self.dashboard_start_entry.pack(side="left", padx=3)
        ttk.Label(filters, text="To:").pack(side="left", padx=(5, 2))
        self.dashboard_end_entry = ttk.Entry(filters, textvariable=self.dashboard_end_var, width=12)
        self.dashboard_end_entry.pack(side="left", padx=3)
        ttk.Button(filters, text="Apply Dates", command=self._dashboard_apply_manual).pack(side="left", padx=6)

        self.dashboard_range_label = ttk.Label(f, text="")
        self.dashboard_range_label.pack(anchor="w", pady=(2, 4))
        cards = ttk.Frame(f)
        cards.pack(fill="x", pady=10)
        self.dashboard_values = {}
        metrics = [
            ("do_count", "DOs in Period"), ("pending_ton", "Pending TON"),
            ("builty_count", "Builty in Period"), ("unbilled_count", "Unbilled Builty"),
            ("bill_count", "Bills in Period"), ("bill_total", "Bill Total (Rs.)"),
            ("commission", "Commission (Rs.)"), ("driver_payable", "Driver Payable (Rs.)"),
        ]
        for i, (key, label) in enumerate(metrics):
            box = ttk.LabelFrame(cards, text=label, padding=12)
            box.grid(row=i//4, column=i%4, sticky="nsew", padx=5, pady=5)
            val = ttk.Label(box, text="—", font=("Segoe UI", 16, "bold"))
            val.pack(anchor="w")
            self.dashboard_values[key] = val
            cards.columnconfigure(i%4, weight=1)
        ttk.Button(f, text="Refresh Dashboard", command=self.refresh_dashboard).pack(anchor="w", pady=8)
        self._dashboard_period_changed()

    def _dashboard_period_changed(self):
        from datetime import date, timedelta
        period = self.dashboard_period.get()
        today = date.today()
        if period == "Today":
            start = end = today
        elif period == "Last 7 Days":
            start, end = today - timedelta(days=6), today
        else:
            return
        self.dashboard_start_var.set(start.strftime("%d/%m/%Y"))
        self.dashboard_end_var.set(end.strftime("%d/%m/%Y"))
        self.refresh_dashboard()

    def _dashboard_apply_manual(self):
        from datetime import datetime
        try:
            start = datetime.strptime(self.dashboard_start_var.get().strip(), "%d/%m/%Y").date()
            end = datetime.strptime(self.dashboard_end_var.get().strip(), "%d/%m/%Y").date()
            if end < start:
                raise ValueError("To date must be on or after From date.")
            self.dashboard_period.set("Manual Date")
            self.refresh_dashboard()
        except ValueError as exc:
            messagebox.showerror("Dashboard Date", "Enter valid dates as DD/MM/YYYY and ensure To is not before From.\\n" + str(exc))

    def refresh_dashboard(self):
        from datetime import datetime
        try:
            start = datetime.strptime(self.dashboard_start_var.get().strip(), "%d/%m/%Y").date().isoformat()
            end = datetime.strptime(self.dashboard_end_var.get().strip(), "%d/%m/%Y").date().isoformat()
            # Imported DBF dates may be ISO (YYYY-MM-DD) or Indian (DD/MM/YYYY).
            def date_expr(column):
                return (f"(CASE WHEN length({column})>=10 AND substr({column},3,1)='/' "
                        f"THEN substr({column},7,4)||'-'||substr({column},4,2)||'-'||substr({column},1,2) "
                        f"ELSE substr({column},1,10) END)")
            with db() as con:
                do_date = date_expr("do_date")
                builty_date = date_expr("date")
                bill_date = date_expr("bill_date")
                values = {
                    "do_count": con.execute(f"SELECT COUNT(*) FROM dos WHERE {do_date} BETWEEN ? AND ?", (start, end)).fetchone()[0],
                    "pending_ton": con.execute("SELECT COALESCE(SUM(remaining_qty),0) FROM dos").fetchone()[0],
                    "builty_count": con.execute(f"SELECT COUNT(*) FROM builtys WHERE {builty_date} BETWEEN ? AND ?", (start, end)).fetchone()[0],
                    "unbilled_count": con.execute(f"SELECT COUNT(*) FROM builtys WHERE billed=0 AND {builty_date} BETWEEN ? AND ?", (start, end)).fetchone()[0],
                    "bill_count": con.execute(f"SELECT COUNT(*) FROM bills WHERE {bill_date} BETWEEN ? AND ?", (start, end)).fetchone()[0],
                    "bill_total": con.execute(f"SELECT COALESCE(SUM(total),0) FROM bills WHERE {bill_date} BETWEEN ? AND ?", (start, end)).fetchone()[0],
                    "commission": con.execute(f"SELECT COALESCE(SUM(commission),0) FROM builtys WHERE {builty_date} BETWEEN ? AND ?", (start, end)).fetchone()[0],
                    "driver_payable": con.execute(f"SELECT COALESCE(SUM(driver_payable),0) FROM builtys WHERE {builty_date} BETWEEN ? AND ?", (start, end)).fetchone()[0],
                }
            for key, value in values.items():
                label = self.dashboard_values.get(key)
                if label:
                    label.configure(text=f"{value:,.2f}" if key in ("pending_ton","bill_total","commission","driver_payable") else f"{value:,}")
            self.dashboard_range_label.configure(text=f"Showing: {start} to {end} | Pending TON is current outstanding balance.")
        except Exception as exc:
            messagebox.showerror("Dashboard", f"Could not refresh dashboard:\\n{exc}")

    # ===================== MULTI-COMPANY / IMPORT =====================
    def add_company(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Add Company", "Enter company name:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in list_companies():
            messagebox.showwarning("Add Company", "This company already exists.")
            return
        self.company_var.set(name)
        self.company_combo.configure(values=list_companies() + [name])
        set_active_company(name)
        init_db()
        self.company_combo.configure(values=list_companies())
        messagebox.showinfo("Company Created", f"Company '{name}' database is ready.")
        self._restart_app()

    def switch_company(self, _event=None):
        name = self.company_var.get()
        if name == get_active_company():
            return
        set_active_company(name)
        init_db()
        self._restart_app()

    def _restart_app(self):
        # Rebuild widgets so every list reads from the newly selected company's database.
        for child in self.winfo_children():
            child.destroy()
        self._build()

    def swastik_import_tab(self, nb):
        f = ttk.Frame(nb, padding=14)
        nb.add(f, text="Import")
        ttk.Label(f, text="Import legacy company data",
                  style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(f, text="Select the old company data folder and confirm. DO, Builty and Bill records are the intended import scope.",
                  wraplength=900).pack(anchor="w", pady=4)
        ttk.Button(f, text="Import", command=self.import_swastik_zip).pack(anchor="w", pady=10)
        backup_row = ttk.Frame(f)
        backup_row.pack(anchor="w", pady=8)
        ttk.Button(backup_row, text="Restore Database Backup (.db / .sql)", command=self.restore_backup).pack(side="left", padx=(0, 8))
        ttk.Button(backup_row, text="Create Backup Now", command=self.create_backup_now).pack(side="left")
        self.import_status = ttk.Label(f, text="Automatic daily .db and .sql backups are saved beside the EXE; latest copies are saved under temp\\<company>.", wraplength=1000)
        self.import_status.pack(anchor="w", pady=8)

    def create_backup_now(self):
        try:
            from db import backup_database
            backup_database()
            messagebox.showinfo("Backup", "Backup created in the active company's Backup and temp folders.")
        except Exception as exc:
            messagebox.showerror("Backup", str(exc))

    def _automatic_backup_tick(self):
        """Refresh latest copies periodically and create a daily snapshot after date rollover."""
        try:
            from db import backup_database
            backup_database()
        except Exception as exc:
            print(f"Automatic backup failed: {exc}", file=sys.stderr)
        finally:
            if self.winfo_exists():
                self.after(60 * 60 * 1000, self._automatic_backup_tick)

    def restore_backup(self):
        from db import restore_database
        path = filedialog.askopenfilename(title="Select SQLite backup", filetypes=[("Database backup", "*.db *.sql"), ("SQLite database", "*.db"), ("SQL dump", "*.sql"), ("All files", "*.*")])
        if not path:
            return
        if not messagebox.askyesno("Restore Backup", "Restore this backup into the currently selected company? The current database will be copied to a safety file first."):
            return
        try:
            restore_database(path)
            init_db()
            messagebox.showinfo("Restore Backup", "Backup restored. The app will refresh now.")
            self._restart_app()
        except Exception as exc:
            messagebox.showerror("Restore Backup", f"Restore failed; current data was not intentionally overwritten.\n{exc}")

    def import_swastik_zip(self):
        """Preview and import SWASTIK E/K/N/R/S DBF records into isolated company DBs."""
        from tkinter import messagebox, filedialog
        from swastik_import import discover_companies, inspect_company, import_company
        import db as db_module

        folder = filedialog.askdirectory(
            title="Select extracted SWASTIK folder (contains DO_SOFT)",
            mustexist=True,
        )
        if not folder:
            return

        try:
            companies = discover_companies(folder)
            preview = []
            for code, data_dir in companies.items():
                counts = inspect_company(data_dir)
                preview.append(
                    f"{code}: DO {counts['do1']:,}, Schedules {counts['do2']:,}, "
                    f"Builty {counts['builty']:,}, Bills {counts['bill1']:,}, "
                    f"Bill details {counts['bill2']:,}"
                )
            preview_text = "\\n".join(preview)
            self.import_status.configure(
                text="SWASTIK source preview (active, non-deleted DBF records):\\n" + preview_text
            )
            if not messagebox.askyesno(
                "Confirm Import",
                "The following company databases will be updated. Each database will be backed up first. "
                "Existing records will not be deleted.\\n\\n" + preview_text +
                "\\n\\nProceed with import?",
                parent=self,
            ):
                return

            previous_company = db_module.get_active_company()
            reports = []
            try:
                for code, data_dir in companies.items():
                    # E/K/N/R/S each get a separate SQLite database.
                    db_module.set_active_company(code)
                    db_module.init_db()
                    db_module.backup_database()
                    with db_module.db() as con:
                        result = import_company(data_dir, con)
                        actual = {
                            "DO": con.execute("SELECT COUNT(*) FROM dos").fetchone()[0],
                            "Builty": con.execute("SELECT COUNT(*) FROM builtys").fetchone()[0],
                            "Bill": con.execute("SELECT COUNT(*) FROM bills").fetchone()[0],
                            "Broken Builty→DO links": con.execute(
                                "SELECT COUNT(*) FROM builtys b LEFT JOIN dos d ON d.id=b.do_id WHERE d.id IS NULL"
                            ).fetchone()[0],
                            "Broken Bill→Builty links": con.execute(
                                "SELECT COUNT(*) FROM bill_builtys bb LEFT JOIN bills b ON b.id=bb.bill_id "
                                "LEFT JOIN builtys y ON y.id=bb.builty_id WHERE b.id IS NULL OR y.id IS NULL"
                            ).fetchone()[0],
                        }
                    reports.append(
                        f"{code}: added DO {result['do_inserted']}, Builty {result['builty_inserted']}, "
                        f"Bill {result['bill_inserted']}; existing DO {result['do_existing']}, "
                        f"Builty {result['builty_existing']}; schedules {result['schedules_inserted']}; "
                        f"unlinked Builty skipped {result['orphan_builty_skipped']}."
                    )
                    reports.append(
                        f"   Database totals: DO {actual['DO']}, Builty {actual['Builty']}, "
                        f"Bill {actual['Bill']}; broken links: Builty→DO {actual['Broken Builty→DO links']}, "
                        f"Bill→Builty {actual['Broken Bill→Builty links']}."
                    )
            finally:
                db_module.set_active_company(previous_company)
                db_module.init_db()
            report_text = "\\n".join(reports)
            self.import_status.configure(text="Import finished. Check per-company totals below.\\n" + report_text)
            messagebox.showinfo("Import Results", report_text, parent=self)
            self._restart_app()
        except Exception as exc:
            messagebox.showerror(
                "Import failed",
                "Import stopped because an error occurred. Review the message before retrying; "
                "company databases are isolated and the pre-import backup is retained.\\n\\n" + str(exc),
                parent=self,
            )

    # ===================== DO TAB =====================
    def do_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="1 · DO Entry")
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Button(bar, text="Upload PDF → Create DO", command=self.upload_pdf).pack(side="left")
        ttk.Button(bar, text="Edit / Update Selected", command=self.edit_do).pack(side="left", padx=6)
        ttk.Button(bar, text="Delete Selected", command=self.delete_do).pack(side="left")
        self.show_all_dos = False
        ttk.Button(bar, text="Pending DO", command=self.show_pending_dos).pack(side="left", padx=(10, 3))
        ttk.Button(bar, text="All DO", command=self.show_all_do).pack(side="left", padx=3)
        ttk.Button(bar, text="Refresh", command=self.refresh_do).pack(side="right")

        cols = ("id", "do_no", "date", "customer", "material", "qty", "remaining", "transporter", "to_place")
        heads = ["ID", "DO No", "Date", "Customer", "Material", "DO Qty", "Remaining", "Transporter", "To"]
        widths = [50, 110, 90, 220, 180, 85, 95, 160, 140]
        self.dot = ttk.Treeview(f, columns=cols, show="headings", height=22)
        for c, h, w in zip(cols, heads, widths):
            self.dot.heading(c, text=h)
            self.dot.column(c, width=w, anchor="w" if c in ("customer", "material", "transporter", "to_place") else "center")
        self.dot.pack(fill="both", expand=True, pady=10)
        self.dot.bind("<Double-1>", lambda _e: self.edit_do())
        self.refresh_do()

    def show_pending_dos(self):
        self.show_all_dos = False
        self.refresh_do()

    def show_all_do(self):
        self.show_all_dos = True
        self.refresh_do()

    def refresh_do(self):
        if not hasattr(self, "dot"):
            return
        for x in self.dot.get_children():
            self.dot.delete(x)
        con = db()
        try:
            if getattr(self, "show_all_dos", False):
                rows = con.execute("SELECT * FROM dos ORDER BY id DESC").fetchall()
            else:
                rows = con.execute("SELECT * FROM dos WHERE COALESCE(remaining_qty, 0) > 0.000001 ORDER BY id DESC").fetchall()
            for r in rows:
                self.dot.insert("", "end", values=(
                    r["id"], r["do_no"], r["do_date"], r["customer_name"], r["material"],
                    "{:.3f}".format(r["qty"]), "{:.3f}".format(r["remaining_qty"]), r["transporter_name"],
                    r["to_place"] or "",
                ))
        finally:
            con.close()
    def upload_pdf(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not p:
            return
        try:
            d = parse_pdf(p)
        except Exception as e:
            messagebox.showerror("PDF Import", str(e))
            return
        if not d.get("gmdc_do_no"):
            messagebox.showerror("PDF Import", "GMDC DO Number could not be detected.")
            return
        # Open editable form pre-filled from PDF
        self._do_form(data=d, source_pdf=p)

    def edit_do(self):
        sel = self.dot.selection()
        if not sel:
            messagebox.showwarning("Edit DO", "Select a DO row first.")
            return
        do_id = int(self.dot.item(sel[0])["values"][0])
        con = db()
        row = con.execute("SELECT * FROM dos WHERE id=?", (do_id,)).fetchone()
        schedules = con.execute("SELECT schedule_date,qty,uom,unit_price,extended_price FROM do_schedules WHERE do_id=? ORDER BY schedule_date", (do_id,)).fetchall()
        con.close()
        if row:
            payload = dict(row)
            payload["schedule_rows"] = [dict(s) for s in schedules]
            self._do_form(data=payload, existing_id=do_id)

    def delete_do(self):
        sel = self.dot.selection()
        if not sel:
            return
        do_id = int(self.dot.item(sel[0])["values"][0])
        if not messagebox.askyesno("Delete DO", "Delete this DO? Related builtys will be blocked if any exist."):
            return
        con = db()
        used = con.execute("SELECT COUNT(*) c FROM builtys WHERE do_id=?", (do_id,)).fetchone()["c"]
        if used:
            con.close()
            messagebox.showerror("Delete DO", "This DO has builtys. Delete those first.")
            return
        con.execute("DELETE FROM dos WHERE id=?", (do_id,))
        con.commit()
        con.close()
        self.refresh_do()
        self.refresh_builty()

    def _do_form(self, data, existing_id=None, source_pdf=None):
        w = tk.Toplevel(self)
        w.title("Edit DO" if existing_id else "Create DO from PDF")
        w.geometry("640x620")
        w.transient(self)
        fields = [
            ("gmdc_do_no", "GMDC DO No"), ("do_no", "DO No"), ("do_date", "DO Date"),
            ("customer_no", "Customer No"), ("customer_name", "Customer Name"),
            ("customer_gstin", "Customer GSTIN"), ("order_type", "Order Type"),
            ("bill_to", "Bill To"), ("ship_to", "Ship To"),
            ("state", "State"), ("hsn", "HSN"),
            ("material", "Material"), ("schedule_date", "Schedule Date"),
            ("qty", "Qty"), ("uom", "UOM"),
            ("unit_price", "Unit Price"), ("extended_price", "Extended Price"),
            ("transporter_code", "Transporter Code"), ("transporter_name", "Transporter Name"),
            ("order_total", "Order Total"),
            ("from_place", "From"), ("to_place", "To"),
        ]
        vars_ = {}
        frm = ttk.Frame(w, padding=10)
        frm.pack(fill="both", expand=True)
        for i, (k, lab) in enumerate(fields):
            ttk.Label(frm, text=lab).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=5, pady=3)
            value = data.get(k) or ""
            if k == "schedule_date" and data.get("schedule_rows"):
                value = data["schedule_rows"][0].get("schedule_date", value)
            v = tk.StringVar(value=str(value))
            vars_[k] = v
            if k == "schedule_date":
                dates = [r.get("schedule_date", "") for r in (data.get("schedule_rows") or []) if r.get("schedule_date")]
                widget = ttk.Combobox(frm, textvariable=v, values=dates, width=30, state="readonly" if dates else "normal")
            else:
                widget = ttk.Entry(frm, textvariable=v, width=32)
            widget.grid(row=i // 2, column=(i % 2) * 2 + 1, padx=5, pady=3)

        def save():
            vals = {k: vars_[k].get().strip() for k, _ in fields}
            qty = _f(vals["qty"])
            try:
                con = db()
                schedule_rows = data.get("schedule_rows") or []
                if existing_id:
                    # keep remaining_qty consistent: adjust by delta if qty changed
                    prev = con.execute("SELECT qty, remaining_qty FROM dos WHERE id=?",
                                       (existing_id,)).fetchone()
                    used = _f(prev["qty"]) - _f(prev["remaining_qty"])
                    new_remaining = max(qty - used, 0)
                    con.execute(
                        """UPDATE dos SET do_no=?, gmdc_do_no=?, do_date=?, customer_no=?, customer_name=?,
                           customer_gstin=?, order_type=?, bill_to=?, ship_to=?, state=?, hsn=?,
                           material=?, schedule_date=?, qty=?, uom=?, unit_price=?, extended_price=?,
                           transporter_code=?, transporter_name=?, order_total=?,
                           from_place=?, to_place=?, to_ma_dist=?, remaining_qty=?
                           WHERE id=?""",
                        (vals["do_no"], vals["gmdc_do_no"], vals["do_date"], vals["customer_no"], vals["customer_name"],
                         vals["customer_gstin"], vals["order_type"], vals["bill_to"], vals["ship_to"],
                         vals["state"], vals["hsn"], vals["material"], vals["schedule_date"],
                         qty, vals["uom"], _f(vals["unit_price"]), _f(vals["extended_price"]),
                         vals["transporter_code"], vals["transporter_name"], _f(vals["order_total"]),
                         vals["from_place"], vals["to_place"], vals["to_place"], new_remaining, existing_id),
                    )
                else:
                    do_columns = (
                        "do_no,gmdc_do_no,do_date,customer_no,customer_name,customer_gstin,"
                        "order_type,bill_to,ship_to,state,hsn,material,schedule_date,qty,uom,"
                        "unit_price,extended_price,transporter_code,transporter_name,order_total,"
                        "from_place,to_place,to_ma_dist,remaining_qty,source_pdf"
                    )
                    do_values = (
                        vals["do_no"], vals["gmdc_do_no"], vals["do_date"], vals["customer_no"], vals["customer_name"],
                        vals["customer_gstin"], vals["order_type"], vals["bill_to"], vals["ship_to"],
                        vals["state"], vals["hsn"], vals["material"], vals["schedule_date"],
                        qty, vals["uom"], _f(vals["unit_price"]), _f(vals["extended_price"]),
                        vals["transporter_code"], vals["transporter_name"], _f(vals["order_total"]),
                        vals["from_place"], vals["to_place"], vals["to_place"], qty, source_pdf or "",
                    )
                    # Build placeholders from the exact value count so the SQL cannot drift out of sync.
                    placeholders = ",".join("?" for _ in do_values)
                    con.execute(
                        f"INSERT INTO dos({do_columns}) VALUES({placeholders})",
                        do_values,
                    )
                if schedule_rows:
                    if existing_id:
                        con.execute("DELETE FROM do_schedules WHERE do_id=?", (existing_id,))
                        schedule_do_id = existing_id
                    else:
                        schedule_do_id = con.execute("SELECT id FROM dos WHERE gmdc_do_no=? ORDER BY id DESC LIMIT 1",
                                                     (vals["gmdc_do_no"],)).fetchone()["id"]
                    for item in schedule_rows:
                        date_text = str(item.get("schedule_date") or "").strip()
                        if not date_text:
                            continue
                        qty_row = _f(item.get("qty"))
                        con.execute(
                            """INSERT INTO do_schedules(do_id,schedule_date,qty,remaining_qty,uom,unit_price,extended_price)
                               VALUES(?,?,?,?,?,?,?) ON CONFLICT(do_id,schedule_date) DO UPDATE SET
                               qty=excluded.qty, remaining_qty=MIN(do_schedules.remaining_qty,excluded.qty),
                               uom=excluded.uom, unit_price=excluded.unit_price, extended_price=excluded.extended_price""",
                            (schedule_do_id, date_text, qty_row, qty_row, item.get("uom") or vals["uom"],
                             _f(item.get("unit_price")), _f(item.get("extended_price"))),
                        )
                con.commit()
                con.close()
                self.refresh_do()
                self.refresh_builty()
                w.destroy()
            except Exception as e:
                messagebox.showerror("Save DO", str(e))

        btns = ttk.Frame(w, padding=(10, 0, 10, 10))
        btns.pack(fill="x")
        ttk.Button(btns, text="Save", command=save).pack(side="right")
        ttk.Button(btns, text="Cancel", command=w.destroy).pack(side="right", padx=6)

    # ===================== BUILTY TAB =====================
    def builty_tab(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="2 · Builty Entry")
        # Two-column layout: SWASTIK-style Builty form on the left, pending DOs on the right.
        split = ttk.Panedwindow(f, orient="horizontal")
        split.pack(fill="both", expand=True)
        left = ttk.Frame(split, padding=(2, 2, 8, 2))
        right = ttk.Frame(split, padding=(6, 2, 2, 2))
        split.add(left, weight=3)
        split.add(right, weight=2)

        title = ttk.Frame(left)
        title.pack(fill="x")
        ttk.Label(title, text="Builty Entry", style="Title.TLabel").pack(side="left")

        form = ttk.LabelFrame(left, text="Builty Details", padding=8)
        form.pack(fill="x", pady=(6, 5))
        self.b_vars = {k: tk.StringVar() for k in (
            "builty_no", "truck_no", "date", "qty", "do_no", "from_place", "to_place",
            "consignee", "driver_name", "mobile_no", "owner_name", "address",
            "challan_no", "quota_date", "freight_rate", "freight_amount", "ewaybill",
            "pay_status", "cgst_rate", "sgst_rate", "remarks", "sale_party", "supply_party",
            "center_name", "quota_select", "vehicle_no", "sale_rate", "sale_amount",
            "despatch_weight", "receipt_weight", "freight_type", "commission",
            "receipt_date", "driver_mobile", "voucher_remarks", "blt_print", "driver_payable",
        )}
        self.b_vars["date"].set(__import__("datetime").date.today().strftime("%d/%m/%Y"))
        self.b_vars["pay_status"].set("To Be Billed")
        self.b_vars["commission"].set("0")
        self.b_vars["cgst_rate"].set("0")
        self.b_vars["sgst_rate"].set("0")

        pending_box = ttk.LabelFrame(right, text="Pending DO — select a DO to auto-fill details", padding=5)
        pending_box.pack(fill="x", expand=False, pady=4)
        cols = ("id", "do_no", "customer", "material", "remaining")
        self.pd = ttk.Treeview(pending_box, columns=cols, show="headings", height=5, selectmode="browse")
        for c, h, w in zip(cols, ("ID", "DO No", "Party Name", "Item Name", "Pending TON"), (42, 105, 185, 130, 90)):
            self.pd.heading(c, text=h)
            self.pd.column(c, width=w, anchor="w" if c in ("customer", "material") else "center")
        self.pd.pack(fill="both", expand=True)
        self.pd.bind("<<TreeviewSelect>>", self._on_pending_do_select)

        do_box = ttk.LabelFrame(right, text="DO Details (Auto from DO)", padding=7)
        do_box.pack(fill="x", pady=4)
        self.b_do_summary = tk.StringVar(value="Select a pending DO to auto-fill party, GSTIN, material and available quantity.")
        ttk.Label(do_box, textvariable=self.b_do_summary, justify="left", wraplength=450).pack(anchor="w")

        transport = ttk.LabelFrame(left, text="Transport Details", padding=7)
        transport.pack(fill="x", pady=4)
        fields = [
            ("Builty No.", "builty_no"), ("Date", "date"), ("DO No.", "do_no"),
            ("Vehicle No.", "truck_no"), ("Driver Name", "driver_name"), ("Driver Mobile No.", "driver_mobile"),
            ("Truck Owner Name", "owner_name"), ("Address", "address"), ("Challan No.", "challan_no"),
            ("Select Quota", "quota_select"), ("Despatch Weight", "despatch_weight"),
            ("Receipt Weight", "receipt_weight"), ("Actual Weight (TON)", "qty"),
            ("Freight Rate", "freight_rate"), ("Freight (Rs.)", "freight_amount"),
            ("Sale Rate", "sale_rate"), ("Sale Amount", "sale_amount"), ("Commission Rs.", "commission"),
            ("Receipt Date", "receipt_date"), ("Driver Payable (Rs.)", "driver_payable"),
        ]
        for i, (label, key) in enumerate(fields):
            r, col = divmod(i, 3)
            ttk.Label(transport, text=label).grid(row=r, column=col*2, padx=4, pady=3, sticky="w")
            if key == "quota_select":
                ent = ttk.Combobox(transport, textvariable=self.b_vars[key], width=15, state="readonly")
                self._quota_combo = ent
                ent.bind("<<ComboboxSelected>>", self._on_quota_selected)
            else:
                ent = ttk.Entry(transport, textvariable=self.b_vars[key], width=17)
            ent.grid(row=r, column=col*2+1, padx=4, pady=3, sticky="ew")
            if key in ("qty", "freight_rate", "commission"):
                self.b_vars[key].trace_add("write", lambda *_: self._recalc_freight())
            self.b_vars[key].trace_add("write", lambda *_: self.update_builty_preview())
        for col in range(6):
            transport.columnconfigure(col, weight=1)

        other = ttk.LabelFrame(left, text="Other Details / Accounts", padding=7)
        other.pack(fill="x", pady=4)
        for i, (label, key) in enumerate([("CGST %", "cgst_rate"), ("SGST %", "sgst_rate"), ("To Pay / Paid", "pay_status")]):
            ttk.Label(other, text=label).grid(row=0, column=i*2, padx=4, pady=3, sticky="w")
            if key == "pay_status":
                ttk.Combobox(other, textvariable=self.b_vars[key], values=("To Be Billed", "Paid", "To Pay"), width=15, state="readonly").grid(row=0, column=i*2+1, padx=4, pady=3)
            else:
                ttk.Entry(other, textvariable=self.b_vars[key], width=10).grid(row=0, column=i*2+1, padx=4, pady=3)
        ttk.Label(other, text="Sale Party Name").grid(row=1, column=0, padx=4, pady=3, sticky="w")
        ttk.Entry(other, textvariable=self.b_vars["sale_party"], width=25).grid(row=1, column=1, padx=4, pady=3, sticky="ew")
        ttk.Label(other, text="Supply Party - Mill").grid(row=1, column=2, padx=4, pady=3, sticky="w")
        ttk.Entry(other, textvariable=self.b_vars["supply_party"], width=25).grid(row=1, column=3, columnspan=3, padx=4, pady=3, sticky="ew")
        ttk.Label(other, text="Center Name").grid(row=2, column=0, padx=4, pady=3, sticky="w")
        ttk.Entry(other, textvariable=self.b_vars["center_name"], width=25).grid(row=2, column=1, padx=4, pady=3, sticky="ew")
        ttk.Label(other, text="Freight Type").grid(row=2, column=2, padx=4, pady=3, sticky="w")
        ttk.Combobox(other, textvariable=self.b_vars["freight_type"], values=("To Be Billed", "Paid", "To Pay"), width=20, state="readonly").grid(row=2, column=3, padx=4, pady=3, sticky="ew")
        ttk.Label(other, text="Voucher Remarks").grid(row=3, column=0, padx=4, pady=3, sticky="w")
        ttk.Entry(other, textvariable=self.b_vars["voucher_remarks"]).grid(row=3, column=1, columnspan=5, padx=4, pady=3, sticky="ew")
        ttk.Label(other, text="Shortage / Remarks").grid(row=4, column=0, padx=4, pady=3, sticky="w")
        ttk.Entry(other, textvariable=self.b_vars["remarks"]).grid(row=4, column=1, columnspan=5, padx=4, pady=3, sticky="ew")

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=5)
        ttk.Button(buttons, text="＋ Add", command=self.open_new_builty_window).pack(side="left", padx=2)
        ttk.Button(buttons, text="Edit Selected", command=self.load_selected_builty).pack(side="left", padx=2)
        ttk.Button(buttons, text="◀ Previous", command=lambda: self.navigate_builty(-1)).pack(side="left", padx=2)
        ttk.Button(buttons, text="Next ▶", command=lambda: self.navigate_builty(1)).pack(side="left", padx=2)
        ttk.Button(buttons, text="💾 Save Builty", command=self.create_builty).pack(side="left", padx=2)
        ttk.Button(buttons, text="Print Preview", command=self.preview_selected_builty).pack(side="left", padx=2)
        ttk.Button(buttons, text="Print / Open PDF", command=self.reprint_builty).pack(side="left", padx=2)
        ttk.Button(buttons, text="Cancel", command=self.clear_builty_form).pack(side="left", padx=2)
        self.manual_builty = tk.BooleanVar(value=False)
        ttk.Checkbutton(buttons, text="Manual details", variable=self.manual_builty,
                        command=self.toggle_manual_builty).pack(side="right", padx=3)

        saved_head = ttk.Frame(right)
        saved_head.pack(fill="x", pady=(6, 2))
        ttk.Label(saved_head, text="Saved Builty List", style="Head.TLabel").pack(side="left")
        self.show_all_builtys = False
        ttk.Button(saved_head, text="All Builty", command=self.show_all_builty_records).pack(side="right")
        ttk.Button(saved_head, text="Selected DO Builty", command=self.show_selected_do_builtys).pack(side="right", padx=4)
        bcols = ("id", "no", "do", "party", "date", "truck", "qty", "freight", "status")
        self.bt = ttk.Treeview(right, columns=bcols, show="headings", height=5)
        for c, h, w in zip(bcols, ("ID", "Builty No.", "DO No.", "Party Name", "Date", "Truck No.", "Weight", "Amount", "Status"),
                           (35, 75, 90, 150, 82, 95, 72, 78, 72)):
            self.bt.heading(c, text=h)
            self.bt.column(c, width=w, anchor="center")
        self.bt.pack(fill="both", expand=True)
        self.bt.bind("<Double-1>", lambda _e: self.reprint_builty())

        # Keep preview/print actions on the form; the right column is reserved for pending and saved DO/Builty lists.
        preview_head = ttk.Frame(left)
        preview_head.pack(fill="x", pady=(3, 0))
        ttk.Button(preview_head, text="Print Preview", command=self.preview_selected_builty).pack(side="left", padx=2)
        ttk.Button(preview_head, text="Print / Open PDF", command=self.reprint_builty).pack(side="left", padx=2)
        ttk.Button(preview_head, text="Export PDF", command=self.reprint_builty).pack(side="left", padx=2)
        self.b_preview = tk.Text(left, wrap="word", font=("Courier New", 9), height=4, background="white",
                                 relief="solid", borderwidth=1, padx=8, pady=6)
        self.b_preview.pack(fill="x", pady=(3, 0))
        self.update_builty_preview()
        self.refresh_builty()

    def delete_selected_builty(self):
        """Delete a selected unbilled Builty and restore its quantity to the linked DO."""
        sel = self.bt.selection() if hasattr(self, "bt") else ()
        if not sel:
            messagebox.showwarning("Delete Builty", "Select a saved Builty from the list first.")
            return
        values = self.bt.item(sel[0]).get("values", [])
        if not values:
            messagebox.showwarning("Delete Builty", "Selected Builty record could not be read.")
            return
        builty_id = int(values[0])
        con = db()
        try:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM builtys WHERE id=?", (builty_id,)).fetchone()
            if not row:
                con.rollback()
                messagebox.showwarning("Delete Builty", "This Builty no longer exists.")
                return
            if row["billed"]:
                con.rollback()
                messagebox.showerror("Delete Builty", "This Builty is already linked to a Bill. Remove it from the Bill first.")
                return
            if row["freight_paid"]:
                con.rollback()
                messagebox.showerror("Delete Builty", "Freight payment is recorded for this Builty. Reverse the payment before deleting.")
                return
            if not messagebox.askyesno(
                "Confirm Delete",
                f'Delete Builty No. {row["builty_no"]}? The quantity will be returned to its Pending DO.'
            ):
                con.rollback()
                return
            quota_date = row["quota_date"] if "quota_date" in row.keys() else ""
            if quota_date:
                con.execute(
                    "UPDATE do_schedules SET remaining_qty=MIN(qty, COALESCE(remaining_qty,0)+?) WHERE do_id=? AND schedule_date=?",
                    (float(row["qty"] or 0), row["do_id"], quota_date)
                )
            con.execute(
                "UPDATE dos SET remaining_qty=MIN(qty, COALESCE(remaining_qty,0)+?) WHERE id=?",
                (float(row["qty"] or 0), row["do_id"])
            )
            con.execute("DELETE FROM builtys WHERE id=?", (builty_id,))
            con.commit()
        except Exception as exc:
            con.rollback()
            messagebox.showerror("Delete Builty", f"Could not delete Builty: {exc}")
            return
        finally:
            con.close()
        self.clear_builty_form()
        self.refresh_builty()
        messagebox.showinfo("Delete Builty", "Builty deleted and quantity restored to Pending DO.")

    def open_new_builty_window(self):
        # Separate DO-selection workspace styled after the supplied SWASTIK DO Entry screenshot.
        win = tk.Toplevel(self)
        win.title("Builty Entry — Select Pending DO")
        win.geometry("960x650")
        win.minsize(900, 580)
        win.transient(self)

        toolbar = ttk.Frame(win, padding=(10, 8))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Close", command=win.destroy).pack(side="left", padx=3)
        ttk.Label(toolbar, text="Builty Entry — Pending DO Selection",
                  style="Title.TLabel").pack(side="left", padx=12)
        ttk.Button(toolbar, text="Refresh", command=lambda: load_pending()).pack(side="right")

        body = ttk.Frame(win, padding=8)
        body.pack(fill="both", expand=True)
        left = ttk.LabelFrame(body, text="DO Details (Auto from PDF / Saved DO)", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = ttk.LabelFrame(body, text="Pending DO / Quota List", padding=8)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        fields = [
            ("DO No.", "do_no"), ("Date", "do_date"), ("GMDC DO No.", "gmdc_do_no"),
            ("DO Party Name", "customer_name"), ("Customer No.", "customer_no"),
            ("Customer GSTIN", "customer_gstin"), ("Regi. No.", "regi_no"),
            ("Agent Name", "agent_name"), ("Item Name", "material"), ("Mines Name", "from_place"),
            ("No. of Trucks", "no_trucks"), ("Truck Capacity", "truck_capacity"),
            ("Total Tonne", "qty"), ("Rate Rs.", "unit_price"), ("Amount Rs.", "extended_price"),
            ("Order Total", "order_total"), ("Schedule Date", "schedule_date"),
        ]
        vars_ = {}
        grid = ttk.Frame(left)
        grid.pack(fill="x")
        for i, (label, key) in enumerate(fields):
            rr, cc = divmod(i, 2)
            cell = ttk.Frame(grid)
            cell.grid(row=rr, column=cc, sticky="ew", padx=3, pady=3)
            ttk.Label(cell, text=label, width=16).pack(anchor="w")
            var = tk.StringVar()
            vars_[key] = var
            ent = ttk.Entry(cell, textvariable=var, width=25)
            ent.pack(fill="x")
            if key not in ("do_no", "customer_name", "customer_no", "customer_gstin",
                           "regi_no", "agent_name", "no_trucks", "truck_capacity"):
                ent.configure(state="readonly")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        cols = ("id", "do_no", "party", "material", "pending")
        tree = ttk.Treeview(right, columns=cols, show="headings", height=18, selectmode="browse")
        for col, title, width in zip(cols, ("ID", "DO No.", "DO Party Name", "Item Name", "Pending TON"),
                                      (42, 115, 160, 135, 80)):
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor="w" if col in ("party", "material") else "center")
        tree.pack(fill="both", expand=True)

        records = {}
        def load_pending():
            for item in tree.get_children():
                tree.delete(item)
            records.clear()
            con = db()
            rows = con.execute(
                "SELECT * FROM dos WHERE remaining_qty>0.000001 ORDER BY id DESC"
            ).fetchall()
            con.close()
            for row in rows:
                data = dict(row)
                records[int(row["id"])] = data
                tree.insert("", "end", iid=str(row["id"]), values=(
                    row["id"], row["do_no"] or row["gmdc_do_no"] or "",
                    row["customer_name"] or "", row["material"] or "",
                    f'{_f(row["remaining_qty"]):.3f}'
                ))
            if not rows:
                for key, var in vars_.items():
                    var.set("")
        def select_do(_event=None):
            sel = tree.selection()
            if not sel:
                return
            row = records.get(int(sel[0]))
            if not row:
                return
            mapping = {
                "do_no": "do_no", "do_date": "do_date", "gmdc_do_no": "gmdc_do_no",
                "customer_name": "customer_name", "customer_no": "customer_no",
                "customer_gstin": "customer_gstin", "material": "material",
                "from_place": "from_place", "qty": "remaining_qty",
                "unit_price": "unit_price", "extended_price": "extended_price",
                "order_total": "order_total", "schedule_date": "schedule_date",
            }
            for key, var in vars_.items():
                source = mapping.get(key)
                if source:
                    var.set(str(row[source] if row[source] is not None else ""))
                else:
                    var.set("")
            # Keep selected DO linked to the main Builty form.
            original = next((iid for iid in self.pd.get_children()
                             if int(self.pd.item(iid)["values"][0]) == int(row["id"])), None)
            if original:
                self.pd.selection_set(original)
                self.pd.focus(original)
                self.pd.see(original)
            self.clear_builty_form()
            if original:
                self.pd.selection_set(original)
                self._on_pending_do_select()
            self.b_vars["qty"].set(f'{_f(row["remaining_qty"]):.3f}')
        tree.bind("<<TreeviewSelect>>", select_do)
        tree.bind("<Double-1>", lambda _e: use_selected())
        buttons = ttk.Frame(win, padding=8)
        buttons.pack(fill="x")
        def use_selected():
            if not tree.selection():
                messagebox.showwarning("Select Pending DO", "Pehla Pending DO select karo.", parent=win)
                return
            select_do()
            win.destroy()
        ttk.Button(buttons, text="Create Builty for Selected DO", command=use_selected).pack(side="left")
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right")
        load_pending()

    def toggle_manual_builty(self):
        manual = bool(self.manual_builty.get())
        if manual:
            self.b_do_summary.set("Manual mode: select a pending DO for stock/quantity control, then edit truck, driver, owner, challan, weight, freight and remarks below. DO-derived party/GSTIN/material details remain linked to the selected DO.")
        else:
            self.b_do_summary.set("Select a pending DO to auto-fill party, GSTIN, material, quota and registration details.")
        self.update_builty_preview()

    def navigate_builty(self, step):
        rows = self.bt.get_children()
        if not rows:
            return
        selected = self.bt.selection()
        index = rows.index(selected[0]) if selected and selected[0] in rows else (0 if step > 0 else len(rows)-1)
        index = max(0, min(len(rows)-1, index + step))
        self.bt.selection_set(rows[index])
        self.bt.focus(rows[index])
        self.bt.see(rows[index])
        self.load_selected_builty()

    def load_selected_builty(self):
        sel = self.bt.selection()
        if not sel:
            messagebox.showinfo("Edit Builty", "Select a saved Builty from Saved Builty List first.")
            return
        b_id = int(self.bt.item(sel[0])["values"][0])
        con = db()
        row = con.execute("SELECT * FROM builtys WHERE id=?", (b_id,)).fetchone()
        do_row = con.execute("SELECT * FROM dos WHERE id=?", (row["do_id"],)).fetchone() if row else None
        con.close()
        if not row:
            return
        # Load existing record for review/print. Saving an existing record is intentionally
        # not performed through Create, to avoid deducting the DO quantity twice.
        self.clear_builty_form()
        mapping = {
            "builty_no": "builty_no", "truck_no": "truck_no", "date": "date",
            "qty": "qty", "from_place": "from_place", "to_place": "to_place",
            "consignee": "consignee", "driver_name": "driver_name", "remarks": "remarks",
            "freight_rate": "freight_rate", "freight_amount": "freight_amount",
            "mobile_no": "mobile_no", "owner_name": "owner_name", "address": "address",
            "driver_payable": "driver_payable",
            "challan_no": "challan_no", "quota_date": "quota_date", "pay_status": "pay_status",
            "cgst_rate": "cgst_rate", "sgst_rate": "sgst_rate", "sale_party": "sale_party",
            "supply_party": "supply_party", "center_name": "center_name",
            "quota_select": "quota_select", "vehicle_no": "vehicle_no", "sale_rate": "sale_rate",
            "sale_amount": "sale_amount", "despatch_weight": "despatch_weight",
            "receipt_weight": "receipt_weight", "freight_type": "freight_type",
            "commission": "commission", "receipt_date": "receipt_date",
            "driver_mobile": "driver_mobile", "voucher_remarks": "voucher_remarks",
            "blt_print": "blt_print",
        }
        for target, source in mapping.items():
            if source in row.keys() and row[source] is not None:
                self.b_vars[target].set(str(row[source]))
        if do_row:
            self.b_vars["do_no"].set(do_row["do_no"] or "")
            material = (do_row["material"] or "").strip()
            if len(material) > 90:
                material = material[:87] + "..."
            self.b_do_summary.set(
                f"Party: {do_row['customer_name'] or '-'}    GSTIN: {do_row['customer_gstin'] or '-'}\\n"
                f"Customer No.: {do_row['customer_no'] or '-'}    Material: {material or '-'}\\n"
                f"GMDC DO: {do_row['gmdc_do_no'] or '-'}    Internal DO: {do_row['do_no'] or '-'}\\n"
                f"Total: {_f(do_row['qty']):.3f} TON    Pending: {_f(do_row['remaining_qty']):.3f} TON"
            )
        self.update_builty_preview()

    def clear_builty_form(self):
        for key, var in self.b_vars.items():
            var.set("")
        self.b_vars["date"].set(__import__("datetime").date.today().strftime("%d/%m/%Y"))
        self.b_vars["pay_status"].set("To Be Billed")
        self.b_vars["cgst_rate"].set("0")
        self.b_vars["sgst_rate"].set("0")
        self.b_do_summary.set("Select a pending DO to show party, GSTIN, material, mines, quota and registration details.")
        self.update_builty_preview()

    def update_builty_preview(self):
        if not hasattr(self, "b_preview"):
            return
        v = {k: var.get().strip() for k, var in self.b_vars.items()}
        summary = self.b_do_summary.get()
        amount = _f(v.get("freight_amount"))
        cgst = amount * _f(v.get("cgst_rate")) / 100
        sgst = amount * _f(v.get("sgst_rate")) / 100
        total = amount + cgst + sgst
        lines = [
            "AT OWNER'S RISK",
            "",
            "                 MANSI COAL CAREER",
            "       LIGNITE SUPPLIER & COMMISSION AGENT",
            "",
            "=" * 62,
            f"L.R. No.: {v.get('builty_no','')}       L.R. Date: {v.get('date','')}",
            "=" * 62,
            " : CONSIGNOR :                         : CONSIGNEE :",
            f"{FIRM.get('name',''):<34} {v.get('consignee','')}",
            f"GSTIN: {FIRM.get('gstin',''):<27}",
            "",
            f"DO No.: {v.get('do_no','')}   Challan No.: {v.get('challan_no','')}   Quota Dt.: {v.get('quota_date','')}",
            "-" * 62,
            "Description                         Weight     Freight",
            "-" * 62,
            f"LIGNITE / MATERIAL                   {v.get('qty','')}       {amount:.2f}",
            "",
            f"Truck No.: {v.get('truck_no','')}",
            f"Driver's Name: {v.get('driver_name','')}     Mobile No.: {v.get('mobile_no','')}",
            f"Address: {v.get('address','')}",
            f"Truck Owner Name: {v.get('owner_name','')}",
            "",
            f"CGST {_f(v.get('cgst_rate')):.2f}%: {cgst:.2f}",
            f"SGST {_f(v.get('sgst_rate')):.2f}%: {sgst:.2f}",
            f"Total: {total:.2f}    To Pay / Paid: {v.get('pay_status','')}",
            "",
            v.get("remarks") or "200 Kg. Shortage allowed. We are not responsible for quality. Lignite direct loading from mines.",
            "GST TO BE PAID UNDER RCM",
            "",
            "                                            For MANSI COAL CAREER",
        ]
        self.b_preview.configure(state="normal")
        self.b_preview.delete("1.0", "end")
        self.b_preview.insert("1.0", "\n".join(lines))
        self.b_preview.configure(state="disabled")

    def _on_quota_selected(self, _event=None):
        """Load quota/date and available tonnes for the selected DO schedule."""
        do_id = getattr(self, "_selected_quota_do_id", None)
        quota = self.b_vars["quota_select"].get().strip()
        if not do_id or not quota:
            return
        try:
            quota_date, quota_qty = quota.rsplit(" — ", 1)
            available = _f(quota_qty.replace(" TON", ""))
        except ValueError:
            return
        self.b_vars["quota_date"].set(quota_date.strip())
        self.b_vars["qty"].set(f"{available:.3f}")
        self._recalc_freight()

    def _on_pending_do_select(self, _e=None):
        sel = self.pd.selection()
        if not sel:
            return
        v = self.pd.item(sel[0])["values"]
        do_id = int(v[0])
        con = db()
        row = con.execute("SELECT * FROM dos WHERE id=?", (do_id,)).fetchone()
        con.close()
        if not row:
            return
        pending = _f(row["remaining_qty"])
        self._selected_quota_do_id = do_id
        # Build quota choices from all schedule rows if the table exists; fall back
        # to the DO's single saved schedule date and remaining quantity.
        quota_options = []
        con = db()
        try:
            schedule_cols = {r[1] for r in con.execute("PRAGMA table_info(do_schedules)")}
            if schedule_cols:
                schedule_rows = con.execute(
                    "SELECT schedule_date, qty, COALESCE(remaining_qty, qty) AS remaining_qty "
                    "FROM do_schedules WHERE do_id=? ORDER BY schedule_date", (do_id,)
                ).fetchall()
                quota_options = [
                    f"{r['schedule_date']} — {_f(r['remaining_qty']):.3f} TON"
                    for r in schedule_rows if _f(r['remaining_qty']) > 0.000001
                ]
        except Exception:
            quota_options = []
        finally:
            con.close()
        if not quota_options and row["schedule_date"]:
            quota_options = [f"{row['schedule_date']} — {pending:.3f} TON"]
        # Update the visible readonly quota dropdown when the selected DO changes.
        if hasattr(self, "_quota_combo"):
            self._quota_combo.configure(values=quota_options)
        if quota_options:
            self.b_vars["quota_select"].set(quota_options[0])
            self._on_quota_selected()
        else:
            self.b_vars["quota_select"].set("")
            self.b_vars["quota_date"].set(row["schedule_date"] or "")
        self.b_vars["do_no"].set(row["do_no"] or "")
        self.b_vars["from_place"].set(row["from_place"] or "BHAVNAGAR")
        self.b_vars["to_place"].set(row["to_place"] or "")
        # DO Party Name comes from the DO customer; Supply Of Part comes from the transporter.
        transporter = (row["transporter_name"] or "").strip()
        if transporter and "MANSI COAL" in transporter.upper():
            transporter = "MANSI COAL CARRIER"
        self.b_vars["sale_party"].set((row["customer_name"] or "").strip())
        self.b_vars["supply_party"].set(transporter)
        self.b_vars["center_name"].set((row["to_place"] or "").strip())
        self.b_vars["consignee"].set(row["customer_name"] or "")
        if not self.b_vars["qty"].get():
            self.b_vars["qty"].set(f"{pending:.3f}")
        rate = lookup_rate(row["from_place"], row["to_place"], row["material"])
        if rate and not self.b_vars["freight_rate"].get():
            self.b_vars["freight_rate"].set(f"{rate:.2f}")
        self.b_do_summary.set(
            f"Party Name: {row['customer_name'] or ''}     GSTIN: {row['customer_gstin'] or ''}\\n"
            f"Customer No.: {row['customer_no'] or ''}     Item: {row['material'] or ''}\\n"
            f"Mines / From: {row['from_place'] or 'BHAVNAGAR'}     Quota Date: {row['schedule_date'] or ''}\\n"
            f"DO No.: {row['do_no'] or ''}     Total TON: {row['qty'] or 0}     Pending TON: {pending:.3f}\\n"
            "Regi. No.: (party master integration pending)"
        )
        self._recalc_freight()
        self.update_builty_preview()

    def _recalc_freight(self):
        q = _f(self.b_vars["qty"].get())
        r = _f(self.b_vars["freight_rate"].get())
        gross = q * r
        commission = _f(self.b_vars["commission"].get())
        payable = gross - commission
        self.b_vars["freight_amount"].set(f"{gross:.2f}")
        if "driver_payable" in self.b_vars:
            self.b_vars["driver_payable"].set(f"{payable:.2f}")

    def show_all_builty_records(self):
        self.show_all_builtys = True
        self.refresh_builty()

    def show_selected_do_builtys(self):
        self.show_all_builtys = False
        self.refresh_builty()

    def refresh_builty(self):
        if not hasattr(self, "pd"):
            return
        selected_do_id = None
        try:
            selection = self.pd.selection()
            if selection:
                selected_do_id = int(self.pd.item(selection[0], "values")[0])
        except (ValueError, IndexError, TypeError):
            selected_do_id = None
        for t in (self.pd, self.bt):
            for x in t.get_children():
                t.delete(x)
        con = db()
        try:
            for r in con.execute("SELECT id,do_no,gmdc_do_no,customer_name,material,remaining_qty,to_place FROM dos WHERE remaining_qty>0.000001 ORDER BY id DESC"):
                self.pd.insert("", "end", values=(r["id"], r["do_no"] or r["gmdc_do_no"] or "", r["customer_name"], r["material"], "{:.3f}".format(r["remaining_qty"])))
            if selected_do_id is not None:
                for iid in self.pd.get_children():
                    if int(self.pd.item(iid, "values")[0]) == selected_do_id:
                        self.pd.selection_set(iid)
                        break
            selected_do_id = None
            if not getattr(self, "show_all_builtys", False) and self.pd.selection():
                selected_do_id = int(self.pd.item(self.pd.selection()[0], "values")[0])
            query = """SELECT b.id,b.builty_no,b.do_id,d.do_no,d.customer_name,b.date,b.truck_no,b.qty,
                             b.freight_amount,b.billed,b.freight_paid
                      FROM builtys b JOIN dos d ON d.id=b.do_id"""
            params = ()
            if selected_do_id is not None and not getattr(self, "show_all_builtys", False):
                query += " WHERE b.do_id=?"
                params = (selected_do_id,)
            query += " ORDER BY b.id DESC"
            for r in con.execute(query, params):
                self.bt.insert("", "end", values=(r["id"], r["builty_no"], r["do_no"] or "", r["customer_name"] or "", r["date"], r["truck_no"], "{:.3f}".format(r["qty"]), "{:.2f}".format(r["freight_amount"]), "Billed" if r["billed"] else ("Paid" if r["freight_paid"] else "Pending")))
        finally:
            con.close()
    def create_builty(self):
        sel = self.pd.selection()
        if not sel:
            messagebox.showwarning("Select DO", "Select a pending DO first.")
            return
        v = self.pd.item(sel[0])["values"]
        do_id = int(v[0])
        pending = _f(v[4])
        qty = _f(self.b_vars["qty"].get())
        if qty <= 0:
            messagebox.showerror("Qty", "Loaded quantity must be greater than zero.")
            return
        if qty > pending + 1e-9:
            messagebox.showerror("Qty exceeded", f"Maximum available is {pending:.3f} TON.")
            return
        rate = _f(self.b_vars["freight_rate"].get())
        freight = _f(self.b_vars["freight_amount"].get()) or (qty * rate)
        con = db()
        try:
            cur = con.execute(
                """INSERT INTO builtys(builty_no,do_id,truck_no,date,qty,freight_rate,freight_amount,
                   from_place,to_place,consignor,consignee,driver_name,ewaybill,remarks)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (self.b_vars["builty_no"].get().strip(), do_id,
                 self.b_vars["truck_no"].get().strip(), self.b_vars["date"].get().strip(),
                 qty, rate, freight,
                 self.b_vars["from_place"].get().strip(), self.b_vars["to_place"].get().strip(),
                 FIRM["name"], self.b_vars["consignee"].get().strip(),
                 self.b_vars["driver_name"].get().strip(),
                 self.b_vars["ewaybill"].get().strip(),
                 self.b_vars["remarks"].get().strip()),
            )
            b_id = cur.lastrowid
            # Persist every extra field visible in the Builty form, not just print essentials.
            extra_keys = (
                "mobile_no", "owner_name", "address", "challan_no", "quota_date", "driver_payable",
                "pay_status", "cgst_rate", "sgst_rate", "sale_party", "supply_party",
                "center_name", "quota_select", "vehicle_no", "sale_rate", "sale_amount",
                "despatch_weight", "receipt_weight", "freight_type", "commission",
                "receipt_date", "driver_mobile", "voucher_remarks", "blt_print",
            )
            con.execute(
                "UPDATE builtys SET " + ",".join(f"{key}=?" for key in extra_keys) + " WHERE id=?",
                tuple(_f(self.b_vars[k].get()) if k in (
                    "cgst_rate", "sgst_rate", "sale_rate", "sale_amount",
                    "despatch_weight", "receipt_weight", "commission", "driver_payable"
                ) else self.b_vars[k].get().strip() for k in extra_keys) + (b_id,),
            )
            quota_date = self.b_vars["quota_date"].get().strip()
            if quota_date:
                schedule = con.execute(
                    "SELECT remaining_qty FROM do_schedules WHERE do_id=? AND schedule_date=?",
                    (do_id, quota_date),
                ).fetchone()
                if schedule and qty > _f(schedule["remaining_qty"]) + 1e-9:
                    con.rollback()
                    con.close()
                    messagebox.showerror("Quota Qty", f"Selected quota has only {_f(schedule['remaining_qty']):.3f} TON remaining.")
                    return
                if schedule:
                    con.execute("UPDATE do_schedules SET remaining_qty=remaining_qty-? WHERE do_id=? AND schedule_date=?",
                                (qty, do_id, quota_date))
            con.execute("UPDATE dos SET remaining_qty=remaining_qty-? WHERE id=?", (qty, do_id))
            con.commit()
        except Exception as e:
            con.close()
            messagebox.showerror("Builty", str(e))
            return

        row = con.execute("SELECT * FROM builtys WHERE id=?", (b_id,)).fetchone()
        do_row = con.execute("SELECT * FROM dos WHERE id=?", (do_id,)).fetchone()
        con.close()
        self._print_builty_pdf(dict(row), dict(do_row))
        for k in self.b_vars:
            self.b_vars[k].set("")
        self.refresh_builty()
        self.refresh_do()

    def preview_selected_builty(self):
        sel = self.bt.selection()
        if not sel:
            self.update_builty_preview()
            messagebox.showinfo("Print Preview", "Saved Builty select karo. New Builty mate pehla DO select kari details bharo; save pachhi PDF preview/print thai shakshe.")
            return
        b_id = int(self.bt.item(sel[0])["values"][0])
        con = db()
        row = con.execute("SELECT * FROM builtys WHERE id=?", (b_id,)).fetchone()
        do_row = con.execute("SELECT * FROM dos WHERE id=?", (row["do_id"],)).fetchone() if row else None
        con.close()
        if row and do_row:
            self._print_builty_pdf(dict(row), dict(do_row))

    def reprint_builty(self):
        sel = self.bt.selection()
        if not sel:
            messagebox.showwarning("Print Builty", "Saved Builty List mathi Builty select karo.")
            return
        b_id = int(self.bt.item(sel[0])["values"][0])
        con = db()
        row = con.execute("SELECT * FROM builtys WHERE id=?", (b_id,)).fetchone()
        if not row:
            con.close()
            return
        do_row = con.execute("SELECT * FROM dos WHERE id=?", (row["do_id"],)).fetchone()
        con.close()
        self._print_builty_pdf(dict(row), dict(do_row))

    def _print_builty_pdf(self, row, do_row):
        out = EXPORT_DIR / f"Builty_{row['builty_no'] or row['id']}.pdf"
        try:
            generate_builty_pdf(out, FIRM, row, do_row, copy_label="CONSIGNOR COPY")
        except Exception as e:
            messagebox.showerror("Print Builty", str(e))
            return
        if messagebox.askyesno("Builty PDF", f"Saved: {out.name}\n\nOpen it now to print?"):
            open_file(out)

    # ===================== BILL TAB =====================
    def bill_tab(self, nb):
        f = ttk.Frame(nb, padding=6)
        nb.add(f, text="3 · Bill (Material)")

        # Header fields similar to the supplied SWASTIK Bill screen.
        head = ttk.LabelFrame(f, text="Bill Header", padding=6)
        head.pack(fill="x", pady=(0, 5))
        self.bill_vars = {k: tk.StringVar() for k in (
            "bill_no", "bill_date", "due_date", "party_name", "item_name",
            "mines_name", "do_no", "dnote_no", "period_from", "period_to",
            "rate_per_ton", "gst_paid_by", "weight_basis", "cgst_pct",
            "sgst_pct", "igst_pct", "remarks"
        )}
        self.bill_vars["bill_date"].set(datetime.now().strftime("%d/%m/%y"))
        self.bill_vars["due_date"].set(datetime.now().strftime("%d/%m/%y"))
        self.bill_vars["gst_paid_by"].set("Transporter")
        self.bill_vars["weight_basis"].set("Both Less")
        self.bill_vars["cgst_pct"].set("0")
        self.bill_vars["sgst_pct"].set("0")
        self.bill_vars["igst_pct"].set("5")

        header_fields = [
            ("Party Name", "party_name", 28), ("Item Name", "item_name", 18),
            ("Mines Name", "mines_name", 18), ("DO No.", "do_no", 14),
            ("D/Note No.", "dnote_no", 12), ("Bill No.", "bill_no", 12),
            ("Date", "bill_date", 12), ("Due Date", "due_date", 12),
            ("Period From", "period_from", 12), ("Period To", "period_to", 12),
        ]
        for idx, (label, key, width) in enumerate(header_fields):
            row, col = divmod(idx, 5)
            ttk.Label(head, text=label).grid(row=row, column=col*2, sticky="w", padx=3, pady=3)
            ttk.Entry(head, textvariable=self.bill_vars[key], width=width).grid(row=row, column=col*2+1, sticky="ew", padx=3, pady=3)
        for col in range(10):
            head.grid_columnconfigure(col, weight=1)

        listing = ttk.LabelFrame(f, text="Pending Builty — select multiple of same party", padding=4)
        listing.pack(fill="both", expand=True)
        cols = ("id", "do", "builty", "date", "vehicle", "mines", "desp", "rcpt", "rate", "amount")
        heads = ("ID", "DO No.", "Builty No.", "Date", "Vehicle No.", "Mines", "Desp. Weight", "Rcpt. Weight", "Rate Rs.", "Amount Rs.")
        widths = (42, 90, 90, 85, 120, 85, 100, 100, 95, 110)
        self.pb = ttk.Treeview(listing, columns=cols, show="headings", selectmode="extended", height=10)
        for col, title, width in zip(cols, heads, widths):
            self.pb.heading(col, text=title)
            self.pb.column(col, width=width, anchor="e" if col in ("desp", "rcpt", "rate", "amount") else "w")
        self.pb.column("id", width=42, stretch=False)
        self.pb.pack(fill="both", expand=True)
        self.pb.bind("<<TreeviewSelect>>", self.update_selected_total)

        settings = ttk.Frame(f)
        settings.pack(fill="x", pady=5)
        for idx, (label, key, width) in enumerate((
            ("Rate / TON", "rate_per_ton", 10), ("CGST %", "cgst_pct", 7),
            ("SGST %", "sgst_pct", 7), ("IGST %", "igst_pct", 7),
        )):
            ttk.Label(settings, text=label).grid(row=0, column=idx*2, sticky="w", padx=3)
            entry = ttk.Entry(settings, textvariable=self.bill_vars[key], width=width)
            entry.grid(row=0, column=idx*2+1, padx=3)
            if key == "rate_per_ton":
                entry.bind("<KeyRelease>", self.update_selected_total)
        ttk.Label(settings, text="GST Paid By").grid(row=0, column=8, padx=3)
        ttk.Combobox(settings, textvariable=self.bill_vars["gst_paid_by"], values=("Transporter", "Customer", "Company"), state="readonly", width=13).grid(row=0, column=9, padx=3)
        ttk.Label(settings, text="Weight").grid(row=0, column=10, padx=3)
        weight_combo = ttk.Combobox(settings, textvariable=self.bill_vars["weight_basis"], values=("Both Less", "Despatch", "Receipt"), state="readonly", width=12)
        weight_combo.grid(row=0, column=11, padx=3)
        weight_combo.bind("<<ComboboxSelected>>", self.update_selected_total)
        ttk.Label(settings, text="Remarks").grid(row=1, column=0, padx=3, sticky="w")
        ttk.Entry(settings, textvariable=self.bill_vars["remarks"], width=80).grid(row=1, column=1, columnspan=7, sticky="ew", padx=3)

        totals = ttk.LabelFrame(f, text="Bill Totals", padding=5)
        totals.pack(fill="x", pady=(0, 5))
        self.bill_total = tk.StringVar(value="No. of Builties: 0")
        self.bill_gross = tk.StringVar(value="0.00")
        self.bill_gst = tk.StringVar(value="0.00")
        self.bill_round = tk.StringVar(value="0.00")
        self.bill_net = tk.StringVar(value="0.00")
        self.bill_desp = tk.StringVar(value="0.000")
        self.bill_rcpt = tk.StringVar(value="0.000")
        for idx, (label, var) in enumerate((
            ("No. of Builties", self.bill_total), ("Gross Amount", self.bill_gross),
            ("GST Amt.", self.bill_gst), ("Round Off", self.bill_round),
            ("Net Amount", self.bill_net), ("Desp. Weight", self.bill_desp),
            ("Rcpt. Weight", self.bill_rcpt),
        )):
            ttk.Label(totals, text=label).grid(row=0, column=idx*2, padx=3, pady=2, sticky="w")
            ttk.Label(totals, textvariable=var, style="Head.TLabel").grid(row=0, column=idx*2+1, padx=3, pady=2, sticky="w")

        actions = ttk.Frame(f)
        actions.pack(fill="x")
        ttk.Button(actions, text="Refresh", command=self.refresh_bill).pack(side="left")
        ttk.Button(actions, text="Create Bill & Print PDF", command=self.create_bill).pack(side="right")
        self._bill_db_signature = None
        self.refresh_bill()
        self.after(2500, self._auto_refresh_bill)

    def _bill_pending_signature(self):
        con = db()
        try:
            rows = con.execute(
                """SELECT b.id,b.builty_no,b.do_id,b.truck_no,b.date,b.qty,
                          b.despatch_weight,b.receipt_weight,b.sale_rate,b.sale_amount,
                          b.freight_rate,b.freight_amount,b.billed,
                          d.do_no,d.customer_name,d.material,d.from_place,d.to_place
                   FROM builtys b JOIN dos d ON d.id=b.do_id
                   WHERE b.billed=0 ORDER BY b.id DESC"""
            ).fetchall()
            return tuple(tuple(row) for row in rows)
        finally:
            con.close()

    def _auto_refresh_bill(self):
        # Detect changes saved from DO/Builty screens and refresh without a manual click.
        try:
            if hasattr(self, "pb"):
                signature = self._bill_pending_signature()
                if signature != self._bill_db_signature:
                    self.refresh_bill()
        except Exception:
            pass
        finally:
            try:
                self.after(2500, self._auto_refresh_bill)
            except Exception:
                pass

    def refresh_bill(self):
        if not hasattr(self, "pb"):
            return
        selected_ids = {str(self.pb.item(i)["values"][0]) for i in self.pb.selection()}
        for x in self.pb.get_children():
            self.pb.delete(x)
        con = db()
        try:
            rows = con.execute(
                """SELECT b.id,b.builty_no,d.do_no,d.customer_name,b.truck_no,b.date,b.qty,
                          COALESCE(b.despatch_weight,b.qty) AS desp,
                          COALESCE(b.receipt_weight,b.qty) AS rcpt,
                          COALESCE(b.sale_rate,b.freight_rate,0) AS rate,
                          COALESCE(b.sale_amount,b.freight_amount,0) AS amount,
                          d.material,d.from_place,d.to_place
                   FROM builtys b JOIN dos d ON d.id=b.do_id
                   WHERE b.billed=0 ORDER BY b.id DESC"""
            ).fetchall()
            self._bill_db_signature = self._bill_pending_signature()
            for r in rows:
                iid = self.pb.insert("", "end", values=(
                    r["id"], r["do_no"], r["builty_no"], r["date"], r["truck_no"],
                    r["from_place"] or r["material"] or "", f'{r["desp"]:.3f}',
                    f'{r["rcpt"]:.3f}', f'{r["rate"]:.2f}', f'{r["amount"]:.2f}',
                ))
                if str(r["id"]) in selected_ids:
                    self.pb.selection_add(iid)
        finally:
            con.close()
        self.update_selected_total()

    def update_selected_total(self, _e=None):
        # Recalculate the Rate Rs. and Amount Rs. columns from the entered bill rate
        # and currently selected weight basis, so the grid agrees with the bill total.
        basis = self.bill_vars["weight_basis"].get()
        entered_rate = _f(self.bill_vars["rate_per_ton"].get())
        for iid in self.pb.get_children():
            values = list(self.pb.item(iid)["values"])
            desp_row, rcpt_row = _f(values[6]), _f(values[7])
            row_rate = entered_rate if entered_rate > 0 else _f(values[8])
            bill_weight = (rcpt_row - desp_row) if basis == "Both Less" else (desp_row if basis == "Despatch" else rcpt_row)
            values[8] = f"{row_rate:.2f}"
            values[9] = f"{bill_weight * row_rate:.2f}"
            self.pb.item(iid, values=values)

        selected = [self.pb.item(i)["values"] for i in self.pb.selection()]
        count = len(selected)
        desp = sum(_f(v[6]) for v in selected if v)
        rcpt = sum(_f(v[7]) for v in selected if v)
        rate = entered_rate
        if rate <= 0 and desp:
            rate = sum(_f(v[8]) * _f(v[6]) for v in selected if v) / desp
        taxable_qty = (rcpt - desp) if basis == "Both Less" else (desp if basis == "Despatch" else rcpt)
        gross = round(taxable_qty * rate, 2)
        gst = round(gross * (_f(self.bill_vars["cgst_pct"].get()) + _f(self.bill_vars["sgst_pct"].get()) + _f(self.bill_vars["igst_pct"].get())) / 100, 2)
        net_before_round = gross + gst
        net = round(net_before_round)
        self.bill_total.set(str(count))
        self.bill_desp.set(f"{desp:.3f}")
        self.bill_rcpt.set(f"{rcpt:.3f}")
        self.bill_gross.set(f"{gross:,.2f}")
        self.bill_gst.set(f"{gst:,.2f}")
        self.bill_round.set(f"{net - net_before_round:,.2f}")
        self.bill_net.set(f"{net:,.2f}")
        if selected:
            try:
                con = db()
                row = con.execute("SELECT d.customer_name,d.material,d.from_place,d.do_no FROM dos d JOIN builtys b ON b.do_id=d.id WHERE b.id=?", (int(selected[0][0]),)).fetchone()
                con.close()
                if row:
                    self.bill_vars["party_name"].set(row["customer_name"] or "")
                    self.bill_vars["item_name"].set(row["material"] or "")
                    self.bill_vars["mines_name"].set(row["from_place"] or "")
                    self.bill_vars["do_no"].set(row["do_no"] or "")
            except Exception:
                pass

    def create_bill(self):
        sel = self.pb.selection()
        if not sel:
            messagebox.showwarning("Select Builty", "Select one or more pending Builty records.")
            return
        ids = [int(self.pb.item(i)["values"][0]) for i in sel]
        con = db()
        rows = []
        for bid in ids:
            row = con.execute("""SELECT b.id,b.qty,b.despatch_weight,b.receipt_weight,b.sale_rate,
                b.sale_amount,d.customer_name,d.customer_gstin,d.material,d.from_place,d.do_no
                FROM builtys b JOIN dos d ON d.id=b.do_id WHERE b.id=?""", (bid,)).fetchone()
            if row:
                rows.append(dict(row))
        if not rows:
            con.close()
            messagebox.showerror("Bill", "Selected Builty records could not be loaded.")
            return
        customer = rows[0]["customer_name"] or ""
        if any((r["customer_name"] or "") != customer for r in rows):
            con.close()
            messagebox.showerror("Customer mismatch", "Select Builty records of the same customer.")
            return
        desp = sum(_f(r["despatch_weight"] or r["qty"]) for r in rows)
        rcpt = sum(_f(r["receipt_weight"] or r["qty"]) for r in rows)
        basis = self.bill_vars["weight_basis"].get()
        qty = (rcpt - desp) if basis == "Both Less" else (desp if basis == "Despatch" else rcpt)
        rate = _f(self.bill_vars["rate_per_ton"].get())
        if rate <= 0:
            rate = (sum(_f(r["sale_rate"]) * _f(r["despatch_weight"] or r["qty"]) for r in rows) / desp) if desp else 0
        sub = round(qty * rate, 2)
        cgst = round(sub * _f(self.bill_vars["cgst_pct"].get()) / 100, 2)
        sgst = round(sub * _f(self.bill_vars["sgst_pct"].get()) / 100, 2)
        igst = round(sub * _f(self.bill_vars["igst_pct"].get()) / 100, 2)
        before_round = sub + cgst + sgst + igst
        total = round(before_round)
        try:
            cur = con.execute("""INSERT INTO bills(bill_no,bill_date,bill_type,customer_name,customer_gstin,total_qty,
                rate_per_ton,subtotal,cgst,sgst,igst,total,remarks) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (self.bill_vars["bill_no"].get().strip() or None, self.bill_vars["bill_date"].get().strip(),
                 "MATERIAL", customer, rows[0]["customer_gstin"] or "", qty, rate, sub, cgst, sgst, igst, total,
                 self.bill_vars["remarks"].get().strip()))
            bill_id = cur.lastrowid
            for r in rows:
                con.execute("INSERT INTO bill_builtys(bill_id,builty_id) VALUES(?,?)", (bill_id, r["id"]))
                con.execute("UPDATE builtys SET billed=1 WHERE id=?", (r["id"],))
            con.commit()
        except Exception as e:
            con.close()
            messagebox.showerror("Bill", str(e))
            return
        bill_row = dict(con.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone())
        bill_row.update({"customer_gstin": rows[0]["customer_gstin"] or "",
                         "due_date": self.bill_vars["due_date"].get(),
                         "gst_paid_by": self.bill_vars["gst_paid_by"].get(),
                         "round_off": total - before_round,
                         "party_name": customer, "item_name": rows[0]["material"] or "",
                         "mines_name": rows[0]["from_place"] or "",
                         "do_no": rows[0]["do_no"] or "", "weight_basis": basis})
        builty_rows = []
        for r in rows:
            br = con.execute("""SELECT b.builty_no,b.truck_no,b.date,b.qty,b.despatch_weight,b.receipt_weight,
                b.sale_rate,b.sale_amount,d.do_no,d.material,d.from_place
                FROM builtys b JOIN dos d ON d.id=b.do_id WHERE b.id=?""", (r["id"],)).fetchone()
            builty_rows.append(dict(br))
        con.close()
        out = EXPORT_DIR / f"Bill_{bill_row['bill_no'] or bill_id}.pdf"
        try:
            generate_bill_pdf(out, FIRM, bill_row, builty_rows)
        except Exception as e:
            messagebox.showerror("Print Bill", str(e))
        else:
            if messagebox.askyesno("Bill PDF", f"Saved: {out.name}\n\nOpen it now?"):
                open_file(out)
        self.refresh_bill()
        self.refresh_builty()

    # ===================== DATE-WISE EXPORT =====================
    def export_tab(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="5 · Date-wise Export")
        ttk.Label(f, text="Export DO, Builty and Bill records by date range",
                  style="Title.TLabel").pack(anchor="w", pady=(0, 8))
        dates = ttk.LabelFrame(f, text="Date Range", padding=8)
        dates.pack(fill="x", pady=5)
        self.export_from = tk.StringVar(value="01/01/2000")
        self.export_to = tk.StringVar(value=datetime.now().strftime("%d/%m/%y"))
        ttk.Label(dates, text="From Date (DD/MM/YY)").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(dates, textvariable=self.export_from, width=16).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dates, text="To Date (DD/MM/YY)").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Entry(dates, textvariable=self.export_to, width=16).grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(f, text="Select an export below. Each export includes all matching records in the selected date range.",
                  wraplength=900).pack(anchor="w", pady=8)
        buttons = ttk.Frame(f)
        buttons.pack(anchor="w", pady=5)
        ttk.Button(buttons, text="Export DOs to CSV", command=lambda: self.export_datewise("do")).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons, text="Export Builties to CSV", command=lambda: self.export_datewise("builty")).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(buttons, text="Export Bills to CSV", command=lambda: self.export_datewise("bill")).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(buttons, text="Daily Builty Report (CSV)", command=self.export_daily_builty_report).grid(row=2, column=0, columnspan=3, padx=5, pady=8, sticky="ew")
        ttk.Button(buttons, text="Export ALL (DO + Builty + Bills)", command=lambda: self.export_datewise("all")).grid(row=1, column=0, columnspan=3, padx=5, pady=8, sticky="ew")


    def export_daily_builty_report(self):
        """Export a date-filtered Builty daily report with transport and party details."""
        from tkinter import filedialog
        from pathlib import Path as _Path
        import csv as _csv

        start = self._parse_export_date(self.export_from.get())
        end = self._parse_export_date(self.export_to.get())
        if not start or not end:
            messagebox.showerror("Daily Builty Report", "Enter dates as DD/MM/YY or DD/MM/YYYY.")
            return
        if start > end:
            messagebox.showerror("Daily Builty Report", "From Date must be on or before To Date.")
            return
        folder = filedialog.askdirectory(title="Choose folder to save Daily Builty Report")
        if not folder:
            return

        con = db()
        try:
            builty_columns = {r["name"] for r in con.execute("PRAGMA table_info(builtys)")}
            do_columns = {r["name"] for r in con.execute("PRAGMA table_info(dos)")}
            def col(alias, available, name, fallback=""):
                return f"{alias}.{name}" if name in available else f"'{fallback}'"
            # GRAND TOTAL is the saved freight amount; if the source contains a separate
            # grand-total field in future versions, prefer that field.
            grand_total_expr = col("b", builty_columns, "grand_total")
            if grand_total_expr == "' '" or grand_total_expr == "''":
                grand_total_expr = "COALESCE(b.freight_amount,0)"
            elif grand_total_expr == "''":
                grand_total_expr = "COALESCE(b.freight_amount,0)"
            mines_expr = col("b", builty_columns, "from_place", "BHAVNAGAR")
            if mines_expr == "'BHAVNAGAR'" and "from_place" in do_columns:
                mines_expr = "d.from_place"
            agent_expr = col("b", builty_columns, "agent_name")
            if agent_expr == "''":
                agent_expr = col("d", do_columns, "agent_name")
            if agent_expr == "''":
                agent_expr = col("d", do_columns, "transporter_name")
            sale_expr = col("b", builty_columns, "sale_party")
            if sale_expr == "''":
                sale_expr = col("b", builty_columns, "sale_party_name")
            supply_expr = col("b", builty_columns, "supply_party")
            if supply_expr == "''":
                supply_expr = col("b", builty_columns, "supply_party_mill")
            if sale_expr == "''" and supply_expr == "''":
                sale_supply_expr = "''"
            else:
                sale_supply_expr = "TRIM(COALESCE(" + sale_expr + ", '') || CASE WHEN COALESCE(" + sale_expr + ", '') <> '' AND COALESCE(" + supply_expr + ", '') <> '' THEN ' / ' ELSE '' END || COALESCE(" + supply_expr + ", ''))"
            query = f"""
                SELECT b.builty_no AS builty_no,
                       {mines_expr} AS mines,
                       b.date AS builty_date,
                       COALESCE(d.do_no,d.gmdc_do_no,'') AS do_no,
                       b.truck_no AS vehicle_no,
                       {grand_total_expr} AS grand_total,
                       COALESCE(b.qty,0) AS weight,
                       COALESCE(d.customer_name,'') AS do_party_name,
                       {sale_supply_expr} AS sale_supply_party,
                       {agent_expr} AS agent_name,
                       COALESCE(b.freight_rate,0) AS freight_rate
                FROM builtys b JOIN dos d ON d.id=b.do_id
                ORDER BY b.date,b.id
            """
            records = []
            for row in con.execute(query):
                parsed = self._parse_export_date(row["builty_date"])
                if parsed and start <= parsed <= end:
                    records.append(dict(row))
            fields = [
                ("Builty No.", "builty_no"), ("Mines", "mines"),
                ("Blt. Date", "builty_date"), ("DO No.", "do_no"),
                ("Vehicle No.", "vehicle_no"), ("GRAND TOTAL", "grand_total"),
                ("Weight", "weight"), ("DO Party Name", "do_party_name"),
                ("Sale Party / Supply Party - Mill Name", "sale_supply_party"),
                ("Agent Name", "agent_name"), ("Freight Rate", "freight_rate"),
            ]
            out = _Path(folder) / f"Daily_Builty_Report_{start.strftime('%Y%m%d')}_to_{end.strftime('%Y%m%d')}.csv"
            with open(out, "w", newline="", encoding="utf-8-sig") as fh:
                writer = _csv.writer(fh)
                writer.writerow([label for label, _ in fields])
                for record in records:
                    writer.writerow([record.get(key, "") for _, key in fields])
                writer.writerow([])
                writer.writerow(["TOTAL WEIGHT", sum(float(x.get("weight") or 0) for x in records)])
                writer.writerow(["GRAND TOTAL", sum(float(x.get("grand_total") or 0) for x in records)])
        except Exception as e:
            messagebox.showerror("Daily Builty Report", str(e))
            return
        finally:
            con.close()
        messagebox.showinfo("Daily Builty Report", f"Report saved to:\n{out}\n\nRecords: {len(records)}")

    def _parse_export_date(self, value):
        value = str(value or "").strip()
        for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y", "%d-%m-%Y", "%d-%b-%y", "%d-%b-%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    def export_datewise(self, kind):
        from tkinter import filedialog
        start = self._parse_export_date(self.export_from.get())
        end = self._parse_export_date(self.export_to.get())
        if not start or not end:
            messagebox.showerror("Date-wise Export", "Enter dates as DD/MM/YY or DD/MM/YYYY.")
            return
        if start > end:
            messagebox.showerror("Date-wise Export", "From Date must be on or before To Date.")
            return
        folder = filedialog.askdirectory(title="Choose folder to save date-wise exports")
        if not folder:
            return
        from pathlib import Path as _Path
        import csv as _csv
        outdir = _Path(folder)
        con = db()
        jobs = []
        if kind in ("do", "all"):
            jobs.append(("DOs", "SELECT * FROM dos ORDER BY do_date,id", "do_date"))
        if kind in ("builty", "all"):
            jobs.append(("Builties", """SELECT b.*,d.do_no,d.customer_name,d.material,d.from_place AS do_from_place,
                d.to_place AS do_to_place FROM builtys b JOIN dos d ON d.id=b.do_id ORDER BY b.date,b.id""", "date"))
        if kind in ("bill", "all"):
            jobs.append(("Bills", "SELECT * FROM bills ORDER BY bill_date,id", "bill_date"))
        exported = []
        try:
            for label, query, date_col in jobs:
                rows = [dict(r) for r in con.execute(query)]
                matching = []
                for row in rows:
                    parsed = self._parse_export_date(row.get(date_col))
                    if parsed and start <= parsed <= end:
                        matching.append(row)
                if matching:
                    fields = list(matching[0].keys())
                else:
                    # Preserve useful headers even when the range has no matching rows.
                    fields = list(rows[0].keys()) if rows else []
                path = outdir / f"{label}_{start.strftime('%Y%m%d')}_to_{end.strftime('%Y%m%d')}.csv"
                with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                    if fields:
                        writer = _csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                        writer.writeheader()
                        writer.writerows(matching)
                exported.append(f"{label}: {len(matching)} records")
        except Exception as e:
            messagebox.showerror("Date-wise Export", str(e))
            return
        finally:
            con.close()
        messagebox.showinfo("Date-wise Export Complete",
            "Saved date-wise CSV exports to:\\n" + str(outdir) + "\\n\\n" + "\\n".join(exported))

    # ===================== FREIGHT PAID TAB =====================
    def freight_paid_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="4 · Freight Paid")
        ttk.Label(f, text="Select a Builty and record freight payment", style="Head.TLabel").pack(anchor="w")
        self.fp_tv = ttk.Treeview(
            f, columns=("id", "builty", "truck", "date", "qty", "freight", "paid"),
            show="headings", height=12,
        )
        for c, h, w in zip(("id", "builty", "truck", "date", "qty", "freight", "paid"),
                           ("ID", "Builty No", "Truck", "Date", "Qty", "Freight", "Status"),
                           [50, 120, 110, 110, 90, 110, 90]):
            self.fp_tv.heading(c, text=h)
            self.fp_tv.column(c, width=w)
        self.fp_tv.pack(fill="both", expand=True, pady=6)

        form = ttk.LabelFrame(f, text="Payment Entry", padding=10)
        form.pack(fill="x", pady=6)
        self.fp_vars = {k: tk.StringVar() for k in ("pay_date", "amount", "mode", "reference_no", "remarks")}
        for i, (lab, k) in enumerate([("Date", "pay_date"), ("Amount", "amount"),
                                      ("Mode", "mode"), ("Ref No", "reference_no"), ("Remarks", "remarks")]):
            ttk.Label(form, text=lab).grid(row=0, column=i * 2, padx=4, sticky="w")
            ttk.Entry(form, textvariable=self.fp_vars[k], width=18).grid(row=0, column=i * 2 + 1, padx=4)
        ttk.Button(form, text="Save Payment", command=self.save_freight_paid).grid(row=0, column=10, padx=10)
        ttk.Button(f, text="Refresh", command=self.refresh_freight_paid).pack(anchor="e")
        self.refresh_freight_paid()

    def refresh_freight_paid(self):
        if not hasattr(self, "fp_tv"):
            return
        for x in self.fp_tv.get_children():
            self.fp_tv.delete(x)
        con = db()
        for r in con.execute(
            """SELECT id,builty_no,truck_no,date,qty,freight_amount,freight_paid
               FROM builtys ORDER BY id DESC"""
        ):
            self.fp_tv.insert("", "end", values=(
                r["id"], r["builty_no"], r["truck_no"], r["date"],
                f'{r["qty"]:.3f}', f'{r["freight_amount"]:.2f}',
                "Paid" if r["freight_paid"] else "Due",
            ))
        con.close()

    def save_freight_paid(self):
        sel = self.fp_tv.selection()
        if not sel:
            messagebox.showwarning("Freight Paid", "Select a Builty row first.")
            return
        b_id = int(self.fp_tv.item(sel[0])["values"][0])
        amount = _f(self.fp_vars["amount"].get())
        if amount <= 0:
            messagebox.showerror("Freight Paid", "Enter a valid amount.")
            return
        con = db()
        con.execute(
            """INSERT INTO freight_paid(builty_id,pay_date,amount,mode,reference_no,remarks)
               VALUES(?,?,?,?,?,?)""",
            (b_id, self.fp_vars["pay_date"].get().strip(), amount,
             self.fp_vars["mode"].get().strip(),
             self.fp_vars["reference_no"].get().strip(),
             self.fp_vars["remarks"].get().strip()),
        )
        con.execute("UPDATE builtys SET freight_paid=1 WHERE id=?", (b_id,))
        con.commit()
        con.close()
        for k in self.fp_vars:
            self.fp_vars[k].set("")
        self.refresh_freight_paid()
        self.refresh_builty()

    # ===================== DEBIT NOTE TAB =====================
    def debit_note_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="5 · Debit Note (Freight)")
        ttk.Label(f, text="Select Builty(ies) to raise a Debit Note for Freight", style="Head.TLabel").pack(anchor="w")
        self.dn_tv = ttk.Treeview(
            f, columns=("id", "builty", "customer", "truck", "date", "qty", "freight"),
            show="headings", selectmode="extended", height=10,
        )
        for c, h, w in zip(
            ("id", "builty", "customer", "truck", "date", "qty", "freight"),
            ("ID", "Builty No", "Customer", "Truck", "Date", "Qty", "Freight"),
            [50, 110, 260, 110, 100, 90, 110],
        ):
            self.dn_tv.heading(c, text=h)
            self.dn_tv.column(c, width=w)
        self.dn_tv.pack(fill="both", expand=True, pady=6)

        form = ttk.LabelFrame(f, text="Debit Note", padding=10)
        form.pack(fill="x", pady=6)
        self.dn_vars = {k: tk.StringVar() for k in ("dn_no", "dn_date", "reason")}
        for i, (lab, k) in enumerate([("DN No", "dn_no"), ("Date", "dn_date"), ("Reason", "reason")]):
            ttk.Label(form, text=lab).grid(row=0, column=i * 2, padx=4, sticky="w")
            ttk.Entry(form, textvariable=self.dn_vars[k], width=22).grid(row=0, column=i * 2 + 1, padx=4)
        ttk.Button(form, text="Create Debit Note PDF", command=self.create_debit_note).grid(row=0, column=6, padx=10)
        ttk.Button(f, text="Refresh", command=self.refresh_debit_note).pack(anchor="e")

        ttk.Label(f, text="Previous Debit Notes", style="Head.TLabel").pack(anchor="w", pady=(10, 3))
        self.dn_hist = ttk.Treeview(
            f, columns=("id", "no", "date", "party", "amount", "reason"),
            show="headings", height=6,
        )
        for c, h, w in zip(("id", "no", "date", "party", "amount", "reason"),
                           ("ID", "DN No", "Date", "Party", "Amount", "Reason"),
                           [50, 110, 100, 250, 110, 300]):
            self.dn_hist.heading(c, text=h)
            self.dn_hist.column(c, width=w)
        self.dn_hist.pack(fill="x")
        self.refresh_debit_note()

    def refresh_debit_note(self):
        if not hasattr(self, "dn_tv"):
            return
        for t in (self.dn_tv, self.dn_hist):
            for x in t.get_children():
                t.delete(x)
        con = db()
        for r in con.execute(
            """SELECT b.id,b.builty_no,d.customer_name,b.truck_no,b.date,b.qty,b.freight_amount
               FROM builtys b JOIN dos d ON d.id=b.do_id ORDER BY b.id DESC"""
        ):
            self.dn_tv.insert("", "end", values=(
                r["id"], r["builty_no"], r["customer_name"], r["truck_no"], r["date"],
                f'{r["qty"]:.3f}', f'{r["freight_amount"]:.2f}',
            ))
        for r in con.execute("SELECT * FROM debit_notes ORDER BY id DESC"):
            self.dn_hist.insert("", "end", values=(
                r["id"], r["dn_no"], r["dn_date"], r["party"],
                f'{r["amount"]:.2f}', r["reason"],
            ))
        con.close()

    def create_debit_note(self):
        sel = self.dn_tv.selection()
        if not sel:
            messagebox.showwarning("Debit Note", "Select at least one Builty row.")
            return
        rows = []
        for i in sel:
            v = self.dn_tv.item(i)["values"]
            rows.append({"id": int(v[0]), "customer": v[2], "qty": _f(v[5]), "freight": _f(v[6]),
                         "builty_no": v[1], "truck": v[3], "date": v[4]})
        customer = rows[0]["customer"]
        if any(r["customer"] != customer for r in rows):
            messagebox.showerror("Customer mismatch", "Select rows of the same customer.")
            return
        total = round(sum(r["freight"] for r in rows), 2)
        con = db()
        try:
            con.execute(
                """INSERT INTO debit_notes(dn_no,dn_date,party,amount,reason,builty_ids)
                   VALUES(?,?,?,?,?,?)""",
                (self.dn_vars["dn_no"].get().strip(),
                 self.dn_vars["dn_date"].get().strip(),
                 customer, total, self.dn_vars["reason"].get().strip(),
                 ",".join(str(r["id"]) for r in rows)),
            )
            con.commit()
        except Exception as e:
            con.close()
            messagebox.showerror("Debit Note", str(e))
            return
        con.close()

        # Produce a Debit Note PDF using the bill_pdf helper (DEBIT NOTE header)
        fake_bill = {
            "bill_no": self.dn_vars["dn_no"].get().strip() or f"DN-{total:.0f}",
            "bill_date": self.dn_vars["dn_date"].get().strip(),
            "bill_type": "FREIGHT",
            "customer_name": customer,
            "total_qty": sum(r["qty"] for r in rows),
            "rate_per_ton": 0,
            "subtotal": total,
            "cgst": 0, "sgst": 0, "igst": 0, "total": total,
        }
        builties_pdf = [{
            "builty_no": r["builty_no"], "truck_no": r["truck"], "date": r["date"],
            "qty": r["qty"], "do_no": "",
        } for r in rows]
        out = EXPORT_DIR / f"DebitNote_{fake_bill['bill_no']}.pdf"
        try:
            generate_bill_pdf(out, FIRM, fake_bill, builties_pdf)
        except Exception as e:
            messagebox.showerror("Debit Note PDF", str(e))
            self.refresh_debit_note()
            return
        if messagebox.askyesno("Debit Note PDF", f"Saved: {out.name}\n\nOpen it now?"):
            open_file(out)
        for k in self.dn_vars:
            self.dn_vars[k].set("")
        self.refresh_debit_note()

    # ===================== FREIGHT RATE TAB =====================
    def rate_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="6 · Freight Rate")
        ttk.Label(f, text="Freight Rate Master (latest effective date is used while creating Builty)",
                  style="Head.TLabel").pack(anchor="w")

        form = ttk.LabelFrame(f, text="Add / Update Rate", padding=10)
        form.pack(fill="x", pady=6)
        self.r_vars = {k: tk.StringVar() for k in ("from_place", "to_place", "material",
                                                   "rate_per_ton", "effective_date", "remarks")}
        for i, (lab, k) in enumerate([("From", "from_place"), ("To", "to_place"),
                                      ("Material", "material"), ("Rate/TON", "rate_per_ton"),
                                      ("Effective Date", "effective_date"), ("Remarks", "remarks")]):
            ttk.Label(form, text=lab).grid(row=i // 3, column=(i % 3) * 2, padx=4, pady=4, sticky="w")
            ttk.Entry(form, textvariable=self.r_vars[k], width=22).grid(row=i // 3, column=(i % 3) * 2 + 1, padx=4, pady=4)
        ttk.Button(form, text="Save Rate", command=self.save_rate).grid(row=0, column=6, rowspan=2, padx=10)
        ttk.Button(form, text="Delete Selected", command=self.delete_rate).grid(row=1, column=6, padx=10)

        self.r_tv = ttk.Treeview(
            f, columns=("id", "from", "to", "material", "rate", "date", "remarks"),
            show="headings", height=14,
        )
        for c, h, w in zip(("id", "from", "to", "material", "rate", "date", "remarks"),
                           ("ID", "From", "To", "Material", "Rate", "Effective Date", "Remarks"),
                           [50, 130, 130, 200, 90, 130, 260]):
            self.r_tv.heading(c, text=h)
            self.r_tv.column(c, width=w)
        self.r_tv.pack(fill="both", expand=True, pady=6)
        self.refresh_rates()

    def refresh_rates(self):
        if not hasattr(self, "r_tv"):
            return
        for x in self.r_tv.get_children():
            self.r_tv.delete(x)
        con = db()
        for r in con.execute("SELECT * FROM freight_rates ORDER BY id DESC"):
            self.r_tv.insert("", "end", values=(
                r["id"], r["from_place"], r["to_place"], r["material"],
                f'{r["rate_per_ton"]:.2f}', r["effective_date"], r["remarks"] or "",
            ))
        con.close()

    def save_rate(self):
        rate = _f(self.r_vars["rate_per_ton"].get())
        if rate <= 0:
            messagebox.showerror("Freight Rate", "Enter a valid rate.")
            return
        con = db()
        con.execute(
            """INSERT INTO freight_rates(from_place,to_place,material,rate_per_ton,effective_date,remarks)
               VALUES(?,?,?,?,?,?)""",
            (self.r_vars["from_place"].get().strip(),
             self.r_vars["to_place"].get().strip(),
             self.r_vars["material"].get().strip(),
             rate,
             self.r_vars["effective_date"].get().strip(),
             self.r_vars["remarks"].get().strip()),
        )
        con.commit()
        con.close()
        for k in self.r_vars:
            self.r_vars[k].set("")
        self.refresh_rates()

    def delete_rate(self):
        sel = self.r_tv.selection()
        if not sel:
            return
        rid = int(self.r_tv.item(sel[0])["values"][0])
        con = db()
        con.execute("DELETE FROM freight_rates WHERE id=?", (rid,))
        con.commit()
        con.close()
        self.refresh_rates()


if __name__ == "__main__":
    try:
        App().mainloop()
    except tk.TclError as e:
        print(f"Cannot start GUI: {e}", file=sys.stderr)
        sys.exit(1)
