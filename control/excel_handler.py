# -*- coding: utf-8 -*-
"""
excel_handler.py — Excel/PDF 操作模組

包含：
- Excel COM 連線管理
- 模板操作
- PDF 匯出
- 圖片插入
"""

import os
import time
import atexit
from typing import List, Dict, Optional
from dataclasses import dataclass

from capabilities import CapabilityResult, format_excel_com_unavailable
from config import RUNTIME, get_template_for_mode, use_dual_images
from utils import (
    safe_remove, check_integrity, write_error_marker,
    find_attachment_pdf, merge_into_second_page
)


# ========= Excel 連線管理 =========
class ExcelComUnavailable(RuntimeError):
    """Raised when the optional Excel COM backend cannot be loaded."""


def _load_excel_com_modules():
    try:
        import win32com.client as win32_client
        from win32com.client import constants as win32_constants
        return win32_client, win32_constants
    except Exception as exc:
        result = CapabilityResult(
            name="excel_com",
            available=False,
            reason="缺少 pywin32 的 win32com 模組",
            detail=str(exc),
        )
        raise ExcelComUnavailable(format_excel_com_unavailable(result)) from exc


class ExcelManager:
    """Excel COM 連線管理器（單例模式）"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._excel = None
        self._initialized = True
        atexit.register(self.quit)
    
    def _is_connected(self) -> bool:
        """檢查 Excel COM 物件是否仍然有效"""
        if self._excel is None:
            return False
        try:
            # 嘗試存取一個屬性來測試連線
            _ = self._excel.Version
            return True
        except Exception:
            return False
    
    @property
    def excel(self):
        """取得 Excel Application（懶載入 + 自動重連）"""
        if not self._is_connected():
            self._start_excel()
        return self._excel
    
    def _start_excel(self):
        """啟動 Excel"""
        # 先清理舊的（如果有）
        if self._excel is not None:
            try:
                self._excel.Quit()
            except Exception:
                pass
            self._excel = None
            time.sleep(0.3)
        
        win32_client, win32_constants = _load_excel_com_modules()
        try:
            self._excel = win32_client.DispatchEx("Excel.Application")
        except Exception as exc:
            result = CapabilityResult(
                name="excel_com",
                available=False,
                reason="無法啟動 Excel COM",
                detail=str(exc),
            )
            raise ExcelComUnavailable(format_excel_com_unavailable(result)) from exc
        try:
            self._excel.Visible = False
        except Exception:
            pass
        try:
            self._excel.DisplayAlerts = False
        except Exception:
            pass
        try:
            self._excel.AutomationSecurity = win32_constants.msoAutomationSecurityLow
        except Exception:
            pass
    
    def quit(self):
        """關閉 Excel"""
        if self._excel is not None:
            try:
                self._excel.Quit()
            except Exception:
                pass
            self._excel = None
    
    def restart(self):
        """重啟 Excel"""
        self.quit()
        time.sleep(0.5)
        self._start_excel()


# 全域實例
_excel_manager = None

def get_excel_manager() -> ExcelManager:
    """取得 Excel 管理器"""
    global _excel_manager
    if _excel_manager is None:
        _excel_manager = ExcelManager()
    return _excel_manager


# ========= 模板操作 =========
def _flatten_weld_slots(cfg: dict) -> List[str]:
    """展平焊口儲存格列表"""
    if "weld_slots" in cfg and cfg["weld_slots"]:
        return list(cfg["weld_slots"])
    grid = cfg.get("weld_slots_grid", [])
    flat = []
    for row in grid:
        flat.extend(row)
    return flat


def fill_weld_slots(ws, tpl_cfg: dict, texts: List[str]):
    """填入焊口代碼"""
    cells = _flatten_weld_slots(tpl_cfg)
    n = min(len(texts), len(cells))
    for i in range(n):
        ws.Range(cells[i]).Value = texts[i]
    
    overflow = len(texts) - len(cells)
    behavior = tpl_cfg.get("overflow_behavior", "ellipsis_last_cell")
    if overflow > 0 and cells:
        if behavior == "ellipsis_last_cell":
            ws.Range(cells[-1]).Value = f"... (+{overflow} more)"


def export_pdf_with_retry(ws, pdf_path: str) -> bool:
    """匯出 PDF（含重試）"""
    for _ in range(RUNTIME.max_retries):
        try:
            ws.ExportAsFixedFormat(0, pdf_path)
            if check_integrity(None, pdf_path, level=1):
                return True
        except Exception:
            pass
        time.sleep(RUNTIME.retry_sleep)
    return False


# ========= 報告產出 =========
@dataclass
class ReportResult:
    """報告產出結果"""
    success: bool
    output_file: Optional[str] = None
    pdf_file: Optional[str] = None
    error: Optional[str] = None


def generate_report(
    folder_path: str,
    folder_name: str,
    date_str: str,
    series_no: str,
    mode: str,
    tokens: List,  # List[WeldToken]
    note_text: str,
    materials_text: str,
    line_number: str,
    dwg_no: str,
    report_id: str,
    seq: int,
    output_dir: str,
    pdf_dir: str,
    description: str,
    on_progress: callable = None,
) -> ReportResult:
    """
    產出單份報告
    
    Args:
        folder_path: 來源資料夾路徑
        folder_name: 資料夾名稱
        date_str: 日期字串
        series_no: 系列號
        mode: "single" 或 "group"
        tokens: 焊口資訊列表
        note_text: 說明文字
        materials_text: 材料文字
        line_number: LINE NUMBER
        dwg_no: DWG NO
        report_id: 報告編號
        seq: 序號
        output_dir: XLSM 輸出目錄
        pdf_dir: PDF 輸出目錄
        description: 說明
        on_progress: 進度回呼函數
    
    Returns:
        ReportResult
    """
    try:
        em = get_excel_manager()
        excel = em.excel
    except ExcelComUnavailable as e:
        return ReportResult(success=False, error=str(e))
    
    # 選擇模板
    tpl = get_template_for_mode(mode, len(tokens))
    
    # 取得焊口代碼
    codes = [t.code if hasattr(t, 'code') else f"{t.get('weld_no','')}{t.get('tag','')}" for t in tokens]
    codes = [c for c in codes if c]
    
    wb = None
    try:
        wb = excel.Workbooks.Open(tpl["path"])
        
        try:
            ws = wb.Sheets(tpl["sheet"])
        except Exception:
            ws = wb.Sheets(1)
        
        # 填入基本欄位
        ws.Range(tpl["id_cell"]).NumberFormat = "@"
        ws.Range(tpl["id_cell"]).Value = report_id
        ws.Range(tpl["date_cell"]).NumberFormat = "@"
        ws.Range(tpl["date_cell"]).Value = date_str
        ws.Range(tpl["series_cell"]).Value = series_no
        ws.Range(tpl["line_cell"]).Value = line_number or ""
        ws.Range(tpl["dwg_cell"]).Value = dwg_no or ""
        ws.Range(tpl["desc_cell"]).Value = description
        
        # 清空並填入焊口
        for cell in _flatten_weld_slots(tpl):
            try:
                ws.Range(cell).Value = ""
            except Exception:
                pass
        fill_weld_slots(ws, tpl, codes)
        
        # 插入圖片
        before_img = os.path.join(folder_path, 'before.jpg')
        after_img = os.path.join(folder_path, 'after.jpg')
        macro = f"'{wb.Name}'!InsertAndFitPicture_ByAddr"
        
        wb.Activate()
        ws.Activate()
        excel.Application.Goto(ws.Range("A1"), False)
        
        if "before_ranges" in tpl and "after_ranges" in tpl:
            # 27-slot 模式
            b1 = os.path.join(folder_path, 'before_1.jpg')
            b2 = os.path.join(folder_path, 'before_2.jpg')
            a1 = os.path.join(folder_path, 'after_1.jpg')
            a2 = os.path.join(folder_path, 'after_2.jpg')
            
            if os.path.exists(b1):
                excel.Application.Run(macro, tpl["sheet"], b1, tpl["before_ranges"][0], True, 6, True, 0.96, 0, 0)
            if os.path.exists(b2):
                excel.Application.Run(macro, tpl["sheet"], b2, tpl["before_ranges"][1], True, 6, True, 0.96, 0, 0)
            if os.path.exists(a1):
                excel.Application.Run(macro, tpl["sheet"], a1, tpl["after_ranges"][0], True, 6, True, 0.96, 0, 6)
            if os.path.exists(a2):
                excel.Application.Run(macro, tpl["sheet"], a2, tpl["after_ranges"][1], True, 6, True, 0.96, 0, 6)
            
            # Fallback
            if not os.path.exists(b1) and os.path.exists(before_img):
                excel.Application.Run(macro, tpl["sheet"], before_img, tpl["before_ranges"][0], True, 6, True, 0.96, 0, 0)
            if not os.path.exists(a1) and os.path.exists(after_img):
                excel.Application.Run(macro, tpl["sheet"], after_img, tpl["after_ranges"][0], True, 6, True, 0.96, 0, 6)
        else:
            # 6-slot 模式
            if os.path.exists(before_img):
                excel.Application.Run(macro, tpl["sheet"], before_img, tpl["before_range"], True, 6, True, 0.96, 0, 0)
            if os.path.exists(after_img):
                excel.Application.Run(macro, tpl["sheet"], after_img, tpl["after_range"], True, 6, True, 0.96, 0, 6)
        
        # 儲存 XLSM
        out_name = f"管線修改單_{series_no}_{seq:02}.xlsm"
        output_file = os.path.join(output_dir, out_name)
        safe_remove(output_file)
        wb.SaveAs(output_file, FileFormat=52)
        
        if on_progress:
            on_progress(f"已儲存 XLSM: {out_name}")
        
        # 匯出 PDF
        pdf_path = os.path.join(pdf_dir, f"{report_id}.pdf")
        safe_remove(pdf_path)
        pdf_for_integrity = pdf_path if RUNTIME.export_pdf else None
        
        if RUNTIME.export_pdf:
            ok_pdf = export_pdf_with_retry(ws, pdf_path)
            if not ok_pdf:
                write_error_marker(folder_path, "ExportAsFixedFormat failed after retries")
            
            # 合併附件 PDF
            attach_pdf = find_attachment_pdf(folder_path, series_no)
            if attach_pdf and os.path.exists(pdf_path):
                try:
                    merge_into_second_page(pdf_path, attach_pdf)
                    if on_progress:
                        on_progress(f"PDF 已合併附件: {os.path.basename(attach_pdf)}")
                except Exception as e:
                    write_error_marker(folder_path, f"merge failed: {e}")
        
        wb.Close(SaveChanges=False)
        wb = None
        
        # 最終完整性檢查
        integrity_level = RUNTIME.integrity_level_default
        if mode == "group" or len(tokens) > 9:
            integrity_level = 0
        
        attach_pdf = find_attachment_pdf(folder_path, series_no)
        with_aps = [attach_pdf] if attach_pdf else None
        
        if not check_integrity(output_file, pdf_for_integrity, level=integrity_level, with_attachments=with_aps):
            write_error_marker(folder_path, "post-export integrity failed")
            return ReportResult(success=False, error="完整性檢查失敗")
        
        return ReportResult(success=True, output_file=output_file, pdf_file=pdf_for_integrity)
    
    except Exception as e:
        if wb is not None:
            try:
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        return ReportResult(success=False, error=str(e))


def check_images_exist(folder_path: str, mode: str, token_count: int) -> Dict[str, bool]:
    """檢查圖片是否存在"""
    result = {}
    
    if use_dual_images(mode, token_count):
        result['before_1'] = os.path.exists(os.path.join(folder_path, 'before_1.jpg'))
        result['before_2'] = os.path.exists(os.path.join(folder_path, 'before_2.jpg'))
        result['after_1'] = os.path.exists(os.path.join(folder_path, 'after_1.jpg'))
        result['after_2'] = os.path.exists(os.path.join(folder_path, 'after_2.jpg'))
        # Fallback
        result['before'] = os.path.exists(os.path.join(folder_path, 'before.jpg'))
        result['after'] = os.path.exists(os.path.join(folder_path, 'after.jpg'))
        result['has_before'] = result['before_1'] or result['before_2'] or result['before']
        result['has_after'] = result['after_1'] or result['after_2'] or result['after']
    else:
        result['before'] = os.path.exists(os.path.join(folder_path, 'before.jpg'))
        result['after'] = os.path.exists(os.path.join(folder_path, 'after.jpg'))
        result['has_before'] = result['before']
        result['has_after'] = result['after']
    
    return result
