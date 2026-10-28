"""Separate PO Builty form and B167-style PDF. Independent from DO-linked records."""
import json, re, tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from db import db

FIELDS = [
("lr_no","LR No."),("lr_date","LR Date"),("consignor_name","Consignor Name"),
("consignor_address","Consignor Address"),("consignor_gstin","Consignor GSTIN"),
("consignee_name","Consignee Name"),("consignee_address","Consignee Address"),
("consignee_gstin","Consignee GSTIN"),("invoice_no","Invoice No."),("challan_no","Challan No."),
("eway_bill_no","E-Way Bill No."),("eway_generate_date","E-Way Bill Generate Date"),
("eway_valid_date","E-Way Bill Valid Date"),("packing_list_no","Packing List No."),
("description","Description"),("total_bundle","Total Bundle"),("weight_1","Weight 1"),
("weight_2","Weight 2"),("truck_no","Truck No."),("driver_name","Driver Name"),
("driver_address","Address"),("truck_owner","Truck Owner Name"),("mobile_no","Mobile No."),
("cgst","CGST"),("sgst","SGST"),("igst","IGST"),("total","Total"),("notes","Notes / Terms")]

class POBuiltyTab:
    def __init__(self, nb, firm_getter, export_dir, open_file):
        self.firm_getter, self.export_dir, self.open_file = firm_getter, Path(export_dir), open_file
        with db() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS po_builtys(
              id INTEGER PRIMARY KEY AUTOINCREMENT, lr_no TEXT NOT NULL, lr_date TEXT,
              data_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT DEFAULT (datetime('now','localtime')),
              updated_at TEXT DEFAULT (datetime('now','localtime')))""")
        f=ttk.Frame(nb,padding=8); self.frame=f; nb.add(f,text="PO Builty")
        ttk.Label(f,text="PO Based Builty Entry",font=("Segoe UI",17,"bold"),foreground="#B22222").pack(anchor="w")
        ttk.Label(f,text="Separate PO workflow. Existing DO → Builty → Bill data and links remain unchanged.",wraplength=1000).pack(anchor="w",pady=5)
        split=ttk.Panedwindow(f,orient="horizontal"); split.pack(fill="both",expand=True)
        left=ttk.Frame(split,padding=4); right=ttk.Frame(split,padding=4)
        split.add(left,weight=3); split.add(right,weight=2)
        bar=ttk.Frame(left); bar.pack(fill="x")
        ttk.Button(bar,text="Import PO PDF",command=self.import_pdf).pack(side="left",padx=3)
        ttk.Button(bar,text="New / Clear",command=self.clear).pack(side="left",padx=3)
        self.vars={k:tk.StringVar() for k,_ in FIELDS}; self.vars["lr_date"].set(datetime.now().strftime("%d/%m/%Y"))
        self.selected_id=None
        grid=ttk.Frame(left); grid.pack(fill="both",expand=True)
        for i,(key,label) in enumerate(FIELDS):
            r,c=divmod(i,2); ttk.Label(grid,text=label).grid(row=r,column=c*2,sticky="w",padx=3,pady=3)
            ttk.Entry(grid,textvariable=self.vars[key],width=28).grid(row=r,column=c*2+1,sticky="ew",padx=3,pady=3)
        for c in range(4): grid.columnconfigure(c,weight=1)
        bar2=ttk.Frame(left); bar2.pack(fill="x",pady=6)
        ttk.Button(bar2,text="Save PO Builty",command=self.save).pack(side="left",padx=3)
        ttk.Button(bar2,text="Print / Preview PDF",command=self.print_pdf).pack(side="left",padx=3)
        ttk.Button(bar2,text="Delete Selected",command=self.delete).pack(side="left",padx=3)
        ttk.Label(right,text="Saved PO Builtys",font=("Segoe UI",11,"bold")).pack(anchor="w")
        self.tree=ttk.Treeview(right,columns=("id","lr","date","party","truck"),show="headings",height=20)
        for c,l,w in [("id","ID",40),("lr","LR No.",80),("date","LR Date",90),("party","Consignee",160),("truck","Truck No.",95)]:
            self.tree.heading(c,text=l); self.tree.column(c,width=w,anchor="w" if c=="party" else "center")
        self.tree.pack(fill="both",expand=True,pady=5); self.tree.bind("<<TreeviewSelect>>",self.load)
        self.refresh()

    def clear(self):
        self.selected_id=None
        for v in self.vars.values(): v.set("")
        self.vars["lr_date"].set(datetime.now().strftime("%d/%m/%Y"))
        for x in self.tree.selection(): self.tree.selection_remove(x)

    def import_pdf(self):
        path=filedialog.askopenfilename(title="Select PO PDF",filetypes=[("PDF files","*.pdf")])
        if not path: return
        try:
            from pypdf import PdfReader
            text="\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
            if not text.strip(): raise ValueError("PDF text could not be extracted; fill fields manually.")
            patterns={
              "lr_no":r"\bLR\s*NO\.?\s*[:#-]\s*([A-Z0-9/-]+)",
              "lr_date":r"\bLR\s*DATE\s*[:#-]\s*([0-9./-]+)",
              "invoice_no":r"INVOICE\s*NO\.?\s*[:#-]\s*([^\n]+)",
              "challan_no":r"CHALAN\s*NO\.?\s*[:#-]\s*([^\n]+)",
              "eway_bill_no":r"E[\s-]*WAY\s*BILL\s*NO\.?\s*[:#-]\s*([^\n]+)",
              "eway_generate_date":r"E[\s-]*WAY\s*BILL\s*GENERATE\s*DATE\s*[:#-]\s*([^\n]+)",
              "eway_valid_date":r"E[\s-]*WAY\s*BILL\s*VALID\s*DATE\s*[:#-]\s*([^\n]+)",
              "packing_list_no":r"PACKING\s*LIST\s*NO\.?\s*[:#-]\s*([^\n]+)",
              "consignor_gstin":r"CONSIGNOR[\s\S]{0,500}?GSTIN\s*[:#-]?\s*([0-9A-Z]{15})",
              "consignee_gstin":r"CONSIGNEE[\s\S]{0,500}?GSTIN\s*(?:NO\.?\s*)?[:#-]?\s*([0-9A-Z]{15}|URP)",
              "truck_no":r"TRUCK\s*NO\.?\s*[:#-]\s*([A-Z0-9 -]+)",
              "driver_name":r"DRIVER'?S?\s*NAME\s*[:#-]\s*([^\n]+)",
              "truck_owner":r"TRUCK\s*OWNER\s*NAME\s*[:#-]\s*([^\n]+)",
              "mobile_no":r"MOBILE\s*NO\.?\s*[:#-]\s*([0-9 +()-]+)"}
            n=0
            for key,pat in patterns.items():
                m=re.search(pat,text,re.I)
                if m: self.vars[key].set(re.sub(r"\s+"," ",m.group(1)).strip(" :\t")[:500]); n+=1
            for key,label in [("consignor_name","CONSIGNOR"),("consignee_name","CONSIGNEE")]:
                m=re.search(label+r"\s*:\s*\n?\s*([^\n]+)",text,re.I)
                if m: self.vars[key].set(m.group(1).strip()[:500]); n+=1
            messagebox.showinfo("Import PO PDF",f"Read {n} field(s). Please review fields and fill anything missing.",parent=self.frame if hasattr(self,"frame") else self.tree)
        except Exception as e: messagebox.showerror("Import PO PDF",str(e))

    def save(self):
        d={k:v.get().strip() for k,v in self.vars.items()}
        if not d["lr_no"]: messagebox.showwarning("Save PO Builty","LR No. is required."); return False
        try:
            with db() as con:
                if self.selected_id:
                    con.execute("UPDATE po_builtys SET lr_no=?,lr_date=?,data_json=?,updated_at=datetime('now','localtime') WHERE id=?",(d["lr_no"],d["lr_date"],json.dumps(d,ensure_ascii=False),self.selected_id))
                else:
                    cur=con.execute("INSERT INTO po_builtys(lr_no,lr_date,data_json) VALUES(?,?,?)",(d["lr_no"],d["lr_date"],json.dumps(d,ensure_ascii=False))); self.selected_id=cur.lastrowid
            self.refresh(); return True
        except Exception as e: messagebox.showerror("Save PO Builty",str(e)); return False

    def refresh(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        with db() as con: rows=con.execute("SELECT id,lr_no,lr_date,data_json FROM po_builtys ORDER BY id DESC").fetchall()
        for r in rows:
            d=json.loads(r["data_json"] or "{}")
            self.tree.insert("","end",values=(r["id"],r["lr_no"],r["lr_date"],d.get("consignee_name",""),d.get("truck_no","")))

    def load(self,_event=None):
        s=self.tree.selection()
        if not s:return
        self.selected_id=int(self.tree.item(s[0])["values"][0])
        with db() as con:r=con.execute("SELECT data_json FROM po_builtys WHERE id=?",(self.selected_id,)).fetchone()
        if r:
            d=json.loads(r["data_json"] or "{}")
            for k,v in self.vars.items():v.set(str(d.get(k,"")))

    def delete(self):
        s=self.tree.selection()
        if not s: messagebox.showwarning("Delete PO Builty","Select a record first."); return
        ident=int(self.tree.item(s[0])["values"][0])
        if not messagebox.askyesno("Delete PO Builty","Delete this PO Builty?"):return
        with db() as con:con.execute("DELETE FROM po_builtys WHERE id=?",(ident,))
        self.clear();self.refresh()

    def print_pdf(self):
        d={k:v.get().strip() for k,v in self.vars.items()}
        if not d["lr_no"]:messagebox.showwarning("Print PDF","Enter/import LR No. first.");return
        if not self.save():return
        from po_builty import generate_po_builty_pdf
        out=self.export_dir/("PO_Builty_"+re.sub(r"[^A-Za-z0-9_-]","_",d["lr_no"])+".pdf")
        try:generate_po_builty_pdf(out,self.firm_getter(),d)
        except Exception as e:messagebox.showerror("PO Builty PDF",str(e));return
        if messagebox.askyesno("PO Builty PDF",f"Saved {out.name}. Open to print?"):self.open_file(out)


def generate_po_builty_pdf(out_path,firm,data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer
    from xml.sax.saxutils import escape
    styles=getSampleStyleSheet()
    normal=ParagraphStyle("pon",parent=styles["Normal"],fontName="Helvetica",fontSize=7.5,leading=9,alignment=1)
    bold=ParagraphStyle("pob",parent=normal,fontName="Helvetica-Bold")
    title=ParagraphStyle("pot",parent=bold,fontSize=17,leading=19)
    sub=ParagraphStyle("pos",parent=bold,fontSize=10,leading=12)
    left=ParagraphStyle("pol",parent=normal,alignment=0)
    def p(x="",s=normal):return Paragraph(escape(str(x or "").replace("\n"," ")[:1500]),s)
    def t(rows,widths,heights=None):
        q=Table(rows,colWidths=widths,rowHeights=heights,hAlign="CENTER")
        q.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.55,colors.black),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]));return q
    name=str(firm.get("name") or "MANSI COAL CARRIER").upper()
    address=firm.get("address") or "At Post Kunriya, Tal. Bhuj-Kutch. Corr Add Office No b/h sadguru complex madhapar highway"
    story=[t([[p("|| JAY MURLIDHAR ||")],[p(name,title)],[p("TRANSPORT CONTRACTOR & COMMISSION AGENT",sub)],[p(address,bold)]],[166*mm],[5*mm,11*mm,7*mm,7*mm]),
      t([[p("LR NO : "+data.get("lr_no",""),bold),p("LR DATE : "+data.get("lr_date",""),bold)]],[83*mm,83*mm],[7*mm])]
    leftparty=[p(": CONSIGNOR :",bold),p(data.get("consignor_name",""),bold),p(data.get("consignor_address","")),p("GSTIN: "+data.get("consignor_gstin",""),bold)]
    rightparty=[p(": CONSIGNEE :",bold),p(data.get("consignee_name",""),bold),p(data.get("consignee_address","")),p("GSTIN No/Unique No : "+data.get("consignee_gstin",""),bold)]
    meta=[("INVOICE NO","invoice_no"),("CHALAN NO","challan_no"),("E WAY BILL NO","eway_bill_no"),("E WAY BILL GENERATE DATE","eway_generate_date"),("E WAY BILL VALID DATE","eway_valid_date"),("Packing list no","packing_list_no")]
    rightmeta=t([[p(label+" : "+data.get(key,""),left)] for label,key in meta],[83*mm])
    parties=Table([[t([[x] for x in leftparty],[83*mm]),rightmeta],[t([[x] for x in rightparty],[83*mm]),""]],colWidths=[83*mm,83*mm],rowHeights=[30*mm,28*mm])
    parties.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.55,colors.black),("SPAN",(1,1),(1,1)),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(parties)
    weights=" / ".join(x for x in (data.get("weight_1",""),data.get("weight_2","")) if x)
    story.append(t([[p("NO",bold),p("DESCRIPTION",bold),p("TOTAL BUNDLE",bold),p("TOTAL WEIGHT",bold)],[p("1",bold),p(data.get("description","")),p(data.get("total_bundle","")),p(weights)],[p("SUB TOTAL",bold),"",p(data.get("total_bundle",""),bold),p(weights,bold)]],[27*mm,76*mm,28*mm,35*mm],[11*mm,31*mm,7*mm]))
    truck=Table([[p("Truck No :",bold),p(data.get("truck_no",""),bold),p("CGST : "+data.get("cgst",""),bold)],[p("Drivers Name",bold),p(data.get("driver_name","")),p("SGST : "+data.get("sgst",""),bold)],[p("Address",bold),p(data.get("driver_address","")),p("IGST : "+data.get("igst",""),bold)],[p("Truck Owner Name",bold),p(data.get("truck_owner","")),p("TOTAL : "+data.get("total",""),bold)],[p("Mobile No",bold),p(data.get("mobile_no","")),p("",bold)]],colWidths=[27*mm,76*mm,63*mm],rowHeights=[7*mm]*5)
    truck.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.8,colors.black),("INNERGRID",(0,0),(-1,-1),0.55,colors.black),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.extend([truck,Spacer(1,2*mm),t([[p(data.get("notes") or "* 1% SHORTAGE ALLOWED. WE ARE NOT RESPONSIBLE FOR QUALITY MATERIAL DIRECT LOADING FROM COMPANY",left),p("For : "+name,bold)]],[105*mm,61*mm],[15*mm])])
    doc=SimpleDocTemplate(str(out_path),pagesize=A4,leftMargin=22*mm,rightMargin=22*mm,topMargin=18*mm,bottomMargin=18*mm)
    doc.build(story);return str(out_path)
