from importlib.metadata import version

import assayr
from assayr.config import get_settings


def test_version_matches_package_metadata():
    assert assayr.__version__ == version("assayr")


def test_env_file_named_by_variable(tmp_path, monkeypatch):
    env_file = tmp_path / "my settings.env"
    env_file.write_text('ASSAYR_ORG_NAME="Org from file"\nASSAYR_MAX_UPLOAD_MB=7\n', encoding="utf-8")
    monkeypatch.setenv("ASSAYR_ENV_FILE", str(env_file))
    monkeypatch.delenv("ASSAYR_ORG_NAME", raising=False)
    monkeypatch.delenv("ASSAYR_MAX_UPLOAD_MB", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.org_name == "Org from file"
        assert settings.max_upload_mb == 7
    finally:
        get_settings.cache_clear()
