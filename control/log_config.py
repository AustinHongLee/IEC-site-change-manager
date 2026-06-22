# -*- coding: utf-8 -*-
"""
log_config.py — 統一日誌管理模組

功能：
- 集中管理整個專案的日誌
- 同時輸出到控制台和檔案
- 自動輪替（日誌不會無限長大）
- 取代散落各處的 print()
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from resources import project_path


# ========= 日誌目錄 =========
def _get_log_dir() -> str:
    """取得日誌目錄"""
    log_dir = project_path("logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


# ========= 修正 Windows 主控台編碼 =========
def _fix_console_encoding():
    """確保 stdout/stderr 能正確輸出 UTF-8 中文（Windows 主控台 cp1252/cp950 相容）"""
    for attr in ('stdout', 'stderr'):
        stream = getattr(sys, attr)
        try:
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


_fix_console_encoding()


# ========= 格式化器 =========
_CONSOLE_FMT = "%(message)s"
_FILE_FMT = "[%(asctime)s] %(name)-18s %(levelname)-7s %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


# ========= 全域初始化旗標 =========
_initialized = False


def setup_logging(
    level: int = logging.DEBUG,
    log_file: str = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    初始化日誌系統（只會執行一次）

    Args:
        level: 日誌等級
        log_file: 日誌檔案名稱（預設自動產生）
        max_bytes: 單檔最大大小
        backup_count: 保留的舊日誌檔數量

    Returns:
        root logger（之後各模組用 getLogger(__name__) 就好）
    """
    global _initialized
    if _initialized:
        return logging.getLogger("app")

    log_dir = _get_log_dir()

    if log_file is None:
        log_file = os.path.join(log_dir, "app.log")

    root = logging.getLogger()
    root.setLevel(level)

    # 避免重複加 handler
    if not root.handlers:
        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(_CONSOLE_FMT))
        root.addHandler(console_handler)

        # 檔案 handler（含輪替）
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(_FILE_FMT, datefmt=_DATE_FMT)
            )
            root.addHandler(file_handler)
        except Exception as e:
            # 如果無法寫檔，至少控制台還能用
            print(f"⚠️ 無法建立日誌檔案: {e}")

    _initialized = True

    logger = logging.getLogger("app")
    logger.info("=" * 50)
    logger.info("管線修改單產出系統 - 日誌啟動")
    logger.info(f"日誌檔案: {log_file}")
    logger.info("=" * 50)
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    取得 logger（各模組使用此函數）

    Usage:
        from log_config import get_logger
        logger = get_logger(__name__)
        logger.info("...")
        logger.warning("...")
        logger.error("...")
    """
    if not _initialized:
        setup_logging()
    return logging.getLogger(name or "app")
