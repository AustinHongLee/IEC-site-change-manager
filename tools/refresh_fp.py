"""一次性腳本：用新算法重新計算所有指紋。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
CONTROL_DIR = os.path.join(ROOT, "control")
if CONTROL_DIR not in sys.path:
    sys.path.insert(0, CONTROL_DIR)

from record_manager import _load_store, _save_store, auto_backup, RECORDS_JSON_PATH
from utils import compute_fingerprint
from parsers import parse_folder
from config import ATTACHMENTS_ROOT, use_dual_images

auto_backup(RECORDS_JSON_PATH)
store = _load_store()
updated = 0
errors = 0
skipped = 0

for rec in store['records']:
    date_str = rec.get('日期', '')
    folder = rec.get('資料夾名', '')
    if not date_str or not folder:
        continue
    folder_path = os.path.join(ATTACHMENTS_ROOT, date_str, folder)
    if not os.path.isdir(folder_path):
        skipped += 1
        continue
    try:
        info = parse_folder(folder_path)
        sr = [t.raw for t in info.tokens]
        d = use_dual_images(info.mode, len(info.tokens))
        fp = compute_fingerprint(
            date_str, folder, info.series_no, sr,
            info.note_text, info.materials_text, folder_path,
            is_group=(info.mode == 'group'), use_dual_images=d
        )
        old_fp = rec.get('內容指紋', '')
        if old_fp != fp:
            rec['內容指紋'] = fp
            updated += 1
    except Exception as e:
        errors += 1
        print(f"  ERR {folder}: {e}")

_save_store(store)
total = len(store['records'])
print(f"Done: {updated} updated, {skipped} skipped (no folder), {errors} errors, {total} total")
