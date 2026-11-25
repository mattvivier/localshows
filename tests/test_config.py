import json
from pathlib import Path

import pytest

from localshows.cli import main
from localshows.config import load_venues

ROOT = Path(__file__).resolve().parents[1]


def test_repo_venue_list():
    assert {venue.id for venue in load_venues(ROOT)} == {
        "colony",
        "bearsville",
        "pearl-moon",
        "the-local",
    }


def test_duplicate_ids_are_rejected(tmp_path):
    row = {"id": "a", "name": "A", "town": "T", "reader": "r", "url": "https://example.com"}
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "venues.json").write_text(json.dumps([row, row]))
    with pytest.raises(ValueError, match="Duplicate"):
        load_venues(tmp_path)


def test_venues_command(capsys):
    assert main(["--root", str(ROOT), "venues"]) == 0
    assert "Pearl Moon" in capsys.readouterr().out
