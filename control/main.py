# -*- coding: utf-8 -*-
"""
管線修改單產出系統

主入口點 - 可選擇 GUI 或 CLI 模式
"""

import sys
import os

# 確保可以 import 同目錄模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _ensure_utf8_console():
    """讓啟動守門訊息在 Windows 終端可正常輸出中文。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    """主程式入口"""
    import argparse
    _ensure_utf8_console()
    
    parser = argparse.ArgumentParser(
        description="管線修改單產出系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python main.py              # 啟動 GUI
  python main.py --cli        # 執行 CLI（處理全部）
  python main.py --date 20260112  # 只處理指定日期
  python main.py --retry      # 重試失敗項目
        """
    )
    
    parser.add_argument(
        '--cli', action='store_true',
        help='使用命令列模式（不啟動 GUI）'
    )
    parser.add_argument(
        '--date', type=str, nargs='+',
        help='指定要處理的日期（可多個，格式 YYYYMMDD）'
    )
    parser.add_argument(
        '--retry', action='store_true',
        help='重試所有失敗的項目'
    )
    parser.add_argument(
        '--no-pdf', action='store_true',
        help='不匯出 PDF'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='強制重新產出（忽略指紋）'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='啟用 Debug 模式'
    )
    parser.add_argument(
        '--health-check', action='store_true',
        help='只檢查專案資料夾健康狀態，不啟動 GUI/CLI'
    )
    parser.add_argument(
        '--audit-integrity', action='store_true',
        help='執行資料一致性稽核，不啟動 GUI/CLI'
    )
    parser.add_argument(
        '--repair-project', action='store_true',
        help='修復可安全自動修復的專案資料夾問題'
    )
    
    args = parser.parse_args()

    project_lock = None
    try:
        project_lock = _prepare_project_startup(args)
        if args.health_check or args.audit_integrity:
            return
    
        if args.cli or args.date or args.retry:
            # CLI 模式
            run_cli(args)
        else:
            # GUI 模式
            from gui import main as gui_main
            gui_main()
    finally:
        if project_lock is not None:
            project_lock.release()


def _prepare_project_startup(args):
    """啟動前專案守門，回傳已取得的 ProjectLock 或 None。"""
    from config import BASE_DIR
    from project_guard import (
        ProjectLock,
        format_guard_report,
        inspect_project,
        repair_project,
    )

    result = inspect_project(BASE_DIR)
    should_repair = args.repair_project or (
        not args.health_check and result.can_auto_repair
    )
    if should_repair:
        result = repair_project(BASE_DIR)

    if args.health_check or args.audit_integrity or result.repaired or result.has_blocking_issues:
        print(format_guard_report(result))

    if args.health_check or args.audit_integrity:
        if not result.has_blocking_issues:
            from integrity_audit import audit_integrity, format_integrity_report
            print()
            print(format_integrity_report(
                audit_integrity(BASE_DIR),
                max_refs=40 if args.audit_integrity else 12,
            ))
        return None

    if result.has_blocking_issues:
        msg = format_guard_report(result) + "\n\n專案資料夾有需要人工確認的問題，已停止啟動。"
        if _is_gui_request(args):
            _show_startup_message("專案資料夾需要確認", msg)
        print()
        print("專案資料夾有需要人工確認的問題，已停止啟動。")
        sys.exit(2)

    project_lock = ProjectLock(BASE_DIR)
    if not project_lock.acquire(start_heartbeat=True):
        existing = project_lock.read_existing() or {}
        user = existing.get("user", "未知使用者")
        host = existing.get("host", "未知電腦")
        heartbeat = existing.get("heartbeat_at", "未知時間")
        print("此專案目前已有另一個程式正在使用，為避免重複寫入已停止啟動。")
        print(f"使用者: {user}")
        print(f"電腦: {host}")
        print(f"最後心跳: {heartbeat}")
        print("若確認前一個程式已關閉，等待鎖定逾時後再重新啟動。")
        if _is_gui_request(args):
            _show_startup_message(
                "專案正在使用中",
                "此專案目前已有另一個程式正在使用，為避免重複寫入已停止啟動。\n\n"
                f"使用者: {user}\n"
                f"電腦: {host}\n"
                f"最後心跳: {heartbeat}\n\n"
                "若確認前一個程式已關閉，等待鎖定逾時後再重新啟動。",
            )
        sys.exit(3)
    return project_lock


def _is_gui_request(args) -> bool:
    return not (args.cli or args.date or args.retry or args.health_check or args.audit_integrity)


def _show_startup_message(title: str, message: str) -> None:
    """GUI 模式啟動失敗時顯示人看得到的訊息。"""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv[:1])
        QMessageBox.critical(None, title, message)
        app.processEvents()
    except Exception:
        pass


def run_cli(args):
    """執行 CLI 模式"""
    from config import (
        ATTACHMENTS_ROOT, OUTPUT_ROOT, PDF_OUTPUT_DIR, RUNTIME, use_dual_images
    )
    from parsers import parse_folder, weld_code_list, build_auto_description
    from material_pricebook import apply_material_pricing, load_material_pricebook
    from utils import (
        scan_date_folders, scan_subfolders, compute_fingerprint,
        find_attachment_pdf, copy_prefab_pdf, ProcessingSummary,
        parse_seq_from_report_id, clear_error_marker
    )
    from record_manager import (
        load_drawing_map, preload_record_index,
        upsert_record, upsert_detail_rows
    )
    from capabilities import detect_excel_com, format_excel_com_unavailable
    from excel_handler import generate_report, check_images_exist, get_excel_manager
    
    # 更新設定
    if args.no_pdf:
        RUNTIME.export_pdf = False
    if args.force:
        RUNTIME.skip_unchanged = False
    if args.debug:
        RUNTIME.debug_mode = True

    capability = detect_excel_com()
    if not capability.available:
        print(format_excel_com_unavailable(capability))
        sys.exit(4)
    
    print("=" * 50)
    print("管線修改單產出系統 - CLI 模式")
    print("=" * 50)
    
    # 決定要處理的日期
    all_dates = scan_date_folders(ATTACHMENTS_ROOT)
    
    if args.retry:
        # 找出有 _ERROR.txt 的資料夾
        dates_to_process = set()
        for date_str in all_dates:
            attach_dir = os.path.join(ATTACHMENTS_ROOT, date_str)
            for folder in scan_subfolders(attach_dir):
                error_file = os.path.join(attach_dir, folder, "_ERROR.txt")
                if os.path.exists(error_file):
                    dates_to_process.add(date_str)
                    # 清除錯誤標記
                    os.remove(error_file)
        dates_to_process = sorted(dates_to_process)
        print(f"🔄 找到 {len(dates_to_process)} 個日期有失敗項目")
    elif args.date:
        dates_to_process = [d for d in args.date if d in all_dates]
        invalid = [d for d in args.date if d not in all_dates]
        if invalid:
            print(f"⚠️ 以下日期不存在: {', '.join(invalid)}")
    else:
        dates_to_process = all_dates
    
    if not dates_to_process:
        print("沒有要處理的日期資料夾")
        return
    
    print(f"📅 將處理 {len(dates_to_process)} 個日期資料夾")
    print()
    
    # 載入資料
    print("📖 載入 DWG LIST...")
    drawing_map = load_drawing_map()
    
    print("📖 載入紀錄索引...")
    existing_key_set, key_to_row, key_to_meta, max_seq_by_date = preload_record_index()
    material_pricebook = load_material_pricebook()
    
    # 統計
    summary = ProcessingSummary()
    record_rows = []
    detail_rows = []
    materials_rows = []
    
    try:
        for date_str in dates_to_process:
            print(f"\n📁 處理日期: {date_str}")
            
            attach_dir = os.path.join(ATTACHMENTS_ROOT, date_str)
            subfolders = scan_subfolders(attach_dir)
            
            if not subfolders:
                continue
            
            idx_seq = max_seq_by_date.get(date_str, 0)
            out_dir = os.path.join(OUTPUT_ROOT, date_str)
            os.makedirs(out_dir, exist_ok=True)
            
            for folder in subfolders:
                folder_path = os.path.join(attach_dir, folder)
                
                try:
                    info = parse_folder(folder_path)
                    
                    line_number, dwg_no = drawing_map.get(info.series_no, ("", ""))
                    desc = build_auto_description(
                        info.tokens, info.note_text, RUNTIME.show_dims_in_desc
                    )
                    
                    # ① 圖片預處理（必須在指紋計算之前）
                    if RUNTIME.auto_preprocess_images:
                        try:
                            from image_processor import auto_preprocess_if_needed, check_pillow
                            if check_pillow():
                                pp_result = auto_preprocess_if_needed(
                                    folder_path,
                                    max_edge=RUNTIME.preprocess_max_edge,
                                    quality=RUNTIME.preprocess_quality,
                                    backup=RUNTIME.preprocess_backup,
                                    force=False,
                                )
                                if pp_result.get("processed"):
                                    print(f"  ↳ 預處理了 {len(pp_result['processed'])} 張圖片")
                        except ImportError:
                            pass

                    # ①-b 預製圖自動複製
                    prefab_copied = copy_prefab_pdf(folder_path, info.series_no)
                    if prefab_copied:
                        print(f"  ↳ 已複製預製圖: {os.path.basename(prefab_copied)}")

                    # ② 指紋計算（在預處理之後）
                    suffixes_raw = [t.raw for t in info.tokens]
                    dual = use_dual_images(info.mode, len(info.tokens))
                    fp_new = compute_fingerprint(
                        date_str, folder, info.series_no, suffixes_raw,
                        info.note_text, info.materials_text, folder_path,
                        is_group=(info.mode == "group"), use_dual_images=dual
                    )
                    
                    # ③ 略過檢查
                    key = (date_str, folder)
                    existed = key in existing_key_set
                    old_meta = key_to_meta.get(key, {})
                    
                    if existed and RUNTIME.skip_unchanged:
                        old_fp = (old_meta.get('fingerprint') or "").strip()
                        if old_fp and old_fp == fp_new:
                            report_id = old_meta.get('report_id') or f"{date_str}-??"
                            for t in info.tokens:
                                detail_rows.append(_build_detail_row(
                                    t, report_id, date_str, info.series_no, dwg_no, desc
                                ))
                            summary.add_skipped()
                            print(f"  ⏭️ {folder}（略過）")
                            continue
                    
                    # ④ 報告編號
                    if existed and old_meta.get('report_id'):
                        report_id = old_meta['report_id']
                        seq = parse_seq_from_report_id(report_id) or 0
                    else:
                        idx_seq += 1
                        seq = idx_seq
                        report_id = f"{date_str}-{seq:02}"
                        max_seq_by_date[date_str] = seq
                    
                    # 產出
                    result = generate_report(
                        folder_path=folder_path,
                        folder_name=folder,
                        date_str=date_str,
                        series_no=info.series_no,
                        mode=info.mode,
                        tokens=info.tokens,
                        note_text=info.note_text,
                        materials_text=info.materials_text,
                        line_number=line_number or "",
                        dwg_no=dwg_no or "",
                        report_id=report_id,
                        seq=seq,
                        output_dir=out_dir,
                        pdf_dir=PDF_OUTPUT_DIR,
                        description=desc,
                    )
                    
                    if result.success:
                        summary.add_success()
                        clear_error_marker(folder_path)
                        print(f"  ✅ {folder}")
                        
                        # Record
                        codes = weld_code_list(info.tokens)
                        images = check_images_exist(folder_path, info.mode, len(info.tokens))
                        dims_pairs = [f"{t.weld_no}{t.tag}={t.size}"
                            for t in info.tokens if t.weld_no and t.tag and t.size]
                        ap_name = os.path.basename(find_attachment_pdf(folder_path, info.series_no) or "") or "無"
                        
                        record_rows.append({
                            "日期": date_str,
                            "報告編號": report_id,
                            "Series NO": info.series_no,
                            "LINE NUMBER": line_number or "",
                            "DWG NO": dwg_no or "",
                            "變更類型": "裁切重焊" if all(t.is_cut for t in info.tokens) else "加長",
                            "焊口清單": "、".join(codes),
                            "焊口與尺寸": "；".join(dims_pairs),
                            "說明": desc,
                            "材料附加": info.materials_text,
                            "附件PDF": ap_name,
                            "資料夾名": folder,
                            "before.jpg": "有" if images['has_before'] else "無",
                            "after.jpg": "有" if images['has_after'] else "無",
                            "內容指紋": fp_new,
                        })
                        
                        for t in info.tokens:
                            detail_rows.append(_build_detail_row(
                                t, report_id, date_str, info.series_no, dwg_no, desc
                            ))
                        
                        # 材料明細
                        from parsers import parse_materials_txt
                        parsed_mats = apply_material_pricing(
                            parse_materials_txt(folder_path),
                            material_pricebook,
                        )
                        for mat in parsed_mats:
                            materials_rows.append({
                                "項目": None,
                                "報告編號": report_id,
                                "修改日期": date_str,
                                "Series NO": info.series_no,
                                "零件類型": mat.get("零件類型", ""),
                                "尺寸": mat.get("尺寸", ""),
                                "SCH": mat.get("SCH", ""),
                                "材質": mat.get("材質", ""),
                                "類別": mat.get("類別", "材料"),
                                "數量": mat.get("數量", ""),
                                "單位": mat.get("單位", ""),
                                "單價": mat.get("單價", ""),
                                "金額": mat.get("金額", ""),
                                "單價來源": mat.get("單價來源", ""),
                                "金額來源": mat.get("金額來源", ""),
                                "價目表ID": mat.get("價目表ID", ""),
                                "價目來源": mat.get("價目來源", ""),
                                "價目生效日": mat.get("價目生效日", ""),
                                "配價狀態": mat.get("配價狀態", ""),
                                "備註": mat.get("備註", ""),
                            })
                    else:
                        summary.add_failed(f"{date_str}\\{folder}")
                        print(f"  ❌ {folder}: {result.error}")
                
                except Exception as e:
                    summary.add_failed(f"{date_str}\\{folder}")
                    print(f"  ❌ {folder}: {e}")
        
        # 儲存
        if record_rows:
            upsert_record(record_rows)
            print(f"\n📝 已更新 record: {len(record_rows)} 筆")
        
        if detail_rows:
            upsert_detail_rows(detail_rows)
            print(f"📝 已更新明細: {len(detail_rows)} 筆")
        
        if materials_rows:
            from record_manager import upsert_materials_rows
            upsert_materials_rows(materials_rows)
            print(f"📝 已更新材料明細: {len(materials_rows)} 筆")
        
        # 摘要
        summary.print_summary()
    
    finally:
        try:
            em = get_excel_manager()
            em.quit()
        except Exception:
            pass


def _build_detail_row(token, report_id, date_str, series_no, dwg_no, desc):
    """建立明細列"""
    weld_code = token.code if hasattr(token, 'code') else token.get('raw', '')
    size_val = token.size if hasattr(token, 'size') else token.get('size')
    
    return {
        "項目": None,
        "紀錄編號": report_id,
        "修改日期": date_str,
        "修改原因敘述": desc,
        "Series NO": series_no,
        "DWG NO": dwg_no or "",
        "焊口編號": weld_code,
        "焊口尺寸": size_val if size_val else "",
        "係數": "",
        "單價/DB": "",
        "金額": "",
        "備註": "",
    }


if __name__ == "__main__":
    main()
