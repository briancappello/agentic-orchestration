from __future__ import annotations

from workbench.registry import Registry


def test_approve_withdraw_and_cascade(tmp_path):
    reg = Registry(tmp_path / "wb.db")
    with reg.reserve("billing", "Billing", "BIL", "projects/billing") as p:
        pass
    reg.approve(p.id, {"billing/a": "sha256:1", "billing/b": "sha256:2"}, "iss|ana", "Ana")
    got = reg.approvals(p.id)
    assert set(got) == {"billing/a", "billing/b"} and got["billing/a"]["approver_name"] == "Ana"

    reg.withdraw(p.id, ["billing/b"], "blocker_canceled", "billing/a3")
    assert set(reg.approvals(p.id)) == {"billing/a"}
    assert reg.rereviews(p.id)["billing/b"]["reason"] == "blocker_canceled"

    reg.approve(p.id, {"billing/b": "sha256:3"}, "iss|bo", "Bo")
    assert reg.rereviews(p.id) == {} and reg.approvals(p.id)["billing/b"]["digest"] == "sha256:3"

    reg.delete("billing")
    assert reg.approvals(p.id) == {} and reg.rereviews(p.id) == {}
