# -*- coding: utf-8 -*-
"""billing_calculator.py 單元測試"""

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from billing_calculator import (
    amount_to_text,
    build_billing_rows,
    calculate_tax_amount,
    calculate_report_amounts,
    money_to_text,
    parse_amount,
    round_twd,
    tax_rate_to_text,
)


class TestParseAmount:
    def test_parse_money_text(self):
        assert parse_amount("$1,250元") == Decimal("1250")
        assert parse_amount("NT$ 1,250.5") == Decimal("1250.5")

    def test_empty_or_invalid_returns_none(self):
        assert parse_amount("") is None
        assert parse_amount("abc") is None

    def test_amount_to_text(self):
        assert amount_to_text(Decimal("1200.00")) == "1200"
        assert amount_to_text(Decimal("12.50")) == "12.5"
        assert amount_to_text(0) == ""

    def test_billing_money_rounding_is_twd_half_up(self):
        assert round_twd(Decimal("100.5")) == Decimal("101")
        assert round_twd(Decimal("100.4")) == Decimal("100")
        assert money_to_text(Decimal("100.5")) == "101"
        assert money_to_text(Decimal("0.4")) == ""

    def test_tax_amount_uses_five_percent_exclusive_tax(self):
        assert tax_rate_to_text() == "5%"
        assert calculate_tax_amount("110") == Decimal("6")


class TestCalculateReportAmounts:
    def test_sums_weld_and_material_amounts(self):
        store = {
            "details": [
                {"紀錄編號": "R-1", "金額": "100"},
                {"紀錄編號": "R-1", "金額": "$250"},
            ],
            "materials": [
                {"報告編號": "R-1", "金額": "300"},
                {"報告編號": "R-1", "數量": "2", "單價": "50"},
            ],
        }

        totals = calculate_report_amounts(store)

        assert totals["R-1"].weld_amount == Decimal("350")
        assert totals["R-1"].material_amount == Decimal("400")
        assert totals["R-1"].total == Decimal("750")


class TestBuildBillingRows:
    def test_uses_calculated_amounts_when_billing_is_empty(self):
        store = {
            "records": [{"報告編號": "R-1", "日期": "20260101", "Series NO": "0001", "說明": "測試"}],
            "details": [{"紀錄編號": "R-1", "金額": "100"}],
            "materials": [{"報告編號": "R-1", "數量": "2", "單價": "80"}],
        }

        rows = build_billing_rows(store, {})

        assert rows[0]["weld_amount"] == "100"
        assert rows[0]["material_amount"] == "160"
        assert rows[0]["total"] == "260"
        assert rows[0]["tax_rate"] == "5%"
        assert rows[0]["tax_amount"] == "13"
        assert rows[0]["grand_total"] == "273"
        assert rows[0]["material_amount_source"] == "calculated"

    def test_manual_weld_and_material_override_but_total_is_derived(self):
        store = {
            "records": [{"報告編號": "R-1"}],
            "details": [{"紀錄編號": "R-1", "金額": "100"}],
            "materials": [{"報告編號": "R-1", "金額": "200"}],
        }
        billing = {
            "R-1": {
                "weld_amount": "90",
                "material_amount": "180",
                "total": "999",
            }
        }

        rows = build_billing_rows(store, billing)

        assert rows[0]["weld_amount"] == "90"
        assert rows[0]["material_amount"] == "180"
        assert rows[0]["total"] == "270"
        assert rows[0]["total_source"] == "calculated"
        assert rows[0]["tax_amount"] == "14"
        assert rows[0]["grand_total"] == "284"
        assert rows[0]["manual_total"] == "999"
        assert rows[0]["total_mismatch"] == "1"
        assert rows[0]["total_mismatch_amount"] == "729"

    def test_invalid_legacy_manual_total_is_flagged(self):
        store = {
            "records": [{"報告編號": "R-1"}],
            "details": [{"紀錄編號": "R-1", "金額": "100"}],
            "materials": [],
        }
        billing = {"R-1": {"total": "待確認"}}

        rows = build_billing_rows(store, billing)

        assert rows[0]["total"] == "100"
        assert rows[0]["manual_total"] == "待確認"
        assert rows[0]["total_mismatch"] == "1"
        assert rows[0]["total_mismatch_amount"] == ""

    def test_billing_rows_round_subtotal_before_tax(self):
        store = {
            "records": [{"報告編號": "R-1"}],
            "details": [],
            "materials": [{"報告編號": "R-1", "數量": "1", "單價": "100.5"}],
        }

        rows = build_billing_rows(store, {})

        assert rows[0]["material_amount"] == "101"
        assert rows[0]["total"] == "101"
        assert rows[0]["tax_amount"] == "5"
        assert rows[0]["grand_total"] == "106"
        assert rows[0]["rounding_rule"] == "TWD_HALF_UP"
