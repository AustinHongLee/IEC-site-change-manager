"""
materials.txt 格式轉換工具
將舊格式 (A: 純文字, B: 4欄CSV) 統一轉為新格式 (C: 6欄CSV)

Usage:
    python tools/convert_materials.py --dry-run   # 預覽
    python tools/convert_materials.py             # 實際轉換
"""
import os
import re
import sys
import shutil
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
ROOT = os.path.join(REPO_ROOT, "attachments")

# ── 零件名稱映射 ──
COMPONENT_MAP = {
    "鋼管": "Pipe (管)", "直管": "Pipe (管)", "管線": "Pipe (管)", "管": "Pipe (管)",
    "彎頭": "Elbow (彎頭)",
    "三通": "Tee (三通)",
    "法蘭": "Flange (法蘭)",
    "中間接頭": "Coupling (接頭)", "接頭": "Coupling (接頭)",
    "活接": "Union (活接)",
    "纏繞式金屬墊片": "Gasket (墊片)", "金屬墊片": "Gasket (墊片)", "墊片": "Gasket (墊片)",
    "眼鏡盲板": "Spectacle Blind (眼鏡盲板)",
    "大小頭": "Reducer (大小頭)",
}

# ── 尺寸轉換 ──
SIZE_MAP = {
    "0.5": '1/2"', "0.75": '3/4"',
    "1": '1"', "1.5": '1-1/2"',
    "2": '2"', "2.5": '2-1/2"',
    "3": '3"', "4": '4"', "6": '6"', "8": '8"',
}

def size_to_inch(s):
    s = s.strip()
    return SIZE_MAP.get(s, f'{s}"')


# ── Format A 解析: "材料:1吋黑鐵彎頭2個" ──
# 正常項目: {size}吋{material}{component}{qty}{unit}
PAT_ITEM = re.compile(
    r'(\d+(?:\.\d+)?)吋'
    r'(黑鐵|白鐵)'
    r'(鋼管|直管|管線|管|彎頭|三通|法蘭|中間接頭|接頭|活接|纏繞式金屬墊片|金屬墊片|墊片|眼鏡盲板|大小頭)'
    r'(\d+(?:\.\d+)?)\s*'
    r'(M|m|個|片|支|組)?'
)

# 特殊: "3吋WN-flange*1"
PAT_STAR = re.compile(
    r'(\d+(?:\.\d+)?)吋'
    r'(\S+?)'
    r'\s*[*]\s*(\d+)'
)

# 螺栓: "螺栓加螺帽 M16*150 *8"
PAT_BOLT = re.compile(
    r'螺栓加螺帽\s+(M\d+[*]\d+)\s*[*]\s*(\d+)'
)

# 大小頭: "3吋*6吋大小頭*1"
PAT_REDUCER = re.compile(
    r'(\d+(?:\.\d+)?)吋[*](\d+(?:\.\d+)?)吋(大小頭)[*](\d+)'
)


def parse_format_a(text):
    """解析舊版純文字格式"""
    text = re.sub(r'^\s*材料\s*[:：]\s*', '', text).strip()
    results = []
    consumed = set()

    # 螺栓
    for m in PAT_BOLT.finditer(text):
        spec, qty = m.group(1), m.group(2)
        results.append(("Bolt & Nut (螺栓螺帽)", spec, "", "黑鐵", f"{qty} 組", ""))
        consumed.add(m.span())

    # 大小頭: 3吋*6吋大小頭*1
    for m in PAT_REDUCER.finditer(text):
        s1, s2, _, qty = m.groups()
        sz = f'{size_to_inch(s1)}x{size_to_inch(s2)}'.replace('""', '"')
        results.append(("Reducer (大小頭)", sz, "", "黑鐵", f"{qty} 個", ""))
        consumed.add(m.span())

    # *格式: 3吋WN-flange*1, 3吋眼鏡盲板*1
    for m in PAT_STAR.finditer(text):
        # 跳過已被正常 PAT_ITEM 匹配的
        if PAT_ITEM.match(m.group(0)):
            continue
        # 跳過被大小頭匹配的
        if any(m.start() >= s and m.end() <= e for s, e in consumed):
            continue
        sz, comp_raw, qty = m.group(1), m.group(2), m.group(3)
        comp_name = comp_raw
        for k, v in COMPONENT_MAP.items():
            if k in comp_raw:
                comp_name = v
                break
        else:
            if "flange" in comp_raw.lower():
                comp_name = "Flange (法蘭)"
            elif "盲板" in comp_raw:
                comp_name = "Spectacle Blind (眼鏡盲板)"
        results.append((comp_name, size_to_inch(sz), "", "黑鐵", f"{qty} 個", ""))
        consumed.add(m.span())

    # 正常項目: 1吋黑鐵彎頭2個
    for m in PAT_ITEM.finditer(text):
        if any(m.start() >= s and m.end() <= e for s, e in consumed):
            continue
        sz, mat, comp, qty, unit = m.groups()
        unit = unit or "個"
        if unit.lower() == "m":
            unit = "M"
        comp_en = COMPONENT_MAP.get(comp, comp)
        results.append((comp_en, size_to_inch(sz), "", mat, f"{qty} {unit}", ""))

    return results


# ── Format B 解析: 4欄CSV → 6欄 ──
def parse_format_b(lines):
    """將 4 欄 CSV 資料行轉為 6 欄格式"""
    results = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            comp, size, material, qty_unit = parts[0], parts[1], parts[2], parts[3]
            results.append((comp, size, "", material, qty_unit, ""))
    return results


def format_new(items):
    """產生新版 6 欄 CSV 文字"""
    header = [
        "# 使用材料清單",
        "# 零件, 尺寸, SCH, 材質, 數量, 備註",
        "-" * 50,
    ]
    data_lines = []
    for comp, size, sch, mat, qty, note in items:
        data_lines.append(f"{comp}, {size}, {sch}, {mat}, {qty}, {note}")
    return "\n".join(header + data_lines) + "\n"


def detect_format(content):
    if "# 零件, 尺寸, SCH" in content:
        return "C"
    if "# 零件, 尺寸, 材質" in content:
        return "B"
    if content.strip().startswith("材料"):
        return "A"
    return "?"


def convert_file(filepath, dry_run=True):
    """轉換單一 materials.txt，回傳 (format, items, error)"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    fmt = detect_format(content)
    if fmt == "C":
        return fmt, None, None  # 已是新格式

    if fmt == "A":
        items = parse_format_a(content)
        if not items:
            return fmt, None, f"無法解析: {content.strip()[:80]}"
    elif fmt == "B":
        items = parse_format_b(content.splitlines())
        if not items:
            return fmt, None, f"無資料行"
    else:
        return fmt, None, f"未知格式"

    new_content = format_new(items)

    if not dry_run:
        # 備份
        bak = filepath + f".bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(filepath, bak)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

    return fmt, items, None


def main():
    dry_run = "--dry-run" in sys.argv
    mode = "DRY RUN 預覽" if dry_run else "實際轉換"
    print(f"=== materials.txt 格式轉換 ({mode}) ===\n")

    stats = {"A": 0, "B": 0, "C": 0, "error": 0}
    errors = []

    for dirpath, dirs, files in sorted(os.walk(ROOT)):
        if "materials.txt" in files:
            fp = os.path.join(dirpath, "materials.txt")
            rel = os.path.relpath(fp, ROOT)
            fmt, items, err = convert_file(fp, dry_run=dry_run)

            if fmt == "C":
                stats["C"] += 1
                continue

            if err:
                stats["error"] += 1
                errors.append((rel, err))
                print(f"  ❌ [{fmt}] {rel}")
                print(f"     {err}")
                continue

            stats[fmt] = stats.get(fmt, 0) + 1
            print(f"  ✅ [{fmt}→C] {rel}  ({len(items)} 筆)")
            if dry_run:
                for comp, sz, sch, mat, qty, note in items:
                    print(f"        {comp}, {sz}, {sch or ''}, {mat}, {qty}, {note}")

    print(f"\n=== 結果 ===")
    print(f"  Format A → C: {stats['A']} 個")
    print(f"  Format B → C: {stats['B']} 個")
    print(f"  已是 Format C: {stats['C']} 個")
    print(f"  錯誤:          {stats['error']} 個")
    if errors:
        print(f"\n  ⚠️  失敗清單:")
        for rel, err in errors:
            print(f"    {rel}: {err}")


if __name__ == "__main__":
    main()
