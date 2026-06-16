# -*- coding: utf-8 -*-
"""一次性資料完整性掃描腳本"""
import json, os
from collections import Counter

# === Load all data stores ===
with open('records/records.json', 'r', encoding='utf-8') as f:
    store = json.load(f)

billing_path = 'records/billing.json'
billing = {}
if os.path.exists(billing_path):
    with open(billing_path, 'r', encoding='utf-8') as f:
        billing = json.load(f)

dwg_path = 'records/dwg_map.json'
dwg_map = {}
if os.path.exists(dwg_path):
    with open(dwg_path, 'r', encoding='utf-8') as f:
        dwg_map = json.load(f)

snap_path = 'records/weld_snapshot.json'
snap = {}
if os.path.exists(snap_path):
    with open(snap_path, 'r', encoding='utf-8') as f:
        snap = json.load(f)

records = store.get("records", [])
details = store.get("details", [])
att = 'attachments'

print("=== DATA STORE SIZES ===")
print(f"records.json: {len(records)} records, {len(details)} details")
print(f"billing.json: {len(billing)} top-level keys")
if isinstance(dwg_map.get("map"), dict):
    print(f"dwg_map.json: {len(dwg_map['map'])} entries")
else:
    print(f"dwg_map.json: {len(dwg_map)} entries")
snap_folders = snap.get("folders", {})
snap_weld = snap.get("weld_index", {})
print(f"weld_snapshot.json: {len(snap_folders)} folders, {len(snap_weld)} weld entries")
print()

# === Check 1: records pointing to non-existent attachments ===
missing_att = []
for r in records:
    d = str(r.get("日期", ""))
    folder = str(r.get("資料夾名", ""))
    if d and folder:
        if not os.path.isdir(os.path.join(att, d, folder)):
            missing_att.append((d, folder, r.get("報告編號", "")))
print(f"Check 1 - Records without attachments folder: {len(missing_att)}")
for x in missing_att:
    print(f"  {x[2]} | {x[0]}/{x[1]}")

# === Check 2: attachment folders without records ===
record_keys = set()
for r in records:
    d = str(r.get("日期", ""))
    folder = str(r.get("資料夾名", ""))
    if d and folder:
        record_keys.add((d, folder))

orphan_att = []
for date_dir in sorted(os.listdir(att)):
    date_path = os.path.join(att, date_dir)
    if not os.path.isdir(date_path) or date_dir.startswith("_"):
        continue
    for folder in sorted(os.listdir(date_path)):
        folder_path = os.path.join(date_path, folder)
        if not os.path.isdir(folder_path) or folder.startswith("_"):
            continue
        if (date_dir, folder) not in record_keys:
            orphan_att.append((date_dir, folder))

print(f"\nCheck 2 - Attachment folders without records: {len(orphan_att)}")
for x in orphan_att:
    print(f"  {x[0]}/{x[1]}")

# === Check 3: details referencing non-existent records ===
record_ids = set(r.get("報告編號", "") for r in records)
orphan_details = []
for det in details:
    rid = det.get("紀錄編號", det.get("報告編號", ""))
    if rid and rid not in record_ids:
        orphan_details.append(rid)
print(f"\nCheck 3 - Orphan details (ref non-existent record): {len(orphan_details)}")
for x in sorted(set(orphan_details)):
    print(f"  {x}")

# === Check 4: duplicate report IDs ===
rid_counts = Counter(r.get("報告編號", "") for r in records if r.get("報告編號"))
dupes = {k: v for k, v in rid_counts.items() if v > 1}
print(f"\nCheck 4 - Duplicate report IDs: {len(dupes)}")
for k, v in sorted(dupes.items()):
    print(f"  {k}: {v} times")

# === Check 5: duplicate (date, folder) keys ===
key_counts = Counter()
for r in records:
    d = str(r.get("日期", ""))
    folder = str(r.get("資料夾名", ""))
    if d and folder:
        key_counts[(d, folder)] += 1
dupe_keys = {k: v for k, v in key_counts.items() if v > 1}
print(f"\nCheck 5 - Duplicate (date, folder) keys: {len(dupe_keys)}")
for k, v in sorted(dupe_keys.items()):
    print(f"  {k[0]}/{k[1]}: {v} times")

# === Check 6: image field vs real file mismatch ===
img_mismatch = []
for r in records:
    d = str(r.get("日期", ""))
    folder = str(r.get("資料夾名", ""))
    if not d or not folder:
        continue
    fpath = os.path.join(att, d, folder)
    if not os.path.isdir(fpath):
        continue
    rec_before = r.get("before.jpg", "") == "有"
    rec_after = r.get("after.jpg", "") == "有"
    real_before = os.path.exists(os.path.join(fpath, "before.jpg"))
    real_after = os.path.exists(os.path.join(fpath, "after.jpg"))
    issues = []
    if rec_before != real_before:
        issues.append(f"before.jpg: record={rec_before}, real={real_before}")
    if rec_after != real_after:
        issues.append(f"after.jpg: record={rec_after}, real={real_after}")
    if issues:
        img_mismatch.append((d, folder, r.get("報告編號",""), "; ".join(issues)))
print(f"\nCheck 6 - Image field mismatch: {len(img_mismatch)}")
for x in img_mismatch[:20]:
    print(f"  {x[2]} | {x[0]}/{x[1]}: {x[3]}")
if len(img_mismatch) > 20:
    print(f"  ... and {len(img_mismatch) - 20} more")

# === Check 7: output files existence ===
out_missing = []
pdf_missing = []
for r in records:
    rid = r.get("報告編號", "")
    d = str(r.get("日期", ""))
    if not rid or not d:
        continue
    # Check PDF
    pdf_path = os.path.join("pdf", f"{rid}.pdf")
    if not os.path.exists(pdf_path):
        pdf_missing.append((d, rid))
print(f"\nCheck 7 - Records without PDF output: {len(pdf_missing)}")
for x in pdf_missing[:10]:
    print(f"  {x[1]} ({x[0]})")
if len(pdf_missing) > 10:
    print(f"  ... and {len(pdf_missing) - 10} more")

# === Check 8: _ERROR.txt markers still present ===
error_markers = []
for date_dir in sorted(os.listdir(att)):
    date_path = os.path.join(att, date_dir)
    if not os.path.isdir(date_path) or date_dir.startswith("_"):
        continue
    for folder in sorted(os.listdir(date_path)):
        folder_path = os.path.join(date_path, folder)
        if not os.path.isdir(folder_path) or folder.startswith("_"):
            continue
        err = os.path.join(folder_path, "_ERROR.txt")
        if os.path.exists(err):
            error_markers.append(f"{date_dir}/{folder}")
print(f"\nCheck 8 - Folders with _ERROR.txt: {len(error_markers)}")
for x in error_markers:
    print(f"  {x}")

# === Check 9: weld_snapshot staleness ===
real_folder_set = set()
for date_dir in sorted(os.listdir(att)):
    dp = os.path.join(att, date_dir)
    if not os.path.isdir(dp) or date_dir.startswith("_"):
        continue
    for fd in sorted(os.listdir(dp)):
        fp = os.path.join(dp, fd)
        if os.path.isdir(fp) and not fd.startswith("_"):
            real_folder_set.add(f"{date_dir}/{fd}")
print(f"\nCheck 9 - Weld snapshot staleness:")
print(f"  Snapshot folders: {len(snap_folders)}")
print(f"  Real folders: {len(real_folder_set)}")

# === Check 10: billing.json vs records cross-ref ===
if billing:
    billing_rids = set()
    if isinstance(billing, dict):
        for key in billing:
            if isinstance(billing[key], list):
                for item in billing[key]:
                    if isinstance(item, dict):
                        rid = item.get("報告編號", item.get("report_id", ""))
                        if rid:
                            billing_rids.add(rid)
    orphan_billing = billing_rids - record_ids
    print(f"\nCheck 10 - Billing refs to non-existent records: {len(orphan_billing)}")
    for x in sorted(orphan_billing):
        print(f"  {x}")
else:
    print("\nCheck 10 - billing.json: empty or not found")

# === Summary ===
print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)
issues_total = (len(missing_att) + len(orphan_att) + len(orphan_details) + 
                len(dupes) + len(dupe_keys) + len(img_mismatch) + len(error_markers))
print(f"Total issues found: {issues_total}")
if issues_total == 0:
    print("All data stores are consistent!")
