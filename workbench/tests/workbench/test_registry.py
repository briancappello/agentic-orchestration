from __future__ import annotations

import sqlite3
import subprocess
import threading

import pytest

import planlib
from workbench.registry import Registry, RegistryError, check_new, suggest_slug
from workbench.scaffold import ScaffoldError, scaffold_store


def test_migrates_once_and_reopens(tmp_path):
    reg = Registry(tmp_path / "wb.db")
    with reg.reserve("billing", "Billing", "BILL", "projects/billing"):
        pass
    reg.close()
    again = Registry(tmp_path / "wb.db")
    assert [p.slug for p in again.list()] == ["billing"]
    assert sqlite3.connect(tmp_path / "wb.db").execute("PRAGMA user_version").fetchone()[0] == 1


def test_slug_tracker_key_and_store_are_unique(tmp_path):
    reg = Registry(tmp_path / "wb.db")
    with reg.reserve("billing", "Billing", "BILL", "projects/billing"):
        pass
    for args, code in [
        (("billing", "Other", "OTH", "projects/other"), "slug_taken"),
        (("other", "Other", "BILL", "projects/other"), "huly_project_taken"),
        (("other", "Other", "OTH", "projects/billing"), "store_taken"),
    ]:
        with pytest.raises(RegistryError) as err:
            with reg.reserve(*args):
                pass
        assert err.value.code == code and err.value.status == 409


def test_a_failed_block_rolls_the_insert_back(tmp_path):
    reg = Registry(tmp_path / "wb.db")
    with pytest.raises(RuntimeError):
        with reg.reserve("billing", "Billing", "BILL", "projects/billing"):
            raise RuntimeError("tracker down")
    assert reg.list() == []
    with reg.reserve("billing", "Billing", "BILL", "projects/billing"):
        pass
    assert reg.get("billing").name == "Billing"


def test_a_concurrent_create_of_the_same_slug_waits_then_fails(tmp_path):
    reg = Registry(tmp_path / "wb.db")
    inside, release, results = threading.Event(), threading.Event(), []

    def first():
        with reg.reserve("billing", "Billing", "BILL", "projects/billing"):
            inside.set()
            release.wait(5)
        results.append("first")

    def second():
        try:
            with reg.reserve("billing", "Billing 2", "BIL2", "projects/billing2"):
                pass
            results.append("second")
        except RegistryError as exc:
            results.append(exc.code)

    t1 = threading.Thread(target=first)
    t1.start()
    inside.wait(5)
    t2 = threading.Thread(target=second)
    t2.start()
    t2.join(0.3)
    assert t2.is_alive(), "the second create should wait for the first"
    release.set()
    t1.join(5)
    t2.join(5)
    assert results == ["first", "slug_taken"]


def test_the_database_refuses_a_bad_slug(tmp_path):
    reg = Registry(tmp_path / "wb.db")
    with pytest.raises(RegistryError) as err:
        with reg.reserve("Bad Slug", "x", "X", "projects/x"):
            pass
    assert "CHECK constraint" in err.value.message and reg.list() == []


def test_rename_changes_only_the_name(tmp_path):
    reg = Registry(tmp_path / "wb.db")
    with reg.reserve("billing", "Billing", "BILL", "projects/billing"):
        pass
    p = reg.rename("billing", "  Billing   v2 ")
    assert (p.slug, p.name, p.store_path) == ("billing", "Billing v2", "projects/billing")
    with pytest.raises(RegistryError) as err:
        reg.rename("nope", "x")
    assert err.value.status == 404
    with pytest.raises(RegistryError):
        reg.rename("billing", "  ")


@pytest.mark.parametrize(("slug", "name", "key", "field"), [
    ("Billing", "Billing", "BILL", "slug"),
    ("-billing", "Billing", "BILL", "slug"),
    ("billing-", "Billing", "BILL", "slug"),
    ("billing", "", "BILL", "name"),
    ("billing", "Billing", "bill", "huly_project"),
    ("billing", "Billing", "BILLING", "huly_project"),
])
def test_check_new_names_the_bad_field(slug, name, key, field):
    with pytest.raises(RegistryError) as err:
        check_new(slug, name, key)
    assert err.value.field == field


def test_suggest_slug():
    assert suggest_slug("Billing v2!") == "billing-v2"
    assert suggest_slug("  Ünïcode -- stuff ") == "n-code-stuff"


def test_scaffold_makes_a_valid_committed_store(tmp_path):
    scaffold_store(tmp_path / "billing", "Billing")
    result = planlib.validate(tmp_path / "billing", show=lambda *_: pytest.fail("openspec called"))
    assert result.errors == [] and result.graph["nodes"] == []
    status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path / "billing", capture_output=True, text=True)
    assert status.stdout == ""


def test_scaffold_refuses_an_existing_directory(tmp_path):
    (tmp_path / "billing").mkdir()
    (tmp_path / "billing" / "keep.txt").write_text("mine")
    with pytest.raises(ScaffoldError):
        scaffold_store(tmp_path / "billing", "Billing")
    assert (tmp_path / "billing" / "keep.txt").read_text() == "mine"
