# -*- coding: utf-8 -*-
"""
test_parsers.py — parsers.py 的單元測試

測試涵蓋：
- 資料夾名稱解析（detect_mode）
- 焊口代碼解析（parse_suffix_combo）
- 說明文字建構（build_auto_description）
- 焊口代碼列表（weld_code_list）
"""

import os
import sys
import pytest

# 加入 control 目錄到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from parsers import (
    detect_mode,
    parse_suffix_combo,
    parse_weld_code_basic,
    weld_code_list,
    build_auto_description,
    WeldToken,
    FolderInfo,
)


# ========= detect_mode =========

class TestDetectMode:
    """資料夾名稱解析測試"""

    def test_single_basic(self):
        mode, series, extra = detect_mode("234_15r1")
        assert mode == "single"
        assert series == "0234"
        assert extra == "15r1"

    def test_single_multi_weld(self):
        mode, series, extra = detect_mode("234_15r1_12r1_10r1_9a1_9b1")
        assert mode == "single"
        assert series == "0234"
        assert extra == "15r1_12r1_10r1_9a1_9b1"

    def test_single_short_series(self):
        mode, series, extra = detect_mode("9_3r0.5_5r0.5")
        assert mode == "single"
        assert series == "0009"
        assert extra == "3r0.5_5r0.5"

    def test_single_long_series(self):
        mode, series, extra = detect_mode("1001_2a1")
        assert mode == "single"
        assert series == "1001"

    def test_group_AG(self):
        mode, series, extra = detect_mode("101_AG")
        assert mode == "group"
        assert series == "0101"
        assert extra == "A"

    def test_group_BG(self):
        mode, series, extra = detect_mode("111_BG")
        assert mode == "group"
        assert series == "0111"
        assert extra == "B"

    def test_group_lowercase(self):
        """小寫 group 標籤也要能辨識"""
        mode, series, extra = detect_mode("632_aG")
        assert mode == "group"
        assert extra == "A"

    def test_invalid_no_underscore(self):
        with pytest.raises(ValueError):
            detect_mode("abc")

    def test_invalid_empty(self):
        with pytest.raises(ValueError):
            detect_mode("")


# ========= parse_suffix_combo =========

class TestParseSuffixCombo:
    """焊口字串解析測試"""

    def test_single_token(self):
        tokens = parse_suffix_combo("15r1")
        assert len(tokens) == 1
        t = tokens[0]
        assert t.weld_no == "15"
        assert t.tag == "r"
        assert t.size == 1.0
        assert t.is_cut is True

    def test_multiple_tokens(self):
        tokens = parse_suffix_combo("15r1_12a0.5_10r1")
        assert len(tokens) == 3
        assert tokens[0].weld_no == "15"
        assert tokens[1].tag == "a"
        assert tokens[1].size == 0.5
        assert tokens[1].is_cut is False
        assert tokens[2].is_cut is True

    def test_decimal_size(self):
        tokens = parse_suffix_combo("248_15r1.5")
        # "248" 是只有數字沒有 tag 的 token
        assert len(tokens) == 2
        assert tokens[1].raw == "15r1.5"
        assert tokens[1].size == 1.5

    def test_token_without_size(self):
        tokens = parse_suffix_combo("15r")
        assert len(tokens) == 1
        assert tokens[0].weld_no == "15"
        assert tokens[0].tag == "r"
        assert tokens[0].size is None

    def test_b_tag(self):
        tokens = parse_suffix_combo("9b1")
        assert tokens[0].tag == "b"
        assert tokens[0].is_cut is False

    def test_empty_string(self):
        tokens = parse_suffix_combo("")
        assert tokens == []

    def test_code_property(self):
        tokens = parse_suffix_combo("15r1")
        assert tokens[0].code == "15r"


# ========= parse_weld_code_basic =========

class TestParseWeldCodeBasic:
    """基本焊口代碼解析"""

    def test_basic(self):
        result = parse_weld_code_basic("15a")
        assert result["weld_no"] == "15"
        assert result["tag"] == "a"
        assert result["is_cut"] is False

    def test_cut(self):
        result = parse_weld_code_basic("12r")
        assert result["is_cut"] is True

    def test_no_tag(self):
        result = parse_weld_code_basic("100")
        assert result["weld_no"] == "100"
        assert result["tag"] == ""


# ========= weld_code_list =========

class TestWeldCodeList:
    """焊口代碼列表"""

    def test_basic(self):
        tokens = [
            WeldToken(raw="15r1", weld_no="15", tag="r", size=1.0, is_cut=True),
            WeldToken(raw="12a0.5", weld_no="12", tag="a", size=0.5, is_cut=False),
        ]
        codes = weld_code_list(tokens)
        assert codes == ["15r", "12a"]

    def test_empty(self):
        assert weld_code_list([]) == []


# ========= build_auto_description =========

class TestBuildAutoDescription:
    """自動說明文字建構"""

    def test_all_cut(self):
        tokens = [
            WeldToken(raw="15r1", weld_no="15", tag="r", size=1.0, is_cut=True),
            WeldToken(raw="12r1", weld_no="12", tag="r", size=1.0, is_cut=True),
        ]
        desc = build_auto_description(tokens, "")
        assert "裁切" in desc
        assert "15r" in desc and "12r" in desc

    def test_add_length(self):
        tokens = [
            WeldToken(raw="15a1", weld_no="15", tag="a", size=1.0, is_cut=False),
        ]
        desc = build_auto_description(tokens, "")
        assert "加長" in desc
        assert "15a" in desc

    def test_with_note(self):
        tokens = [
            WeldToken(raw="15r1", weld_no="15", tag="r", size=1.0, is_cut=True),
        ]
        desc = build_auto_description(tokens, "手動說明文字")
        assert "手動說明文字" in desc
        assert "15r" in desc

    def test_with_dims(self):
        tokens = [
            WeldToken(raw="15r1", weld_no="15", tag="r", size=1.0, is_cut=True),
        ]
        desc = build_auto_description(tokens, "", show_dims=True)
        assert "15r=1" in desc


# ========= WeldToken =========

class TestWeldToken:
    """WeldToken 資料結構"""

    def test_to_dict(self):
        t = WeldToken(raw="15r1", weld_no="15", tag="r", size=1.0, is_cut=True)
        d = t.to_dict()
        assert d["raw"] == "15r1"
        assert d["weld_no"] == "15"
        assert d["is_cut"] is True

    def test_code_no_info(self):
        t = WeldToken(raw="xxx")
        assert t.code == "xxx"

    def test_code_with_info(self):
        t = WeldToken(raw="15r1", weld_no="15", tag="r")
        assert t.code == "15r"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
