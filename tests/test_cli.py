"""Tests for the command-line interface."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquareserve.cli import main


def test_validate_ok_on_example(example_farm_path: Path, capsys):
    rc = main(["validate", str(example_farm_path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Scenario loaded" in out
    assert "24.0 ha" in out


def test_validate_reports_invalid_config(tmp_path: Path, capsys):
    bad = tmp_path / "farm.yaml"

    # missing required fields
    bad.write_text("name: broken\n", encoding="utf-8")  
    rc = main(["validate", str(bad)])
    err = capsys.readouterr().err
    
    assert rc == 1
    assert "INVALID" in err


def test_no_command_exits_nonzero():
    with pytest.raises(SystemExit):
        main([])
