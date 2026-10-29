"""Tests for the dev-only analytics data. These do not touch the database."""
import pytest

from app.services import agent_dev_stores as dev


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(dev.FLAG_NAME, raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(dev, "_warned", False)


def test_store_is_off_by_default():
    assert dev.build_dev_analytics_store(None) is None


def test_only_the_exact_value_one_enables_it(monkeypatch):
    monkeypatch.setenv(dev.FLAG_NAME, "true")
    assert dev.build_dev_analytics_store(None) is None


def test_enabled_store_holds_three_demo_cos_and_synthetic_students(monkeypatch):
    monkeypatch.setenv(dev.FLAG_NAME, "1")
    store = dev.build_dev_analytics_store(None)
    assert store is not None
    assert [c.number for c in store.cos] == [1, 2, 3]
    assert len(store.roster) == 3
    assert all(s.usn.startswith("DEV") for s in store.roster)


def test_refuses_to_enable_in_production(monkeypatch):
    monkeypatch.setenv(dev.FLAG_NAME, "1")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(dev.DevStoreConfigurationError):
        dev.validate_dev_store_config()
    with pytest.raises(dev.DevStoreConfigurationError):
        dev.build_dev_analytics_store(None)
