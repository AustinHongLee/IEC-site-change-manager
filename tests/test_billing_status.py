# -*- coding: utf-8 -*-
"""billing_status.py 單元測試"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from billing_status import (
    is_billing_locked,
    normalize_billing_status,
    validate_billing_status_changes,
    validate_billing_transition,
)


def test_empty_status_normalizes_to_unbilled():
    assert normalize_billing_status("") == "未請款"
    assert normalize_billing_status(None) == "未請款"


def test_known_locked_statuses_are_shared_rule():
    assert is_billing_locked("請款中") is True
    assert is_billing_locked("已付款") is True
    assert is_billing_locked("暫緩") is False
    assert is_billing_locked("") is False


def test_valid_transition_passes():
    assert validate_billing_transition("未請款", "請款中") is None
    assert validate_billing_transition("請款中", "已請款") is None
    assert validate_billing_transition("已付款", "已結案") is None


def test_jump_transition_is_rejected():
    message = validate_billing_transition("未請款", "已請款")

    assert message == "請款狀態不可由「未請款」直接改為「已請款」"


def test_unknown_new_status_is_rejected():
    message = validate_billing_transition("未請款", "送審完成")

    assert message == "請款狀態「送審完成」不是系統允許的狀態"


def test_validate_billing_status_changes_returns_report_context():
    issues = validate_billing_status_changes(
        {"R-1": {"status": "未請款"}},
        {"R-1": {"status": "已請款"}},
    )

    assert len(issues) == 1
    assert issues[0].report_id == "R-1"
    assert issues[0].old_status == "未請款"
    assert issues[0].new_status == "已請款"
