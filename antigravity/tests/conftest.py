from typing import Any

import pytest
from gherkin.dialect import DIALECTS

# specs/ および tests/features/ の Gherkin で使われている "Scenario N:" 構文を
# gherkin パーサーがシナリオキーワードとして認識できるように方言設定を拡張する。
for _i in range(1, 100):
    _kw = f"Scenario {_i}"
    if _kw not in DIALECTS["en"]["scenario"]:
        DIALECTS["en"]["scenario"].append(_kw)


@pytest.fixture
def bdd_context() -> dict[str, Any]:
    """Fixture providing a shared state dictionary across BDD steps."""
    return {}
