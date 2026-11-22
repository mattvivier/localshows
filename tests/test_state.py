import json

import pytest

from localshows import state


def test_round_trip_keeps_unicode(tmp_path):
    path = tmp_path / "new" / "shows.json"
    state.save(path, {"artist": "Blackmore’s Night"})
    assert state.load(path, {}) == {"artist": "Blackmore’s Night"}
    assert "’" in path.read_text(encoding="utf-8")


def test_key_order_does_not_change_the_file(tmp_path):
    path = tmp_path / "shows.json"
    state.save(path, {"b": 1, "a": 2})
    first = path.read_bytes()
    state.save(path, {"a": 2, "b": 1})
    assert path.read_bytes() == first


def test_missing_file_returns_default(tmp_path):
    assert state.load(tmp_path / "none.json", {"x": 1}) == {"x": 1}


def test_corrupt_file_raises(tmp_path):
    path = tmp_path / "shows.json"
    path.write_text("{broken")
    with pytest.raises(json.JSONDecodeError):
        state.load(path, {})


def test_failed_write_keeps_old_file(tmp_path, monkeypatch):
    path = tmp_path / "shows.json"
    state.save(path, {"old": True})

    def fail(*args):
        raise OSError("disk trouble")

    monkeypatch.setattr(state.os, "replace", fail)
    with pytest.raises(OSError):
        state.save(path, {"new": True})
    assert state.load(path, {}) == {"old": True}
    assert list(tmp_path.iterdir()) == [path]
