import re, sqlite3, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

APP = "Radhe Radhe Developer - PDF DO / Builty / Bill"
BASE = Path(__file__).resolve().parent
DB = BASE / "radhe_radhe.db"

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS dos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        do_no TEXT UNIQUE, do_date TEXT, customer_no TEXT, customer_name TEXT,
        customer_gstin TEXT, order_type TEXT, bill_to TEXT, ship_to TEXT,
        state TEXT, hsn TEXT, material TEXT, schedule_date TEXT,
        qty REAL DEFAULT 0, uom TEXT, unit_price REAL DEFAULT 0,
        extended_price REAL DEFAULT 0, transporter_code TEXT,
        transporter_name TEXT, order_total REAL DEFAULT 0,
        remaining_qty REAL DEFAULT 0, source_pdf TEXT
    );
    CREATE TABLE IF NOT EXISTS builtys(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        builty_no TEXT UNIQUE, do_id INTEGER NOT NULL, truck_no TEXT,
        date TEXT, qty REAL NOT NULL DEFAULT 0, remarks TEXT,
        billed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(do_id) REFERENCES dos(id)
    );
    CREATE TABLE IF NOT EXISTS bills(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bill_no TEXT UNIQUE, bill_date TEXT, customer_name TEXT,
        total_qty REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS bill_builtys(
        bill_id INTEGER NOT NULL, builty_id INTEGER NOT NULL,
        PRIMARY KEY(bill_id,builty_id),
        FOREIGN KEY(bill_id) REFERENCES bills(id),
        FOREIGN KEY(builty_id) REFERENCES builtys(id)
    );
    """)
    con.commit(); con.close()

def num(s):
    if s is None: return 0.0
    s = str(s).replace(",", "").strip()
    try: return float(re.search(r"-?\d+(?:\.\d+)?", s).group())
    except: return 0.0

def parse_pdf(path):
    if PdfReader is None:
        raise RuntimeError("Install pypdf first: pip install pypdf")
    text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    def grab(pattern, default=""):
        m = re.search(pattern, text, re.I|re.M)
        return m.group(1).strip() if m else default
    data = {
        "do_no": grab(r"Order Number\s+([0-9]+)", grab(r"Delivery Order\s*\*([0-9]+)\*")),
        "do_date": grab(r"Order Date\s+([0-9A-Z-]+)"),
        "customer_no": grab(r"Customer Number\s*[\r\n]+([0-9]+)"),
        "customer_name": grab(r"Customer Name\s*[\r\n]+(.+?)\s*[\r\n]+(?:Customer GSTIN|24[A-Z0-9]+)"),
        "customer_gstin": grab(r"Customer GSTIN\s*[\r\n]+([0-9A-Z]+)"),
        "order_type": grab(r"Order Type\s+(.+?)(?:\r?\n|$)"),
        "state": grab(r"State\s*:\s*([A-Z ]+?)\s+HSN"),
        "hsn": grab(r"HSN Code\s*:\s*([0-9]+)"),
        "material": grab(r"Description of Goods\s*:\s*(.+?)(?:\r?\n|$)"),
        "schedule_date": grab(r"\d+\s+BHAVNAGAR.*?\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\s+31\s+TON", ""),
        "transporter_code": grab(r"Transporter Code\s*:\s*([A-Z0-9]+)"),
        "transporter_name": grab(r"Transporter Name\s*:\s*(.+?)(?:\r?\n|$)"),
    }
    m = re.search(r"\n?1\s+(.+?)\s+([0-9]{2}-[A-Z]{3}-[0-9]{2})\s+([0-9.]+)\s+([A-Z]+)\s+([0-9.]+)\s+([0-9.]+)", text, re.I)
    if m:
        data["material"] = data["material"] or m.group(1).strip()
        data["schedule_date"] = data["schedule_date"] or m.group(2)
        data["qty"] = num(m.group(3)); data["uom"] = m.group(4)
        data["unit_price"] = num(m.group(5)); data["extended_price"] = num(m.group(6))
    else:
        data["qty"] = num(grab(r"Total Qty:\s*([0-9.]+)"))
        data["uom"] = "TON"
    data["order_total"] = num(grab(r"ORDER TOTAL\s+([0-9.]+)"))
    return data

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP); self.geometry("1180x700"); self.minsize(1050,620)
        init_db(); self.style()
        self.build()

    def style(self):
        s=ttk.Style(self)
        try: s.theme_use("clam")
        except: pass
        s.configure("Title.TLabel",font=("Segoe UI",18,"bold"))
        s.configure("Head.TLabel",font=("Segoe UI",11,"bold"))

    def build(self):
        top=ttk.Frame(self,padding=12); top.pack(fill="x")
        ttk.Label(top,text="Radhe Radhe Developer",style="Title.TLabel").pack(side="left")
        ttk.Label(top,text="  PDF → DO → Builty → Bill",font=("Segoe UI",11)).pack(side="left")
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=10,pady=5)
        self.do_tab(nb); self.builty_tab(nb); self.bill_tab(nb)

    def do_tab(self,nb):
        f=ttk.Frame(nb,padding=10); nb.add(f,text="DO Entry")
        bar=ttk.Frame(f); bar.pack(fill="x")
        ttk.Button(bar,text="Upload PDF → Create DO",command=self.upload_pdf).pack(side="left")
        ttk.Button(bar,text="Refresh",command=self.refresh_do).pack(side="left",padx=6)
        cols=("do_no","date","customer","material","qty","remaining","transporter")
        self.dot=ttk.Treeview(f,columns=cols,show="headings",height=20)
        heads=["DO No","Date","Customer","Material","DO Qty","Remaining","Transporter"]
        for c,h in zip(cols,heads):
            self.dot.heading(c,text=h); self.dot.column(c,width=145)
        self.dot.pack(fill="both",expand=True,pady=10); self.refresh_do()

    def refresh_do(self):
        if not hasattr(self,"dot"): return
        for x in self.dot.get_children(): self.dot.delete(x)
        con=db()
        for r in con.execute("SELECT * FROM dos ORDER BY id DESC"):
            self.dot.insert("", "end", values=(r["do_no"],r["do_date"],r["customer_name"],r["material"],f'{r["qty"]:.3f}',f'{r["remaining_qty"]:.3f}',r["transporter_name"]))
        con.close()

    def upload_pdf(self):
        p=filedialog.askopenfilename(filetypes=[("PDF files","*.pdf")])
        if not p: return
        try: d=parse_pdf(p)
        except Exception as e:
            messagebox.showerror("PDF Import",str(e)); return
        if not d.get("do_no"):
            messagebox.showerror("PDF Import","DO / Order Number could not be detected."); return
        con=db()
        try:
            con.execute("""INSERT INTO dos(do_no,do_date,customer_no,customer_name,customer_gstin,order_type,
            state,hsn,material,schedule_date,qty,uom,unit_price,extended_price,transporter_code,
            transporter_name,order_total,remaining_qty,source_pdf)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["do_no"],d["do_date"],d["customer_no"],d["customer_name"],d["customer_gstin"],d["order_type"],
             d["state"],d["hsn"],d["material"],d["schedule_date"],d["qty"],d["uom"],d["unit_price"],
             d["extended_price"],d["transporter_code"],d["transporter_name"],d["order_total"],d["qty"],p))
            con.commit(); messagebox.showinfo("DO Created",f'DO {d["do_no"]} created.\nQty: {d["qty"]:.3f} {d["uom"]}')
        except sqlite3.IntegrityError:
            messagebox.showwarning("Already exists","This DO is already imported.")
        finally:
            con.close()
        self.refresh_do(); self.refresh_builty()

    def builty_tab(self,nb):
        f=ttk.Frame(nb,padding=10); nb.add(f,text="Builty Entry")
        top=ttk.Frame(f); top.pack(fill="x")
        ttk.Label(top,text="Pending DO",style="Head.TLabel").pack(side="left")
        ttk.Button(top,text="Refresh",command=self.refresh_builty).pack(side="right")
        cols=("id","do_no","customer","material","remaining")
        self.pd=ttk.Treeview(f,columns=cols,show="headings",height=9,selectmode="browse")
        for c,h,w in zip(cols,["ID","DO No","Customer","Material","Pending Qty"],[60,170,240,220,120]):
            self.pd.heading(c,text=h); self.pd.column(c,width=w)
        self.pd.pack(fill="x",pady=6)
        form=ttk.LabelFrame(f,text="Create Builty",padding=10); form.pack(fill="x",pady=8)
        self.b_no=tk.StringVar(); self.truck=tk.StringVar(); self.b_date=tk.StringVar(); self.b_qty=tk.StringVar()
        for i,(lab,var) in enumerate([("Builty No",self.b_no),("Truck No",self.truck),("Date",self.b_date),("Loaded Qty (TON)",self.b_qty)]):
            ttk.Label(form,text=lab).grid(row=0,column=i*2,padx=5,pady=5,sticky="w")
            ttk.Entry(form,textvariable=var,width=18).grid(row=0,column=i*2+1,padx=5,pady=5)
        ttk.Button(form,text="Create Builty",command=self.create_builty).grid(row=0,column=8,padx=10)
        ttk.Label(f,text="Recent Builty",style="Head.TLabel").pack(anchor="w",pady=(10,3))
        self.bt=ttk.Treeview(f,columns=("no","do","truck","qty","billed"),show="headings",height=10)
        for c,h in zip(("no","do","truck","qty","billed"),("Builty No","DO No","Truck","Qty","Bill Status")):
            self.bt.heading(c,text=h); self.bt.column(c,width=150)
        self.bt.pack(fill="both",expand=True); self.refresh_builty()

    def refresh_builty(self):
        if not hasattr(self,"pd"): return
        for t in (self.pd,self.bt):
            for x in t.get_children(): t.delete(x)
        con=db()
        for r in con.execute("SELECT id,do_no,customer_name,material,remaining_qty FROM dos WHERE remaining_qty>0.000001 ORDER BY id DESC"):
            self.pd.insert("", "end", values=(r["id"],r["do_no"],r["customer_name"],r["material"],f'{r["remaining_qty"]:.3f}'))
        for r in con.execute("""SELECT b.builty_no,d.do_no,b.truck_no,b.qty,b.billed
                                FROM builtys b JOIN dos d ON d.id=b.do_id ORDER BY b.id DESC"""):
            self.bt.insert("", "end", values=(r["builty_no"],r["do_no"],r["truck_no"],f'{r["qty"]:.3f}',"Billed" if r["billed"] else "Pending"))
        con.close()

    def create_builty(self):
        sel=self.pd.selection()
        if not sel: messagebox.showwarning("Select DO","Select a pending DO first."); return
        try: qty=float(self.b_qty.get())
        except: messagebox.showerror("Qty","Enter valid loaded quantity."); return
        if qty<=0: messagebox.showerror("Qty","Quantity must be greater than zero."); return
        row=self.pd.item(sel[0])["values"]; doid=int(row[0]); pending=float(row[4])
        if qty>pending+1e-9:
            messagebox.showerror("Qty exceeded",f"Maximum available is {pending:.3f} TON."); return
        con=db()
        try:
            con.execute("INSERT INTO builtys(builty_no,do_id,truck_no,date,qty) VALUES(?,?,?,?,?)",
                        (self.b_no.get().strip(),doid,self.truck.get().strip(),self.b_date.get().strip(),qty))
            con.execute("UPDATE dos SET remaining_qty=remaining_qty-? WHERE id=?",(qty,doid))
            con.commit()
        except sqlite3.IntegrityError:
            messagebox.showerror("Builty","Builty number already exists.")
        finally: con.close()
        self.refresh_builty(); self.refresh_do()

    def bill_tab(self,nb):
        f=ttk.Frame(nb,padding=10); nb.add(f,text="Bill (Material) Entry")
        top=ttk.Frame(f); top.pack(fill="x")
        ttk.Label(top,text="Pending Builty — Multiple Selection",style="Head.TLabel").pack(side="left")
        ttk.Button(top,text="Refresh",command=self.refresh_bill).pack(side="right")
        self.pb=ttk.Treeview(f,columns=("id","builty","do","customer","truck","qty"),show="headings",selectmode="extended",height=15)
        for c,h,w in zip(("id","builty","do","customer","truck","qty"),["ID","Builty No","DO No","Customer","Truck","Qty"],[60,130,160,250,140,100]):
            self.pb.heading(c,text=h); self.pb.column(c,width=w)
        self.pb.pack(fill="both",expand=True,pady=8)
        bottom=ttk.Frame(f); bottom.pack(fill="x")
        self.bill_no=tk.StringVar(); self.bill_date=tk.StringVar()
        ttk.Label(bottom,text="Bill No").pack(side="left"); ttk.Entry(bottom,textvariable=self.bill_no,width=18).pack(side="left",padx=5)
        ttk.Label(bottom,text="Bill Date").pack(side="left"); ttk.Entry(bottom,textvariable=self.bill_date,width=15).pack(side="left",padx=5)
        ttk.Button(bottom,text="Create Bill from Selected Builty",command=self.create_bill).pack(side="right")
        self.bill_total=tk.StringVar(value="Selected Qty: 0.000 TON")
        ttk.Label(bottom,textvariable=self.bill_total,font=("Segoe UI",11,"bold")).pack(side="right",padx=15)
        self.pb.bind("<<TreeviewSelect>>",self.update_selected_total)
        self.refresh_bill()

    def refresh_bill(self):
        if not hasattr(self,"pb"): return
        for x in self.pb.get_children(): self.pb.delete(x)
        con=db()
        for r in con.execute("""SELECT b.id,b.builty_no,d.do_no,d.customer_name,b.truck_no,b.qty
                                FROM builtys b JOIN dos d ON d.id=b.do_id
                                WHERE b.billed=0 ORDER BY b.id DESC"""):
            self.pb.insert("", "end", values=(r["id"],r["builty_no"],r["do_no"],r["customer_name"],r["truck_no"],f'{r["qty"]:.3f}'))
        con.close(); self.update_selected_total()

    def update_selected_total(self,event=None):
        total=0
        if hasattr(self,"pb"):
            for i in self.pb.selection():
                v=self.pb.item(i)["values"]
                if v: total += float(v[5])
        if hasattr(self,"bill_total"): self.bill_total.set(f"Selected Qty: {total:.3f} TON")

    def create_bill(self):
        sel=self.pb.selection()
        if not sel: messagebox.showwarning("Select Builty","Select one or more pending Builty records."); return
        con=db()
        rows=[]
        for i in sel:
            v=self.pb.item(i)["values"]; rows.append((int(v[0]),float(v[5]),v[3]))
        total=sum(x[1] for x in rows); customer=rows[0][2]
        if any(x[2]!=customer for x in rows):
            messagebox.showerror("Customer mismatch","Select Builty records of the same customer.")
            con.close(); return
        try:
            cur=con.execute("INSERT INTO bills(bill_no,bill_date,customer_name,total_qty) VALUES(?,?,?,?)",
                            (self.bill_no.get().strip(),self.bill_date.get().strip(),customer,total))
            bid=cur.lastrowid
            for bidty,qty,_ in rows:
                con.execute("INSERT INTO bill_builtys(bill_id,builty_id) VALUES(?,?)",(bid,bidty))
                con.execute("UPDATE builtys SET billed=1 WHERE id=?",(bidty,))
            con.commit()
            messagebox.showinfo("Bill Created",f"Bill created successfully.\nBuilty: {len(rows)}\nTotal Qty: {total:.3f} TON")
        except sqlite3.IntegrityError:
            messagebox.showerror("Bill","Bill number already exists.")
        finally: con.close()
        self.refresh_bill(); self.refresh_builty()

if __name__=="__main__":
    App().mainloop()
