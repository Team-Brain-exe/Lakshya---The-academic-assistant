"""The dev calendar store: off by default, shared while on, refused in production."""
import pytest

from app.services import agent_dev_stores as dev


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.delenv(dev.FLAG_NAME, raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(dev, "_dev_calendar_store", None)


def test_calendar_store_is_off_by_default():
    assert dev.build_dev_calendar_store(None) is None


def test_one_shared_store_is_returned_while_enabled(monkeypatch):
    monkeypatch.setenv(dev.FLAG_NAME, "1")
    first = dev.build_dev_calendar_store(None)
    second = dev.build_dev_calendar_store(None)
    assert first is not None and first is second


def test_calendar_store_refuses_production(monkeypatch):
    monkeypatch.setenv(dev.FLAG_NAME, "1")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(dev.DevStoreConfigurationError):
        dev.build_dev_calendar_store(None)
