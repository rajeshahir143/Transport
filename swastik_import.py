"""Safe SWASTIK DBF importer for company folders E/K/N/R/S (standard library only)."""
import datetime
import struct
from pathlib import Path

COMPANY_CODES = ("E", "K", "N", "R", "S")


def _case_path(folder, filename):
    folder = Path(folder)
    exact = folder / filename
    if exact.is_file():
        return exact
    try:
        for child in folder.iterdir():
            if child.name.casefold() == filename.casefold() and child.is_file():
                return child
    except OSError:
        pass
    return exact


def read_dbf(path):
    """Yield active (non-deleted) DBF rows as dictionaries."""
    with Path(path).open("rb") as stream:
        header = stream.read(32)
        if len(header) != 32:
            raise ValueError("Invalid DBF header: " + str(path))
        count = struct.unpack_from("<I", header, 4)[0]
        header_len = struct.unpack_from("<H", header, 8)[0]
        record_len = struct.unpack_from("<H", header, 10)[0]
        if header_len < 33 or record_len < 1:
            raise ValueError("Invalid DBF dimensions: " + str(path))
        fields, pos = [], 32
        while pos < header_len:
            stream.seek(pos)
            desc = stream.read(32)
            if not desc or desc[0] == 0x0D:
                break
            name = desc[:11].split(b"\0", 1)[0].decode("ascii", "replace").strip().upper()
            typ, length, decimals = chr(desc[11]), desc[16], desc[17]
            if not name or not length:
                raise ValueError("Invalid DBF field descriptor: " + str(path))
            fields.append((name, typ, length, decimals))
            pos += 32
        if not fields:
            raise ValueError("No DBF fields found: " + str(path))
        stream.seek(header_len)
        for _ in range(count):
            row = stream.read(record_len)
            if len(row) != record_len:
                break
            if row[:1] == b"*":
                continue
            offset, record = 1, {}
            for name, typ, length, decimals in fields:
                raw = row[offset:offset + length]
                offset += length
                if typ in ("C", "M"):
                    value = raw.decode("cp1252", "replace").rstrip("\x00 ")
                elif typ in ("N", "F"):
                    text = raw.decode("ascii", "ignore").strip()
                    try:
                        value = float(text) if text else 0
                        if decimals == 0 and float(value).is_integer():
                            value = int(value)
                    except ValueError:
                        value = 0
                elif typ == "D":
                    text = raw.decode("ascii", "ignore")
                    value = (text[:4] + "-" + text[4:6] + "-" + text[6:8]
                             if len(text) == 8 and text.isdigit() and text != "00000000" else "")
                elif typ == "L":
                    value = raw.upper() in (b"Y", b"T")
                else:
                    value = raw.decode("cp1252", "replace").rstrip("\x00 ")
                record[name] = value
            yield record


def _num(value):
    try:
        return int(float(value or 0))
    except (ValueError, TypeError):
        return 0


def _text(value):
    return str(value or "").strip()


def _data_dir(folder):
    folder = Path(folder)
    if _case_path(folder, "DO1.DBF").is_file() and _case_path(folder, "BUILTY.DBF").is_file():
        return folder
    for base in (folder / "DO_SOFT", folder):
        for code in COMPANY_CODES:
            data = base / code / "DATA"
            if _case_path(data, "DO1.DBF").is_file() and _case_path(data, "BUILTY.DBF").is_file():
                return base
    raise FileNotFoundError("Select the extracted SWASTIK folder containing DO_SOFT/E, K, N, R and S/DATA.")


def discover_companies(folder):
    folder = Path(folder)
    root = _data_dir(folder)
    if root.name.upper() == "DATA":
        return {root.parent.name.upper(): root}
    base = root if root.name.upper() == "DO_SOFT" else root / "DO_SOFT"
    found = {}
    for code in COMPANY_CODES:
        data = base / code / "DATA"
        if _case_path(data, "DO1.DBF").is_file() and _case_path(data, "BUILTY.DBF").is_file():
            found[code] = data
    if not found:
        raise FileNotFoundError("No valid E/K/N/R/S company DATA folders found.")
    return found


def _lookup(data_dir, filename, key, value):
    path = _case_path(data_dir, filename)
    result = {}
    if path.is_file():
        for row in read_dbf(path):
            k, v = _num(row.get(key)), _text(row.get(value))
            if k and v:
                result[k] = v
    return result


def inspect_company(data_dir):
    result = {}
    for filename in ("DO1.DBF", "DO2.DBF", "BUILTY.DBF", "BILL1.DBF", "BILL2.DBF"):
        path = _case_path(data_dir, filename)
        result[filename[:-4].lower()] = sum(1 for _ in read_dbf(path)) if path.is_file() else 0
    return result


def import_company(data_dir, con):
    """Merge active source rows, retain source links, and safely skip existing keys."""
    data_dir = Path(data_dir)
    con.execute("PRAGMA foreign_keys=ON")
    counts = {"do_inserted": 0, "do_existing": 0, "builty_inserted": 0,
              "builty_existing": 0, "bill_inserted": 0, "bill_existing": 0,
              "orphan_builty_skipped": 0, "schedules_inserted": 0,
              "source_do": 0, "source_builty": 0, "source_bill": 0}
    parties = _lookup(data_dir, "ACCOUNT.DBF", "CODE", "NAME")
    items = _lookup(data_dir, "ITEM.DBF", "CODE", "NAME")
    mines = _lookup(data_dir, "MINES.DBF", "CODE", "NAME")
    do_rows = list(read_dbf(_case_path(data_dir, "DO1.DBF")))
    counts["source_do"] = len(do_rows)
    do_id_map, do_cap_map, seen_do_numbers = {}, {}, set()
    con.execute("BEGIN")
    try:
        for row in do_rows:
            inv, number = _num(row.get("INVNO")), _num(row.get("NUM"))
            if not inv or not number:
                continue
            do_no = str(number)
            if do_no in seen_do_numbers:
                do_no = f"{number}-{inv}"
            seen_do_numbers.add(str(number))
            do_cap_map[inv] = float(row.get("CAP") or 0)
            existing = con.execute("SELECT id FROM dos WHERE do_no=?", (do_no,)).fetchone()
            if existing:
                do_id_map[inv] = existing[0]
                counts["do_existing"] += 1
                continue
            party = parties.get(_num(row.get("PRCODE")), "")
            material = items.get(_num(row.get("ITCODE")), "") or mines.get(_num(row.get("MNCODE")), "")
            con.execute("""INSERT OR IGNORE INTO dos
                (do_no,gmdc_do_no,do_date,customer_no,customer_name,customer_gstin,order_type,
                 hsn,material,schedule_date,qty,uom,unit_price,extended_price,transporter_code,
                 transporter_name,order_total,remaining_qty,from_place,to_place,source_pdf)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (do_no, _text(row.get("NUM2")), _text(row.get("DATE")), str(_num(row.get("PRCODE"))),
                 party, "", _text(row.get("DO_TYPE")), "", material, _text(row.get("FR_DATE")),
                 float(row.get("QTY") or 0), "TON", float(row.get("NET_RATE") or row.get("RATE") or 0),
                 float(row.get("AMOUNT") or 0), str(_num(row.get("AGCODE"))),
                 parties.get(_num(row.get("AGCODE")), ""), float(row.get("NET_RCVD") or row.get("NET") or 0),
                 float(row.get("QTY") or 0), "BHAVNAGAR", "", "SWASTIK:" + data_dir.parent.name))
            found = con.execute("SELECT id FROM dos WHERE do_no=?", (do_no,)).fetchone()
            if found:
                do_id_map[inv] = found[0]
                counts["do_inserted"] += 1

        for row in read_dbf(_case_path(data_dir, "DO2.DBF")):
            inv = _num(row.get("INVNO"))
            do_id = do_id_map.get(inv)
            if not do_id:
                continue
            schedule_date = _text(row.get("QTDATE")) or _text(row.get("DATE"))
            qty = _num(row.get("NO")) * do_cap_map.get(inv, 0)
            remaining = _num(row.get("PENDNO")) * do_cap_map.get(inv, 0)
            if not schedule_date or qty <= 0:
                continue
            cur = con.execute("""INSERT OR IGNORE INTO do_schedules
                (do_id,schedule_date,qty,remaining_qty,uom) VALUES(?,?,?,?,?)""",
                (do_id, schedule_date, qty, min(qty, max(0.0, remaining)), "TON"))
            counts["schedules_inserted"] += max(cur.rowcount, 0)

        seen_builty_numbers, source_builty_ids = set(), {}
        for row in read_dbf(_case_path(data_dir, "BUILTY.DBF")):
            counts["source_builty"] += 1
            inv, do_inv = _num(row.get("INVNO")), _num(row.get("DO_INVNO"))
            do_id = do_id_map.get(do_inv)
            if not inv:
                continue
            base_no = (_text(row.get("SERIES")) + str(_num(row.get("NUM"))) +
                       _text(row.get("SERIES2"))).strip()
            if not base_no or base_no == "0":
                base_no = f"LEGACY-{inv}"
            builty_no = base_no if base_no not in seen_builty_numbers else f"{base_no}-{inv}"
            seen_builty_numbers.add(base_no)
            existing = con.execute("SELECT id FROM builtys WHERE builty_no=?", (builty_no,)).fetchone()
            if existing:
                source_builty_ids[inv] = existing[0]
                counts["builty_existing"] += 1
                continue
            if not do_id:
                counts["orphan_builty_skipped"] += 1
                continue
            party = parties.get(_num(row.get("PRCODE")), "")
            cur = con.execute("""INSERT OR IGNORE INTO builtys
                (builty_no,do_id,truck_no,date,qty,freight_rate,freight_amount,from_place,to_place,
                 consignor,consignee,driver_name,ewaybill,remarks,billed,freight_paid,
                 vehicle_no,challan_no,driver_mobile,owner_name,sale_rate,sale_amount,
                 despatch_weight,receipt_weight,commission,driver_payable,receipt_date,voucher_remarks)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (builty_no, do_id, _text(row.get("VEH_NUM")), _text(row.get("DATE")),
                 float(row.get("RCWGT") or row.get("DSWGT") or 0), float(row.get("RATE") or row.get("MST_RATE") or 0),
                 float(row.get("TAMOUNT") or row.get("AMOUNT") or row.get("NET") or 0),
                 "BHAVNAGAR", _text(row.get("SUPPLY")), party, _text(row.get("SUPPLY")),
                 _text(row.get("DRV_NAME")), _text(row.get("GINV_NO")), _text(row.get("REMARKS1")),
                 0, 1 if _text(row.get("ST_PAID")).upper() in ("Y", "YES", "PAID") else 0,
                 _text(row.get("VEH_NUM")), _text(row.get("CHN_NUM")), _text(row.get("DRV_MB")),
                 _text(row.get("OWN_NAME")), float(row.get("SALE_RATE") or 0), float(row.get("SALE_AMT") or 0),
                 float(row.get("DSWGT") or 0), float(row.get("RCWGT") or 0),
                 float(row.get("TCOMMI") or row.get("COMMI") or 0),
                 float(row.get("TNET") or row.get("NET") or 0), _text(row.get("GINV_DT")),
                 _text(row.get("REMARKSV") or row.get("REMARKS2"))))
            found = con.execute("SELECT id FROM builtys WHERE builty_no=?", (builty_no,)).fetchone()
            if found:
                source_builty_ids[inv] = found[0]
            counts["builty_inserted"] += max(cur.rowcount, 0)

        bill_rows = list(read_dbf(_case_path(data_dir, "BILL1.DBF")))
        bill_details = list(read_dbf(_case_path(data_dir, "BILL2.DBF")))
        counts["source_bill"] = len(bill_rows)
        bill_ids = {}
        for row in bill_rows:
            inv, number = _num(row.get("INVNO")), _num(row.get("NUM"))
            if not inv or not number:
                continue
            bill_no = (_text(row.get("SERIES")) + str(number)).strip()
            existing = con.execute("SELECT id FROM bills WHERE bill_no=?", (bill_no,)).fetchone()
            if existing:
                bill_ids[inv] = existing[0]
                counts["bill_existing"] += 1
                continue
            party = parties.get(_num(row.get("PRCODE")), "")
            cur = con.execute("""INSERT OR IGNORE INTO bills
                (bill_no,bill_date,bill_type,customer_name,customer_gstin,total_qty,rate_per_ton,
                 subtotal,cgst,sgst,igst,total,remarks) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (bill_no, _text(row.get("DATE")), "MATERIAL", party, "", float(row.get("TOT_QTY") or 0),
                 0, float(row.get("GROSS") or 0), float(row.get("CGST_AMT") or 0),
                 float(row.get("SGST_AMT") or 0), float(row.get("IGST_AMT") or 0),
                 float(row.get("NET") or 0), _text(row.get("REMARKS1"))))
            found = con.execute("SELECT id FROM bills WHERE bill_no=?", (bill_no,)).fetchone()
            if found:
                bill_ids[inv] = found[0]
            counts["bill_inserted"] += max(cur.rowcount, 0)
        for detail in bill_details:
            bill_id = bill_ids.get(_num(detail.get("INVNO")))
            builty_id = source_builty_ids.get(_num(detail.get("BLT_INVNO")))
            if bill_id and builty_id:
                con.execute("INSERT OR IGNORE INTO bill_builtys(bill_id,builty_id) VALUES(?,?)",
                            (bill_id, builty_id))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return counts
