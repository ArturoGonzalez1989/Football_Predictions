"""Tests for CLI interface."""

import pytest
from unittest.mock import patch
from io import StringIO

from poker_ev_system.cli import (
    main, _parse_hand, _parse_board, _parse_preflop_hand, _format_result,
)
from poker_ev_system.engine.ev_calculator import EVResult


class TestParseHand:
    def test_continuous(self):
        assert _parse_hand("AsKd") == ["As", "Kd"]

    def test_space_separated(self):
        assert _parse_hand("As Kd") == ["As", "Kd"]

    def test_comma_separated(self):
        assert _parse_hand("As,Kd") == ["As", "Kd"]

    def test_invalid(self):
        with pytest.raises(ValueError):
            _parse_hand("A")


class TestParseBoard:
    def test_continuous(self):
        assert _parse_board("QhJhTs") == ["Qh", "Jh", "Ts"]

    def test_space_separated(self):
        assert _parse_board("Qh Jh Ts") == ["Qh", "Jh", "Ts"]

    def test_none_values(self):
        assert _parse_board(None) is None
        assert _parse_board("") is None
        assert _parse_board("none") is None

    def test_turn(self):
        assert _parse_board("QhJhTs9c") == ["Qh", "Jh", "Ts", "9c"]

    def test_river(self):
        assert _parse_board("Qh Jh Ts 9c 2d") == ["Qh", "Jh", "Ts", "9c", "2d"]


class TestParsePreflopHand:
    def test_pocket_pair(self):
        assert _parse_preflop_hand("AA") == ["As", "Ad"]

    def test_suited(self):
        result = _parse_preflop_hand("AKs")
        assert len(result) == 2
        assert result[0][0] == "A"
        assert result[1][0] == "K"
        assert result[0][1] == result[1][1]  # same suit

    def test_offsuit(self):
        result = _parse_preflop_hand("AKo")
        assert len(result) == 2
        assert result[0][0] == "A"
        assert result[1][0] == "K"
        assert result[0][1] != result[1][1]  # different suit

    def test_specific_cards(self):
        assert _parse_preflop_hand("As Kd") == ["As", "Kd"]


class TestFormatResult:
    def test_format_has_key_info(self):
        r = EVResult(
            ev_fold=0.0, ev_call=5.0, ev_raise=8.0,
            equity=0.65, pot_odds=0.25, breakeven_equity=0.25,
            recommended_action="RAISE", recommended_ev=8.0,
        )
        text = _format_result(r, "AsKd", "QhJhTs")
        assert "65.0%" in text
        assert "RAISE" in text
        assert "+8.00" in text
        assert "AsKd" in text
        assert "QhJhTs" in text

    def test_format_preflop(self):
        r = EVResult(
            ev_fold=0.0, ev_call=1.0, ev_raise=2.0,
            equity=0.50, pot_odds=0.25, breakeven_equity=0.25,
            recommended_action="RAISE", recommended_ev=2.0,
        )
        text = _format_result(r, "AsAd", None)
        assert "Preflop" in text


class TestCLICommands:
    def test_calc_command(self, capsys):
        ret = main(["calc", "--hero", "AsAd", "--pot", "12", "--bet", "8", "--stack", "92", "--pos", "BTN"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "RAISE" in out or "CALL" in out
        assert "Equity:" in out

    def test_preflop_command(self, capsys):
        ret = main(["preflop", "--hero", "AKs", "--pos", "CO"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Equity:" in out

    def test_no_command_shows_help(self, capsys):
        ret = main([])
        assert ret == 1

    def test_calc_with_board(self, capsys):
        ret = main(["calc", "--hero", "AsKd", "--board", "QhJhTs", "--pot", "20", "--bet", "10", "--stack", "80", "--pos", "CO"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Equity:" in out

    def test_calc_no_tables(self, capsys):
        ret = main(["calc", "--hero", "AsAd", "--pot", "6", "--bet", "3", "--stack", "97", "--pos", "BTN", "--no-tables", "--sims", "1000"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Equity:" in out
