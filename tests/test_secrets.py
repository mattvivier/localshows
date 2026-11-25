import pytest

from localshows.secrets import load_env, require


def test_env_file_and_environment(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("# note\nA=one\nB = 'two'\nC=\n")
    monkeypatch.setenv("B", "from-env")
    monkeypatch.delenv("A", raising=False)
    values = load_env(tmp_path)
    assert (values["A"], values["B"], values["C"]) == ("one", "from-env", "")
    with pytest.raises(SystemExit, match="C"):
        require(values, "A", "C")
