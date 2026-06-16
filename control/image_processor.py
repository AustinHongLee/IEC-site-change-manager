# -*- coding: utf-8 -*-
"""
image_processor.py — 照片預處理模組

功能：
- EXIF 旋轉校正（解決手機直拍照片方向錯誤問題）
- 最大邊限制縮放（保持原始比例，減輕 VBA 負擔）
- 格式轉換與品質優化
- 原檔自動備份

設計原則：
- Python 負責：EXIF 校正、控制檔案大小
- VBA 負責：精確置中、框內縮放
- 兩者配合，互不衝突
"""

import os
import shutil
from typing import Optional, List, Dict

try:
    from PIL import Image, ExifTags
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


# ========= 預設參數 =========
DEFAULT_MAX_EDGE = 1280      # 最大邊像素（你的標準）
DEFAULT_QUALITY = 85         # JPEG 品質
DEFAULT_BACKUP = True        # 備份原檔


def check_pillow() -> bool:
    """檢查 Pillow 是否可用"""
    return PILLOW_AVAILABLE


def fix_orientation(img: "Image.Image") -> "Image.Image":
    """
    根據 EXIF 資訊校正圖片方向
    
    EXIF Orientation 值對照：
    - 1: 正常
    - 3: 上下顛倒 (旋轉 180°)
    - 6: 順時針 90° (需逆時針轉 270°)
    - 8: 逆時針 90° (需順時針轉 90°)
    """
    if not PILLOW_AVAILABLE:
        return img
    
    try:
        # 尋找 Orientation tag
        orientation_key = None
        for key in ExifTags.TAGS.keys():
            if ExifTags.TAGS[key] == 'Orientation':
                orientation_key = key
                break
        
        if orientation_key is None:
            return img
        
        exif = img._getexif()
        if exif is None:
            return img
        
        orientation_value = exif.get(orientation_key)
        
        if orientation_value == 3:
            img = img.rotate(180, expand=True)
        elif orientation_value == 6:
            img = img.rotate(270, expand=True)
        elif orientation_value == 8:
            img = img.rotate(90, expand=True)
            
    except (AttributeError, KeyError, IndexError, TypeError):
        pass
    
    return img


def resize_max_edge(img: "Image.Image", max_edge: int = DEFAULT_MAX_EDGE) -> "Image.Image":
    """
    限制最大邊，保持原始比例
    
    例如：
    - 3024×2608 → 1280×1103 (橫向，最大邊=寬)
    - 2608×3024 → 1103×1280 (直向，最大邊=高)
    - 1280×720  → 不變（已在限制內）
    """
    w, h = img.size
    max_side = max(w, h)
    
    if max_side <= max_edge:
        return img  # 不需要縮放
    
    scale = max_edge / max_side
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    return img.resize((new_w, new_h), Image.Resampling.LANCZOS)


def preprocess_single_image(
    src_path: str,
    max_edge: int = DEFAULT_MAX_EDGE,
    quality: int = DEFAULT_QUALITY,
    backup: bool = DEFAULT_BACKUP
) -> Dict:
    """
    預處理單張圖片
    
    Args:
        src_path: 圖片路徑
        max_edge: 最大邊像素限制
        quality: JPEG 品質 (1-95)
        backup: 是否備份原檔為 .orig
    
    Returns:
        {
            "success": bool,
            "path": str,
            "original_size": (w, h),
            "new_size": (w, h),
            "backup_path": str or None,
            "error": str or None
        }
    """
    result = {
        "success": False,
        "path": src_path,
        "original_size": None,
        "new_size": None,
        "backup_path": None,
        "error": None
    }
    
    if not PILLOW_AVAILABLE:
        result["error"] = "Pillow 未安裝"
        return result
    
    if not os.path.exists(src_path):
        result["error"] = "檔案不存在"
        return result
    
    try:
        # 開啟圖片
        img = Image.open(src_path)
        result["original_size"] = img.size
        
        # 1. EXIF 旋轉校正
        img = fix_orientation(img)
        
        # 2. 轉換為 RGB（處理 PNG 透明、調色盤模式等）
        if img.mode in ('RGBA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 3. 最大邊縮放
        img = resize_max_edge(img, max_edge)
        result["new_size"] = img.size
        
        # 4. 備份原檔
        if backup:
            backup_path = src_path + ".orig"
            if not os.path.exists(backup_path):
                shutil.copy2(src_path, backup_path)
                result["backup_path"] = backup_path
        
        # 5. 儲存（覆蓋原檔）
        img.save(src_path, "JPEG", quality=quality, optimize=True)
        
        result["success"] = True
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result


def preprocess_folder(
    folder_path: str,
    max_edge: int = DEFAULT_MAX_EDGE,
    quality: int = DEFAULT_QUALITY,
    backup: bool = DEFAULT_BACKUP
) -> Dict:
    """
    預處理資料夾內的所有報告圖片
    
    會處理的檔案：
    - before.jpg, after.jpg (6-slot)
    - before_1.jpg, before_2.jpg, after_1.jpg, after_2.jpg (27-slot)
    
    Returns:
        {
            "processed": [檔名清單],
            "skipped": [檔名清單],
            "errors": [錯誤訊息清單],
            "details": {檔名: 處理結果}
        }
    """
    results = {
        "processed": [],
        "skipped": [],
        "errors": [],
        "details": {}
    }
    
    if not PILLOW_AVAILABLE:
        results["errors"].append("Pillow 未安裝")
        return results
    
    # 要處理的檔案清單
    target_files = [
        "before.jpg", "after.jpg",
        "before_1.jpg", "before_2.jpg",
        "after_1.jpg", "after_2.jpg"
    ]
    
    for filename in target_files:
        img_path = os.path.join(folder_path, filename)
        
        if not os.path.exists(img_path):
            continue
        
        result = preprocess_single_image(
            img_path,
            max_edge=max_edge,
            quality=quality,
            backup=backup
        )
        
        results["details"][filename] = result
        
        if result["success"]:
            results["processed"].append(filename)
        else:
            results["errors"].append(f"{filename}: {result['error']}")
    
    return results


def get_image_info(path: str) -> Optional[Dict]:
    """
    取得圖片資訊
    
    Returns:
        {
            "width": int,
            "height": int,
            "format": str,
            "mode": str,
            "size_kb": float,
            "orientation": str,  # "landscape" or "portrait"
            "needs_preprocessing": bool
        }
    """
    if not PILLOW_AVAILABLE:
        return None
    
    try:
        with Image.open(path) as img:
            w, h = img.size
            max_side = max(w, h)
            
            # 檢查是否有 EXIF 旋轉
            has_rotation = False
            try:
                for key in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[key] == 'Orientation':
                        exif = img._getexif()
                        if exif and exif.get(key) in (3, 6, 8):
                            has_rotation = True
                        break
            except Exception:
                pass
            
            return {
                "width": w,
                "height": h,
                "format": img.format,
                "mode": img.mode,
                "size_kb": os.path.getsize(path) / 1024,
                "orientation": "landscape" if w >= h else "portrait",
                "needs_preprocessing": max_side > DEFAULT_MAX_EDGE or has_rotation
            }
    except Exception:
        return None


def analyze_folder_images(folder_path: str) -> List[Dict]:
    """
    分析資料夾內圖片狀況，回報哪些需要預處理
    """
    issues = []
    
    if not PILLOW_AVAILABLE:
        return [{"file": "*", "issue": "Pillow 未安裝", "severity": "error"}]
    
    target_files = [
        "before.jpg", "after.jpg",
        "before_1.jpg", "before_2.jpg",
        "after_1.jpg", "after_2.jpg"
    ]
    
    for filename in target_files:
        img_path = os.path.join(folder_path, filename)
        
        if not os.path.exists(img_path):
            continue
        
        info = get_image_info(img_path)
        if info is None:
            issues.append({
                "file": filename,
                "issue": "無法讀取",
                "severity": "error"
            })
            continue
        
        # 檢查是否需要預處理
        if info["needs_preprocessing"]:
            max_side = max(info["width"], info["height"])
            if max_side > DEFAULT_MAX_EDGE:
                issues.append({
                    "file": filename,
                    "issue": f"尺寸過大 ({info['width']}×{info['height']})",
                    "severity": "warning",
                    "suggestion": f"建議預處理縮至 {DEFAULT_MAX_EDGE}px"
                })
            else:
                issues.append({
                    "file": filename,
                    "issue": "有 EXIF 旋轉資訊",
                    "severity": "info",
                    "suggestion": "建議預處理校正方向"
                })
        
        # 檢查檔案過大
        if info["size_kb"] > 2000:
            issues.append({
                "file": filename,
                "issue": f"檔案較大 ({info['size_kb']:.0f} KB)",
                "severity": "info",
                "suggestion": "預處理可壓縮至約 100-300 KB"
            })
    
    return issues


# ========= 給 GUI/流程呼叫的便利函數 =========

def auto_preprocess_if_needed(
    folder_path: str,
    max_edge: int = DEFAULT_MAX_EDGE,
    quality: int = DEFAULT_QUALITY,
    backup: bool = DEFAULT_BACKUP,
    force: bool = False
) -> Dict:
    """
    自動判斷並預處理（給流程內呼叫）
    
    Args:
        folder_path: 資料夾路徑
        max_edge: 最大邊限制
        quality: JPEG 品質
        backup: 備份原檔
        force: 強制處理（即使看起來不需要）
    
    Returns:
        處理結果 dict
    """
    if not PILLOW_AVAILABLE:
        return {"processed": [], "skipped": [], "errors": ["Pillow 未安裝"]}
    
    if not force:
        # 檢查是否有需要處理的圖片
        issues = analyze_folder_images(folder_path)
        needs_work = any(i["severity"] in ("warning", "error") for i in issues)
        
        if not needs_work:
            return {"processed": [], "skipped": ["all"], "errors": [], "message": "不需要預處理"}
    
    return preprocess_folder(folder_path, max_edge, quality, backup)


if __name__ == "__main__":
    # 測試
    print("=== 照片預處理模組 ===")
    print(f"Pillow 可用: {check_pillow()}")
    print(f"預設最大邊: {DEFAULT_MAX_EDGE}px")
    print(f"預設品質: {DEFAULT_QUALITY}")
    
    if check_pillow():
        # 測試分析
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        test_folder = os.path.join(base_dir, "attachments", "20260112", "0547_AG")
        if os.path.exists(test_folder):
            print(f"\n分析 {test_folder}:")
            issues = analyze_folder_images(test_folder)
            if issues:
                for issue in issues:
                    print(f"  [{issue.get('severity', '?')}] {issue['file']}: {issue['issue']}")
            else:
                print("  ✅ 所有圖片狀況良好")
