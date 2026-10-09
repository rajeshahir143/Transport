"""Radhe Radhe Developer — Desktop app (Tkinter + SQLite).

Workflow:
    PDF -> DO (auto-fill, Save, Edit/Update)
    DO -> Builty (pending DO, remaining qty auto, SWASTIK-style PDF print)
    Builty -> Bill (multi-select same party, Material + GST)
    Freight Paid / Debit Note (Freight) / Freight Rate Master
Data is stored locally in radhe_radhe.db next to this script.
"""
import os
import platform
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from db import db, init_db, lookup_rate, DB_PATH
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
        ttk.Label(top, text=f"DB: {DB_PATH.name}",
                  font=("Segoe UI", 9), foreground="#666").pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=5)
        self.do_tab(nb)
        self.builty_tab(nb)
        self.bill_tab(nb)
        self.freight_paid_tab(nb)
        self.debit_note_tab(nb)
        self.rate_tab(nb)

    # ===================== DO TAB =====================
    def do_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="1 · DO Entry")
        bar = ttk.Frame(f)
        bar.pack(fill="x")
        ttk.Button(bar, text="Upload PDF → Create DO", command=self.upload_pdf).pack(side="left")
        ttk.Button(bar, text="Edit / Update Selected", command=self.edit_do).pack(side="left", padx=6)
        ttk.Button(bar, text="Delete Selected", command=self.delete_do).pack(side="left")
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

    def refresh_do(self):
        if not hasattr(self, "dot"):
            return
        for x in self.dot.get_children():
            self.dot.delete(x)
        con = db()
        for r in con.execute("SELECT * FROM dos ORDER BY id DESC"):
            self.dot.insert("", "end", values=(
                r["id"], r["do_no"], r["do_date"], r["customer_name"], r["material"],
                f'{r["qty"]:.3f}', f'{r["remaining_qty"]:.3f}', r["transporter_name"],
                r["to_place"] or "",
            ))
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
        if not d.get("do_no"):
            messagebox.showerror("PDF Import", "DO / Order Number could not be detected.")
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
        con.close()
        if row:
            self._do_form(data=dict(row), existing_id=do_id)

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
            ("do_no", "DO No"), ("do_date", "DO Date"),
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
            v = tk.StringVar(value=str(data.get(k) or ""))
            vars_[k] = v
            ttk.Entry(frm, textvariable=v, width=32).grid(row=i // 2, column=(i % 2) * 2 + 1, padx=5, pady=3)

        def save():
            vals = {k: vars_[k].get().strip() for k, _ in fields}
            qty = _f(vals["qty"])
            try:
                con = db()
                if existing_id:
                    # keep remaining_qty consistent: adjust by delta if qty changed
                    prev = con.execute("SELECT qty, remaining_qty FROM dos WHERE id=?",
                                       (existing_id,)).fetchone()
                    used = _f(prev["qty"]) - _f(prev["remaining_qty"])
                    new_remaining = max(qty - used, 0)
                    con.execute(
                        """UPDATE dos SET do_no=?, do_date=?, customer_no=?, customer_name=?,
                           customer_gstin=?, order_type=?, bill_to=?, ship_to=?, state=?, hsn=?,
                           material=?, schedule_date=?, qty=?, uom=?, unit_price=?, extended_price=?,
                           transporter_code=?, transporter_name=?, order_total=?,
                           from_place=?, to_place=?, remaining_qty=?
                           WHERE id=?""",
                        (vals["do_no"], vals["do_date"], vals["customer_no"], vals["customer_name"],
                         vals["customer_gstin"], vals["order_type"], vals["bill_to"], vals["ship_to"],
                         vals["state"], vals["hsn"], vals["material"], vals["schedule_date"],
                         qty, vals["uom"], _f(vals["unit_price"]), _f(vals["extended_price"]),
                         vals["transporter_code"], vals["transporter_name"], _f(vals["order_total"]),
                         vals["from_place"], vals["to_place"], new_remaining, existing_id),
                    )
                else:
                    con.execute(
                        """INSERT INTO dos(do_no,do_date,customer_no,customer_name,customer_gstin,
                           order_type,bill_to,ship_to,state,hsn,material,schedule_date,qty,uom,
                           unit_price,extended_price,transporter_code,transporter_name,order_total,
                           from_place,to_place,remaining_qty,source_pdf)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (vals["do_no"], vals["do_date"], vals["customer_no"], vals["customer_name"],
                         vals["customer_gstin"], vals["order_type"], vals["bill_to"], vals["ship_to"],
                         vals["state"], vals["hsn"], vals["material"], vals["schedule_date"],
                         qty, vals["uom"], _f(vals["unit_price"]), _f(vals["extended_price"]),
                         vals["transporter_code"], vals["transporter_name"], _f(vals["order_total"]),
                         vals["from_place"], vals["to_place"], qty, source_pdf or ""),
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
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="2 · Builty Entry")
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Pending DO (select to auto-fill Builty)", style="Head.TLabel").pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh_builty).pack(side="right")

        cols = ("id", "do_no", "customer", "material", "remaining", "to_place")
        self.pd = ttk.Treeview(f, columns=cols, show="headings", height=8, selectmode="browse")
        for c, h, w in zip(cols, ["ID", "DO No", "Customer", "Material", "Pending Qty", "To"],
                           [50, 110, 230, 220, 110, 150]):
            self.pd.heading(c, text=h)
            self.pd.column(c, width=w)
        self.pd.pack(fill="x", pady=6)
        self.pd.bind("<<TreeviewSelect>>", self._on_pending_do_select)

        form = ttk.LabelFrame(f, text="Create Builty", padding=10)
        form.pack(fill="x", pady=8)
        self.b_vars = {k: tk.StringVar() for k in (
            "builty_no", "truck_no", "date", "qty",
            "from_place", "to_place", "consignee", "driver_name",
            "ewaybill", "freight_rate", "freight_amount", "remarks",
        )}
        layout = [
            ("Builty No", "builty_no"), ("Date", "date"), ("Truck No", "truck_no"),
            ("Loaded Qty (TON)", "qty"), ("From", "from_place"), ("To", "to_place"),
            ("Consignee", "consignee"), ("Driver", "driver_name"), ("E-Way Bill", "ewaybill"),
            ("Freight Rate/TON", "freight_rate"), ("Freight Amount", "freight_amount"), ("Remarks", "remarks"),
        ]
        for i, (lab, k) in enumerate(layout):
            ttk.Label(form, text=lab).grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=4, sticky="w")
            e = ttk.Entry(form, textvariable=self.b_vars[k], width=18)
            e.grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=4)
            if k in ("qty", "freight_rate"):
                self.b_vars[k].trace_add("write", lambda *_: self._recalc_freight())

        btn_row = ttk.Frame(form)
        btn_row.grid(row=3, column=0, columnspan=8, pady=6, sticky="e")
        ttk.Button(btn_row, text="Create & Print Builty", command=self.create_builty).pack(side="right")

        ttk.Label(f, text="Recent Builty (double-click to re-print PDF)", style="Head.TLabel").pack(anchor="w", pady=(10, 3))
        bcols = ("id", "no", "do", "truck", "date", "qty", "freight", "billed", "paid")
        self.bt = ttk.Treeview(f, columns=bcols, show="headings", height=10)
        for c, h, w in zip(bcols, ("ID", "Builty No", "DO No", "Truck", "Date", "Qty", "Freight", "Bill", "Freight Paid"),
                           [50, 110, 100, 110, 95, 85, 95, 85, 110]):
            self.bt.heading(c, text=h)
            self.bt.column(c, width=w)
        self.bt.pack(fill="both", expand=True)
        self.bt.bind("<Double-1>", lambda _e: self.reprint_builty())
        self.refresh_builty()

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
        self.b_vars["from_place"].set(row["from_place"] or "BHAVNAGAR")
        self.b_vars["to_place"].set(row["to_place"] or "")
        self.b_vars["consignee"].set(row["customer_name"] or "")
        if not self.b_vars["qty"].get():
            self.b_vars["qty"].set(f"{pending:.3f}")
        rate = lookup_rate(row["from_place"], row["to_place"], row["material"])
        if rate and not self.b_vars["freight_rate"].get():
            self.b_vars["freight_rate"].set(f"{rate:.2f}")
        self._recalc_freight()

    def _recalc_freight(self):
        q = _f(self.b_vars["qty"].get())
        r = _f(self.b_vars["freight_rate"].get())
        self.b_vars["freight_amount"].set(f"{q * r:.2f}")

    def refresh_builty(self):
        if not hasattr(self, "pd"):
            return
        for t in (self.pd, self.bt):
            for x in t.get_children():
                t.delete(x)
        con = db()
        for r in con.execute(
            "SELECT id,do_no,customer_name,material,remaining_qty,to_place "
            "FROM dos WHERE remaining_qty>0.000001 ORDER BY id DESC"
        ):
            self.pd.insert("", "end", values=(
                r["id"], r["do_no"], r["customer_name"], r["material"],
                f'{r["remaining_qty"]:.3f}', r["to_place"] or "",
            ))
        for r in con.execute(
            """SELECT b.id,b.builty_no,d.do_no,b.truck_no,b.date,b.qty,
                      b.freight_amount,b.billed,b.freight_paid
               FROM builtys b JOIN dos d ON d.id=b.do_id ORDER BY b.id DESC"""
        ):
            self.bt.insert("", "end", values=(
                r["id"], r["builty_no"], r["do_no"], r["truck_no"], r["date"],
                f'{r["qty"]:.3f}', f'{r["freight_amount"]:.2f}',
                "Billed" if r["billed"] else "Pending",
                "Paid" if r["freight_paid"] else "Due",
            ))
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

    def reprint_builty(self):
        sel = self.bt.selection()
        if not sel:
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
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="3 · Bill (Material)")
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Pending Builty — select multiple of same party",
                  style="Head.TLabel").pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh_bill).pack(side="right")

        self.pb = ttk.Treeview(
            f, columns=("id", "builty", "do", "customer", "truck", "date", "qty"),
            show="headings", selectmode="extended", height=12,
        )
        for c, h, w in zip(
            ("id", "builty", "do", "customer", "truck", "date", "qty"),
            ["ID", "Builty No", "DO No", "Customer", "Truck", "Date", "Qty"],
            [50, 110, 100, 260, 120, 100, 100],
        ):
            self.pb.heading(c, text=h)
            self.pb.column(c, width=w)
        self.pb.pack(fill="both", expand=True, pady=8)
        self.pb.bind("<<TreeviewSelect>>", self.update_selected_total)

        form = ttk.LabelFrame(f, text="Bill Details", padding=10)
        form.pack(fill="x", pady=6)
        self.bill_vars = {k: tk.StringVar() for k in
                          ("bill_no", "bill_date", "rate_per_ton", "cgst_pct", "sgst_pct", "igst_pct")}
        self.bill_vars["cgst_pct"].set("0")
        self.bill_vars["sgst_pct"].set("0")
        self.bill_vars["igst_pct"].set("5")
        pairs = [
            ("Bill No", "bill_no"), ("Bill Date", "bill_date"),
            ("Rate / TON", "rate_per_ton"),
            ("CGST %", "cgst_pct"), ("SGST %", "sgst_pct"), ("IGST %", "igst_pct"),
        ]
        for i, (lab, k) in enumerate(pairs):
            ttk.Label(form, text=lab).grid(row=0, column=i * 2, padx=4, pady=4, sticky="w")
            ttk.Entry(form, textvariable=self.bill_vars[k], width=14).grid(row=0, column=i * 2 + 1, padx=4, pady=4)

        bottom = ttk.Frame(f)
        bottom.pack(fill="x")
        self.bill_total = tk.StringVar(value="Selected Qty: 0.000 TON")
        ttk.Label(bottom, textvariable=self.bill_total, font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)
        ttk.Button(bottom, text="Create Bill & Print PDF", command=self.create_bill).pack(side="right")

        self.refresh_bill()

    def refresh_bill(self):
        if not hasattr(self, "pb"):
            return
        for x in self.pb.get_children():
            self.pb.delete(x)
        con = db()
        for r in con.execute(
            """SELECT b.id,b.builty_no,d.do_no,d.customer_name,b.truck_no,b.date,b.qty
               FROM builtys b JOIN dos d ON d.id=b.do_id
               WHERE b.billed=0 ORDER BY b.id DESC"""
        ):
            self.pb.insert("", "end", values=(
                r["id"], r["builty_no"], r["do_no"], r["customer_name"],
                r["truck_no"], r["date"], f'{r["qty"]:.3f}',
            ))
        con.close()
        self.update_selected_total()

    def update_selected_total(self, _e=None):
        total = 0.0
        for i in self.pb.selection():
            v = self.pb.item(i)["values"]
            if v:
                total += _f(v[6])
        self.bill_total.set(f"Selected Qty: {total:.3f} TON")

    def create_bill(self):
        sel = self.pb.selection()
        if not sel:
            messagebox.showwarning("Select Builty", "Select one or more pending Builty records.")
            return
        rows = []
        for i in sel:
            v = self.pb.item(i)["values"]
            rows.append({"id": int(v[0]), "customer": v[3], "qty": _f(v[6])})
        customer = rows[0]["customer"]
        if any(r["customer"] != customer for r in rows):
            messagebox.showerror("Customer mismatch", "Select Builty records of the same customer.")
            return
        total_qty = sum(r["qty"] for r in rows)
        rate = _f(self.bill_vars["rate_per_ton"].get())
        sub = round(total_qty * rate, 2)
        cgst = round(sub * _f(self.bill_vars["cgst_pct"].get()) / 100, 2)
        sgst = round(sub * _f(self.bill_vars["sgst_pct"].get()) / 100, 2)
        igst = round(sub * _f(self.bill_vars["igst_pct"].get()) / 100, 2)
        total = round(sub + cgst + sgst + igst, 2)

        con = db()
        try:
            cur = con.execute(
                """INSERT INTO bills(bill_no,bill_date,bill_type,customer_name,total_qty,
                   rate_per_ton,subtotal,cgst,sgst,igst,total)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (self.bill_vars["bill_no"].get().strip(),
                 self.bill_vars["bill_date"].get().strip(),
                 "MATERIAL", customer, total_qty, rate, sub, cgst, sgst, igst, total),
            )
            bill_id = cur.lastrowid
            for r in rows:
                con.execute("INSERT INTO bill_builtys(bill_id,builty_id) VALUES(?,?)",
                            (bill_id, r["id"]))
                con.execute("UPDATE builtys SET billed=1 WHERE id=?", (r["id"],))
            con.commit()
        except Exception as e:
            con.close()
            messagebox.showerror("Bill", str(e))
            return

        bill_row = dict(con.execute("SELECT * FROM bills WHERE id=?", (bill_id,)).fetchone())
        gstin_row = con.execute(
            "SELECT customer_gstin FROM dos d JOIN builtys b ON b.do_id=d.id WHERE b.id=?",
            (rows[0]["id"],)
        ).fetchone()
        bill_row["customer_gstin"] = gstin_row["customer_gstin"] if gstin_row else ""
        builty_rows = []
        for r in rows:
            br = con.execute(
                """SELECT b.builty_no,b.truck_no,b.date,b.qty,d.do_no FROM builtys b
                   JOIN dos d ON d.id=b.do_id WHERE b.id=?""",
                (r["id"],),
            ).fetchone()
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
