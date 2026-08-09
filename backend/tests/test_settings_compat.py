"""A stale setting in .env must not stop the server booting.

pydantic-settings forbids unknown fields by default, so removing a setting
would otherwise crash every deployment whose .env still mentions it. That
happened with BINDERDASH_API_KEY; this guards the fix.
"""

from pydantic_settings import SettingsConfigDict

from backend.settings import RawSettings


def test_unknown_env_keys_are_ignored(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        'BINDERDASH_API_KEY="a-removed-setting"\n'
        'SOME_TOTALLY_UNKNOWN_KEY="x"\n'
        'LOG_LEVEL="DEBUG"\n'
    )

    class Scoped(RawSettings):
        model_config = SettingsConfigDict(
            env_file=str(env), env_file_encoding="utf-8", extra="ignore"
        )

    # Must not raise, and must still read the settings it does know about.
    assert Scoped().log_level == "DEBUG"


def test_production_config_declares_extra_ignore():
    # The behaviour above comes from model_config, not from the subclass above.
    assert RawSettings.model_config.get("extra") == "ignore"
