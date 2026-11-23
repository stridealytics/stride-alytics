from types import SimpleNamespace

from app import config as config_module


def test_get_setting_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://env.supabase.co")
    monkeypatch.setattr(
        config_module, "st", SimpleNamespace(secrets={"SUPABASE_URL": "https://secret.supabase.co"})
    )

    assert config_module._get_setting("SUPABASE_URL") == "https://env.supabase.co"


def test_get_setting_reads_streamlit_secrets(monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.setattr(
        config_module, "st", SimpleNamespace(secrets={"SUPABASE_URL": "https://secret.supabase.co"})
    )

    assert config_module._get_setting("SUPABASE_URL") == "https://secret.supabase.co"


def test_get_setting_uses_streamlit_secrets_when_environment_is_blank(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setattr(
        config_module, "st", SimpleNamespace(secrets={"SUPABASE_URL": "https://secret.supabase.co"})
    )

    assert config_module._get_setting("SUPABASE_URL") == "https://secret.supabase.co"
