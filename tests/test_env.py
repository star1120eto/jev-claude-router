import os

from router.env import load_env

NAME = "ROUTER_TEST_DOTENV_VALUE"


def _isolate(monkeypatch):
    # テスト後に環境変数が残らないよう、いったん setenv して元の状態(未設定)を記録させる
    monkeypatch.setenv(NAME, "placeholder")
    monkeypatch.delenv(NAME)


def test_loads_values_from_dotenv_in_cwd(tmp_path, monkeypatch):
    _isolate(monkeypatch)
    (tmp_path / ".env").write_text(f"{NAME}=from-dotenv\n")
    monkeypatch.chdir(tmp_path)

    assert load_env() is True
    assert os.environ[NAME] == "from-dotenv"


def test_does_not_override_existing_environment(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(f"{NAME}=from-dotenv\n")
    monkeypatch.setenv(NAME, "from-shell")

    load_env(tmp_path / ".env")

    assert os.environ[NAME] == "from-shell"


def test_returns_false_when_dotenv_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert load_env(tmp_path / "missing.env") is False
