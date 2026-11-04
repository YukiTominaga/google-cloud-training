import pytest


@pytest.fixture
def bdd_context() -> dict:
    """Fixture providing a shared state dictionary across BDD steps."""
    return {}
