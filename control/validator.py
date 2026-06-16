# -*- coding: utf-8 -*-
"""
validator.py — 資料夾防呆驗證模組

功能：
- 檢查必要檔案是否存在
- 驗證檔案格式與內容
- 資料夾命名規則檢查
- 產生驗證報告
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import Enum


class Severity(Enum):
    """問題嚴重程度"""
    ERROR = "error"      # 必須修正，無法繼續
    WARNING = "warning"  # 建議修正，可能影響結果
    INFO = "info"        # 提示資訊


class FileType(Enum):
    """檔案類型"""
    REQUIRED = "required"    # 必要檔案
    OPTIONAL = "optional"    # 可選檔案
    CONDITIONAL = "conditional"  # 條件性必要（依模式而定）


@dataclass
class ValidationIssue:
    """驗證問題"""
    severity: Severity
    category: str       # 類別：naming, file, content, image
    message: str
    suggestion: str = ""
    file_path: str = ""


@dataclass
class FolderValidation:
    """資料夾驗證結果"""
    folder_path: str
    folder_name: str
    is_valid: bool
    mode: str = ""  # "single" or "group"
    series_no: str = ""
    issues: List[ValidationIssue] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    missing_optional: List[str] = field(default_factory=list)
    found_files: List[str] = field(default_factory=list)
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.ERROR)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.WARNING)


# ========= 命名規則 =========

# Single folder: {SeriesNo}_{WeldInfo}
# 例: 202_1001a2.5, 234_15r1_12r1_10r1_9a1_9b1
SINGLE_FOLDER_PATTERN = re.compile(r'^(\d+)_(.+)$')

# Group folder: {SeriesNo}_{X}G
# 例: 101_AG, 111_BG
GROUP_FOLDER_PATTERN = re.compile(r'^(\d+)_([A-Za-z])G$')

# 焊口格式: {數字}{字母}{尺寸}
# 例: 15r1, 12a0.5, 1001a2.5
WELD_TOKEN_PATTERN = re.compile(r'^(\d+)([A-Za-z])(\d+(?:\.\d+)?)$')


# ========= 檔案規格 =========

# 必要檔案
REQUIRED_FILES = {
    # 圖片
    "before.jpg": "修改前照片（6-slot）",
    "after.jpg": "修改後照片（6-slot）",
    "before_1.jpg": "修改前照片 1（27-slot）",
    "after_1.jpg": "修改後照片 1（27-slot）",
    # PDF（格式: {SeriesNo}.*.pdf）
    "{SeriesNo}.*.pdf": "ISO 圖面 PDF（必要）",
}

# 必要檔案（Group 模式 - 27slot）
REQUIRED_FILES_GROUP = {
    "GroupWeld.txt": "焊口清單檔案",
}

# 建議檔案
RECOMMENDED_FILES = {
    "note.txt": "修改原因說明（建議提供，程式可自動判斷 r/a，但手動說明更清楚）",
}

# 可選檔案
OPTIONAL_FILES = {
    "materials.txt": "材料附加說明（新增零件時使用）",
    "before_2.jpg": "修改前照片 2（27-slot）",
    "after_2.jpg": "修改後照片 2（27-slot）",
}

# 圖片檔案（至少要有一組）
IMAGE_FILES_SINGLE = ["before.jpg", "after.jpg"]
IMAGE_FILES_GROUP = [
    ["before_1.jpg", "after_1.jpg"],
    ["before_2.jpg", "after_2.jpg"],
    ["before.jpg", "after.jpg"],  # fallback
]


def detect_folder_mode(folder_name: str) -> Tuple[str, str, str]:
    """
    偵測資料夾模式
    
    Returns:
        (mode, series_no, extra_info)
        mode: "single", "group", or "unknown"
    """
    m = GROUP_FOLDER_PATTERN.match(folder_name)
    if m:
        return "group", m.group(1).zfill(4), m.group(2).upper()
    
    m = SINGLE_FOLDER_PATTERN.match(folder_name)
    if m:
        return "single", m.group(1).zfill(4), m.group(2)
    
    return "unknown", "", ""


def validate_weld_tokens(weld_string: str) -> Tuple[bool, List[str], List[str]]:
    """
    驗證焊口字串格式
    
    Args:
        weld_string: 焊口字串，如 "15r1_12a0.5_10r1"
    
    Returns:
        (is_valid, valid_tokens, invalid_tokens)
    """
    tokens = weld_string.split('_')
    valid = []
    invalid = []
    
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        
        if WELD_TOKEN_PATTERN.match(tok):
            valid.append(tok)
        else:
            # 嘗試其他可接受格式
            # 純數字（只有焊口號）
            if re.match(r'^\d+$', tok):
                valid.append(tok)
            # 數字+字母（沒有尺寸）
            elif re.match(r'^\d+[A-Za-z]$', tok):
                valid.append(tok)
            else:
                invalid.append(tok)
    
    return len(invalid) == 0, valid, invalid


def check_pdf_exists(folder_path: str, series_no: str) -> Tuple[bool, Optional[str], List[ValidationIssue]]:
    """
    檢查是否存在對應的 PDF 附件（ISO 圖）
    
    PDF 檔名格式必須是: {SeriesNo}.*.pdf
    例如: 202.DW-0404-25-AA1B-NA.pdf
    
    Returns:
        (is_valid, pdf_filename, issues)
    """
    issues = []
    
    try:
        files = os.listdir(folder_path)
    except OSError:
        return False, None, [ValidationIssue(
            severity=Severity.ERROR,
            category="file",
            message="無法讀取資料夾",
            file_path=folder_path
        )]
    
    pdf_files = [f for f in files if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="file",
            message="缺少必要的 PDF 附件（ISO 圖）",
            suggestion=f"請提供 {series_no}.*.pdf 格式的 PDF 檔案",
            file_path=folder_path
        ))
        return False, None, issues
    
    # 檢查是否有符合格式的 PDF: {SeriesNo}.*.pdf
    series_variants = [series_no, series_no.lstrip('0')]
    matched_pdf = None
    
    for pdf in pdf_files:
        pdf_lower = pdf.lower()
        for variant in series_variants:
            # 必須是 {SeriesNo}. 開頭
            if pdf_lower.startswith(variant.lower() + '.'):
                matched_pdf = pdf
                break
        if matched_pdf:
            break
    
    if matched_pdf:
        return True, matched_pdf, issues
    
    # 有 PDF 但格式不對
    issues.append(ValidationIssue(
        severity=Severity.ERROR,
        category="file",
        message=f"PDF 檔名格式不正確: {pdf_files[0]}",
        suggestion=f"PDF 檔名必須以 '{series_no}.' 開頭，例如: {series_no}.DW-xxxx.pdf",
        file_path=os.path.join(folder_path, pdf_files[0])
    ))
    return False, pdf_files[0], issues


def check_group_weld_file(folder_path: str) -> Tuple[bool, List[str], List[ValidationIssue]]:
    """
    檢查 GroupWeld.txt 格式
    
    Returns:
        (is_valid, weld_list, issues)
    """
    txt_path = os.path.join(folder_path, "GroupWeld.txt")
    issues = []
    welds = []
    
    if not os.path.exists(txt_path):
        return False, [], [ValidationIssue(
            severity=Severity.ERROR,
            category="file",
            message="GroupWeld.txt 不存在",
            suggestion="Group 模式必須提供 GroupWeld.txt 列出所有焊口",
            file_path=txt_path
        )]
    
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return False, [], [ValidationIssue(
            severity=Severity.ERROR,
            category="file",
            message=f"無法讀取 GroupWeld.txt: {e}",
            file_path=txt_path
        )]
    
    # 新格式: <weldNo><tag><size>，如 15a0.5
    new_pattern = re.compile(r'^\s*(\d+)([A-Za-z])(\d+(?:\.\d+)?)\s*$')
    # 舊格式: <code>_<size>，如 15a0.5_0.5
    old_pattern = re.compile(r'^\s*([A-Za-z0-9\.]+)\s*_\s*([0-9]+(?:\.[0-9]+)?)\s*$')
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if new_pattern.match(line):
            welds.append(line)
        elif old_pattern.match(line):
            welds.append(line)
            issues.append(ValidationIssue(
                severity=Severity.INFO,
                category="content",
                message=f"第 {i} 行使用舊格式: {line}",
                suggestion="建議改用新格式: <焊口號><標記><尺寸>，如 15a0.5",
                file_path=txt_path
            ))
        else:
            issues.append(ValidationIssue(
                severity=Severity.ERROR,
                category="content",
                message=f"第 {i} 行格式錯誤: {line}",
                suggestion="正確格式: <焊口號><標記><尺寸>，如 15a0.5、12r1",
                file_path=txt_path
            ))
    
    if not welds:
        issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="content",
            message="GroupWeld.txt 沒有有效的焊口資料",
            suggestion="每行一個焊口，格式: <焊口號><標記><尺寸>",
            file_path=txt_path
        ))
        return False, [], issues
    
    return len([i for i in issues if i.severity == Severity.ERROR]) == 0, welds, issues


def check_images(folder_path: str, mode: str, weld_count: int = 0) -> Tuple[bool, List[str], List[ValidationIssue]]:
    """
    檢查圖片檔案
    
    Args:
        folder_path: 資料夾路徑
        mode: "single" 或 "group"
        weld_count: 焊口數量（用於判斷 single 模式需要哪種圖片組合）
    
    Returns:
        (has_required_images, found_images, issues)
    """
    issues = []
    found = []
    
    # 檢查所有可能的圖片檔案
    all_possible = [
        "before.jpg", "after.jpg",
        "before_1.jpg", "after_1.jpg",
        "before_2.jpg", "after_2.jpg"
    ]
    for img in all_possible:
        if os.path.exists(os.path.join(folder_path, img)):
            found.append(img)
    
    if mode == "single":
        # 判斷應該用哪種模板
        use_27slot = weld_count > 6
        
        if use_27slot:
            # 27-slot 模板：需要 before_1.jpg, before_2.jpg, after_1.jpg, after_2.jpg
            # 或至少要有 before_1 + after_1
            has_b1 = "before_1.jpg" in found
            has_b2 = "before_2.jpg" in found
            has_a1 = "after_1.jpg" in found
            has_a2 = "after_2.jpg" in found
            
            # 也接受舊的 before.jpg / after.jpg 當 fallback
            has_before_old = "before.jpg" in found
            has_after_old = "after.jpg" in found
            
            has_before = has_b1 or has_before_old
            has_after = has_a1 or has_after_old
            
            if not has_before:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    category="file",
                    message=f"缺少 before 圖片（焊口數 {weld_count} > 6，需要 27-slot 模板）",
                    suggestion="請提供 before_1.jpg（或 before.jpg）",
                    file_path=folder_path
                ))
            
            if not has_after:
                issues.append(ValidationIssue(
                    severity=Severity.ERROR,
                    category="file",
                    message=f"缺少 after 圖片（焊口數 {weld_count} > 6，需要 27-slot 模板）",
                    suggestion="請提供 after_1.jpg（或 after.jpg）",
                    file_path=folder_path
                ))
            
            # 提示：建議提供完整的 4 張圖
            if has_before and has_after:
                if not (has_b1 and has_b2 and has_a1 and has_a2):
                    missing = []
                    if not has_b1: missing.append("before_1.jpg")
                    if not has_b2: missing.append("before_2.jpg")
                    if not has_a1: missing.append("after_1.jpg")
                    if not has_a2: missing.append("after_2.jpg")
                    if missing:
                        issues.append(ValidationIssue(
                            severity=Severity.WARNING,
                            category="file",
                            message=f"27-slot 模板建議提供完整 4 張圖片，缺少: {', '.join(missing)}",
                            suggestion="完整圖片可讓報告更清晰"
                        ))
            
            return has_before and has_after, found, issues
        
        else:
            # 6-slot 模板：需要 before.jpg 和 after.jpg
            for img in ["before.jpg", "after.jpg"]:
                if img not in found:
                    issues.append(ValidationIssue(
                        severity=Severity.ERROR,
                        category="file",
                        message=f"缺少必要圖片: {img}",
                        suggestion="請提供修改前後的照片",
                        file_path=os.path.join(folder_path, img)
                    ))
            
            return len(issues) == 0, found, issues
    
    elif mode == "group":
        # Group 模式：檢查是否有至少一組 before/after
        has_before = any(f.startswith("before") for f in found)
        has_after = any(f.startswith("after") for f in found)
        
        if not has_before:
            issues.append(ValidationIssue(
                severity=Severity.ERROR,
                category="file",
                message="缺少 before 圖片",
                suggestion="請提供 before.jpg 或 before_1.jpg",
            ))
        
        if not has_after:
            issues.append(ValidationIssue(
                severity=Severity.ERROR,
                category="file",
                message="缺少 after 圖片",
                suggestion="請提供 after.jpg 或 after_1.jpg",
            ))
        
        return has_before and has_after, found, issues
    
    return True, found, issues


def validate_folder(folder_path: str) -> FolderValidation:
    """
    完整驗證單一資料夾
    
    Args:
        folder_path: 資料夾完整路徑
    
    Returns:
        FolderValidation 結果
    """
    folder_name = os.path.basename(folder_path)
    result = FolderValidation(
        folder_path=folder_path,
        folder_name=folder_name,
        is_valid=True
    )
    
    # 1. 檢查資料夾是否存在
    if not os.path.isdir(folder_path):
        result.is_valid = False
        result.issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="file",
            message="資料夾不存在",
            file_path=folder_path
        ))
        return result
    
    # 2. 解析資料夾命名
    mode, series_no, extra = detect_folder_mode(folder_name)
    result.mode = mode
    result.series_no = series_no
    
    if mode == "unknown":
        result.is_valid = False
        result.issues.append(ValidationIssue(
            severity=Severity.ERROR,
            category="naming",
            message=f"資料夾命名格式不正確: {folder_name}",
            suggestion="正確格式: {SeriesNo}_{焊口資訊} 或 {SeriesNo}_{X}G (群組)"
        ))
        return result
    
    # 3. Single 模式：驗證焊口格式，並計算焊口數量
    weld_count = 0
    if mode == "single":
        is_valid_weld, valid_tokens, invalid_tokens = validate_weld_tokens(extra)
        weld_count = len(valid_tokens)
        if invalid_tokens:
            result.issues.append(ValidationIssue(
                severity=Severity.WARNING,
                category="naming",
                message=f"部分焊口格式不標準: {', '.join(invalid_tokens)}",
                suggestion="標準格式: <焊口號><標記><尺寸>，如 15r1、12a0.5"
            ))
    
    # 4. Group 模式：檢查 GroupWeld.txt
    if mode == "group":
        gw_valid, gw_welds, gw_issues = check_group_weld_file(folder_path)
        result.issues.extend(gw_issues)
        weld_count = len(gw_welds)
        if not gw_valid:
            result.is_valid = False
            result.missing_required.append("GroupWeld.txt (valid)")
    
    # 5. 檢查圖片（根據焊口數量判斷需要哪種圖片）
    img_ok, img_found, img_issues = check_images(folder_path, mode, weld_count)
    result.issues.extend(img_issues)
    result.found_files.extend(img_found)
    if not img_ok:
        result.is_valid = False
        # 更新 missing_required 清單
        use_27slot = weld_count > 6 or mode == "group"
        if use_27slot:
            if not any(f.startswith("before") for f in img_found):
                result.missing_required.append("before_1.jpg (或 before.jpg)")
            if not any(f.startswith("after") for f in img_found):
                result.missing_required.append("after_1.jpg (或 after.jpg)")
        else:
            if "before.jpg" not in img_found:
                result.missing_required.append("before.jpg")
            if "after.jpg" not in img_found:
                result.missing_required.append("after.jpg")
    
    # 6. 檢查 PDF 附件
    # 6-slot（焊口 ≤ 6）：PDF 必要，格式 {SeriesNo}.*.pdf
    # 27-slot（焊口 > 6 或 Group）：PDF 可選，格式不限
    use_27slot = weld_count > 6 or mode == "group"
    pdf_ok, pdf_name, pdf_issues = check_pdf_exists(folder_path, series_no)
    
    if pdf_ok and pdf_name:
        result.found_files.append(pdf_name)
    
    if use_27slot:
        # 27-slot：PDF 不強制要求
        if not pdf_ok:
            # 有 PDF 但格式不對 → 只是 INFO
            # 沒有 PDF → 也只是 INFO
            result.missing_optional.append(f"{series_no}.*.pdf (可選)")
            result.issues.append(ValidationIssue(
                severity=Severity.INFO,
                category="file",
                message="沒有找到 PDF 附件（27-slot 模式不強制要求）",
                suggestion=f"如需提供，建議檔名以 {series_no}. 開頭"
            ))
        # 清除 check_pdf_exists 產生的 ERROR（降級為 INFO）
        result.issues = [i for i in result.issues if i not in pdf_issues]
    else:
        # 6-slot：PDF 必要
        result.issues.extend(pdf_issues)
        if not pdf_ok:
            result.is_valid = False
            result.missing_required.append(f"{series_no}.*.pdf")
    
    # 7. 檢查 note.txt（建議但非必要）
    note_path = os.path.join(folder_path, "note.txt")
    if os.path.exists(note_path):
        result.found_files.append("note.txt")
        # 檢查內容
        try:
            with open(note_path, 'r', encoding='utf-8') as f:
                note_content = f.read().strip()
            if not note_content:
                result.issues.append(ValidationIssue(
                    severity=Severity.WARNING,
                    category="content",
                    message="note.txt 是空的",
                    suggestion="建議填寫修改原因說明",
                    file_path=note_path
                ))
            elif len(note_content) < 5:
                result.issues.append(ValidationIssue(
                    severity=Severity.INFO,
                    category="content",
                    message="note.txt 內容很短",
                    suggestion="可補充更詳細的說明",
                    file_path=note_path
                ))
        except Exception as e:
            result.issues.append(ValidationIssue(
                severity=Severity.WARNING,
                category="file",
                message=f"無法讀取 note.txt: {e}",
                file_path=note_path
            ))
    else:
        result.missing_optional.append("note.txt")
        result.issues.append(ValidationIssue(
            severity=Severity.WARNING,
            category="file",
            message="缺少 note.txt",
            suggestion="建議提供 note.txt 說明修改原因（程式可自動判斷，但手動說明更清楚）"
        ))
    
    # 8. 檢查 materials.txt（可選）
    materials_path = os.path.join(folder_path, "materials.txt")
    if os.path.exists(materials_path):
        result.found_files.append("materials.txt")
        # 可以在這裡加入格式驗證（等你定好格式後）
    else:
        result.missing_optional.append("materials.txt")
        # materials.txt 是純可選，不用特別提示
    
    # 最終判定
    result.is_valid = result.error_count == 0
    
    return result


def validate_date_folder(date_folder_path: str) -> Dict[str, FolderValidation]:
    """
    驗證日期資料夾下的所有子資料夾
    
    Returns:
        {folder_name: FolderValidation}
    """
    results = {}
    
    if not os.path.isdir(date_folder_path):
        return results
    
    for name in os.listdir(date_folder_path):
        subfolder = os.path.join(date_folder_path, name)
        if os.path.isdir(subfolder):
            results[name] = validate_folder(subfolder)
    
    return results


def generate_validation_report(validations: Dict[str, FolderValidation]) -> str:
    """
    產生驗證報告文字
    """
    lines = []
    lines.append("=" * 60)
    lines.append("資料夾驗證報告")
    lines.append("=" * 60)
    
    total = len(validations)
    valid_count = sum(1 for v in validations.values() if v.is_valid)
    error_count = total - valid_count
    
    lines.append(f"\n📊 統計：共 {total} 個資料夾")
    lines.append(f"   ✅ 通過: {valid_count}")
    lines.append(f"   ❌ 有問題: {error_count}")
    lines.append("")
    
    # 先顯示有問題的
    if error_count > 0:
        lines.append("─" * 40)
        lines.append("❌ 需要修正的資料夾：")
        lines.append("─" * 40)
        
        for name, v in validations.items():
            if not v.is_valid:
                lines.append(f"\n📁 {name} ({v.mode})")
                if v.missing_required:
                    lines.append(f"   缺少必要檔案: {', '.join(v.missing_required)}")
                for issue in v.issues:
                    if issue.severity == Severity.ERROR:
                        lines.append(f"   ⛔ {issue.message}")
                        if issue.suggestion:
                            lines.append(f"      💡 {issue.suggestion}")
    
    # 顯示警告
    warning_folders = [name for name, v in validations.items() 
                       if v.is_valid and v.warning_count > 0]
    if warning_folders:
        lines.append("")
        lines.append("─" * 40)
        lines.append("⚠️ 有警告的資料夾：")
        lines.append("─" * 40)
        
        for name in warning_folders:
            v = validations[name]
            lines.append(f"\n📁 {name}")
            for issue in v.issues:
                if issue.severity == Severity.WARNING:
                    lines.append(f"   ⚠️ {issue.message}")
    
    # 顯示通過的
    if valid_count > 0:
        lines.append("")
        lines.append("─" * 40)
        lines.append("✅ 驗證通過的資料夾：")
        lines.append("─" * 40)
        
        for name, v in validations.items():
            if v.is_valid and v.warning_count == 0:
                lines.append(f"   ✅ {name} ({v.mode}, {len(v.found_files)} 檔案)")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # 測試
    import sys
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    test_path = os.path.join(base_dir, "attachments", "20260112")
    
    if len(sys.argv) > 1:
        test_path = sys.argv[1]
    
    print(f"驗證: {test_path}")
    print()
    
    results = validate_date_folder(test_path)
    report = generate_validation_report(results)
    print(report)
