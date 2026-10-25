import pytest


@pytest.mark.skip(reason="deliberate skip: CI must fail on any skipped test")
def test_ci_validate_skip():
    pass
