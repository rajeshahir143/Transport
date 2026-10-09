# Radhe Radhe Developer — PDF ↔ DO ↔ Builty ↔ Bill

Desktop app in Python (Tkinter + SQLite) that handles the full flow:

| # | Tab | What it does |
|---|-----|--------------|
| 1 | **DO Entry** | Upload a GMDC Delivery Order PDF → auto-fill form → **Save**. Double-click any DO (or use **Edit / Update**) to modify. Remaining qty stays consistent after edits. |
| 2 | **Builty Entry** | Pick a Pending DO: Consignee, From / To, remaining qty, and Freight Rate (from master) all auto-populate. Loaded qty is deducted from the DO automatically. **Create & Print Builty** generates a SWASTIK-style PDF (Consignor / Consignee / Truck / Material / Qty / Freight / GST / Signature). Double-click any row to **re-print**. |
| 3 | **Bill (Material)** | Multi-select Pending Builty records of the **same customer**, enter Rate / TON and GST %, click **Create Bill & Print PDF**. Tax invoice PDF is produced; billed builtys disappear from pending. |
| 4 | **Freight Paid** | Record freight payment per Builty (date, amount, mode, reference). The Builty's freight status flips to "Paid". |
| 5 | **Debit Note (Freight)** | Pick builtys of one party → raise a Debit Note (Freight) PDF for the total freight amount. |
| 6 | **Freight Rate** | Master of freight rates by From / To / Material / Effective Date. The latest matching row auto-fills while creating a Builty. |

## Local database
All data lives in **`radhe_radhe.db`** right next to `main.py`. Nothing is uploaded anywhere.
Back the file up by copying it to a USB drive or network share.

## Install & run

```bash
pip install -r requirements.txt
python main.py
```

PDF outputs are saved under the `exports/` folder next to the script and can be
re-opened for printing at any time (double-click a Builty row or re-run the
Create flows).

## Firm details on printed stationery
Open `main.py` and edit the `FIRM` dictionary near the top:

```python
FIRM = {
    "name": "RADHE RADHE DEVELOPER",
    "address": "Bhavnagar, Gujarat",
    "gstin": "",
    "phone": "",
}
```

## Files

```
radhe_radhe_app/
├── main.py           # Tkinter UI & workflow
├── db.py             # SQLite schema + rate lookup
├── pdf_parser.py     # GMDC Delivery Order PDF extractor (pypdf)
├── pdf_render.py     # Builty + Bill PDFs (ReportLab, SWASTIK-style)
├── requirements.txt
└── README.md
```

## GitHub upload
Zip the whole folder (or `git init && git add . && git commit -m "init"`) and
push to your repository.
