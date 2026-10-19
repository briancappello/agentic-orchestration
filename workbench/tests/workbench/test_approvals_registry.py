from __future__ import annotations


def test_approve_withdraw_and_cascade(open_registry):
    reg = open_registry()
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


def test_worker_commands_are_kept_per_story_and_deleted_with_the_project(open_registry):
    reg = open_registry()
    with reg.reserve("billing", "Billing", "BIL", "projects/billing") as p:
        pass
    with reg.reserve("other", "Other", "OTH", "projects/other") as q:
        pass
    reg.record_command(p.id, "T-1", "s1", "steer", "use the invoice table", "iss|ann", "Ann")
    reg.record_command(p.id, "T-1", "s2", "interrupt", None, "iss|bo", "Bo")
    reg.record_command(p.id, "T-2", "s3", "steer", "x", "iss|ann", "Ann")
    reg.record_command(q.id, "T-1", "s9", "steer", "y", "iss|ann", "Ann")
    got = reg.commands(p.id, "T-1")
    assert [(c["op"], c["actor_name"], c["session_id"]) for c in got] == [("steer", "Ann", "s1"), ("interrupt", "Bo", "s2")]
    assert got[0]["text"] == "use the invoice table" and got[0]["time"] <= got[1]["time"]

    reg.delete("billing")
    assert reg.commands(p.id, "T-1") == [] and len(reg.commands(q.id, "T-1")) == 1
