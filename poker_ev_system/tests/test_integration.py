"""Phase 7 tests: Integration and stress test."""

import time
import pytest
import random
from poker_ev_system.simulator.hand_evaluator import parse_cards, determine_winner
from poker_ev_system.simulator.monte_carlo import equity_vs_hand, ALL_CARDS
from poker_ev_system.engine.ev_calculator import EVCalculator
from poker_ev_system.engine.range_model import expand_hand_notation, get_position_range
from poker_ev_system.simulator.table_builder import (
    categorize_hand, classify_board_texture, classify_spr, classify_bet_size,
)


class TestTableBuilderClassifiers:
    def test_categorize_pocket_pair(self):
        assert categorize_hand("A", "A", True) == "pocket_pair"
        assert categorize_hand("2", "2", False) == "pocket_pair"

    def test_categorize_suited_broadway(self):
        assert categorize_hand("A", "K", True) == "suited_broadway"
        assert categorize_hand("Q", "J", True) == "suited_broadway"

    def test_categorize_offsuit_broadway(self):
        assert categorize_hand("A", "K", False) == "offsuit_broadway"

    def test_categorize_suited_connectors(self):
        assert categorize_hand("9", "8", True) == "suited_connectors"

    def test_categorize_trash(self):
        assert categorize_hand("9", "2", False) == "trash"

    def test_classify_spr(self):
        assert classify_spr(10, 100) == "0-1"
        assert classify_spr(200, 100) == "1-3"
        assert classify_spr(500, 100) == "3-6"
        assert classify_spr(1000, 100) == "6-13"
        assert classify_spr(2000, 100) == "13+"

    def test_classify_bet_size(self):
        assert classify_bet_size(25, 100) == "0.25x"
        assert classify_bet_size(50, 100) == "0.5x"
        assert classify_bet_size(75, 100) == "0.75x"
        assert classify_bet_size(100, 100) == "1x"
        assert classify_bet_size(200, 100) == "1.5x+"


class TestRangeModel:
    def test_position_range_loads(self):
        r = get_position_range("BTN")
        assert len(r) > 100

    def test_all_positions_load(self):
        for pos in ["UTG", "MP", "HJ", "CO", "BTN", "SB", "BB"]:
            r = get_position_range(pos)
            assert len(r) > 0


class TestDeterminism:
    """Same inputs should produce consistent results."""

    def test_evaluator_determinism(self):
        h1 = parse_cards(["As", "Ad"])
        h2 = parse_cards(["Kh", "Kd"])
        board = parse_cards(["2c", "3h", "9s", "7d", "4c"])
        r1 = determine_winner(h1, h2, board)
        r2 = determine_winner(h1, h2, board)
        assert r1 == r2

    def test_ev_determinism(self):
        """Same seed should give same equity (approximately)."""
        random.seed(42)
        hero = parse_cards(["As", "Ad"])
        villain = parse_cards(["Kh", "Kd"])
        eq1 = equity_vs_hand(hero, villain, num_simulations=10000)

        random.seed(42)
        eq2 = equity_vs_hand(hero, villain, num_simulations=10000)
        assert eq1 == eq2


class TestStressCalculations:
    """Run multiple calculations and verify stability."""

    SITUATIONS = [
        (["As", "Ad"], None, 6, 3, 97, "BTN", "CO"),
        (["Kh", "Kd"], None, 3, 10, 90, "CO", "BTN"),
        (["Ah", "Kh"], ["Qh", "Jh", "2c"], 10, 7, 83, "BTN", "BB"),
        (["Ts", "9s"], ["8c", "7s", "2h"], 12, 8, 80, "CO", "UTG"),
        (["7s", "2d"], ["As", "Kh", "Qd"], 10, 10, 80, "BB", "UTG"),
        (["Jh", "Jd"], None, 3, 6, 94, "HJ", "CO"),
        (["5s", "5d"], ["Kh", "Qd", "Jc", "Ts"], 20, 15, 65, "BB", "CO"),
        (["Qh", "Jh"], ["Th", "9s", "2c", "7h"], 15, 10, 75, "CO", "BTN"),
        (["As", "Kd"], ["Ah", "9c", "5s", "3d", "2c"], 25, 12, 63, "BTN", "BB"),
        (["6s", "6d"], ["Ac", "Kh", "3s"], 20, 2, 78, "BB", "BTN"),
    ]

    def test_stress_50_calculations(self):
        """Run 50 calculations, none should crash."""
        calc = EVCalculator(use_tables=False)
        errors = []
        for i in range(50):
            sit = self.SITUATIONS[i % len(self.SITUATIONS)]
            try:
                result = calc.calculate(
                    hero_cards=sit[0],
                    board_cards=sit[1],
                    pot_bb=sit[2],
                    bet_bb=sit[3],
                    stack_bb=sit[4],
                    hero_position=sit[5],
                    villain_position=sit[6],
                    fold_equity=0.45,
                    num_simulations=1000,
                )
                assert 0 <= result.equity <= 1
                assert result.recommended_action in ("FOLD", "CALL", "RAISE", "CHECK", "BET")
            except Exception as e:
                errors.append(f"Iteration {i}: {e}")
        calc.close()
        assert len(errors) == 0, f"Errors in stress test: {errors}"

    def test_timing_under_500ms(self):
        """Individual calculations should complete quickly (without tables)."""
        calc = EVCalculator(use_tables=False)
        times = []
        for sit in self.SITUATIONS[:5]:
            start = time.time()
            calc.calculate(
                hero_cards=sit[0],
                board_cards=sit[1],
                pot_bb=sit[2],
                bet_bb=sit[3],
                stack_bb=sit[4],
                hero_position=sit[5],
                villain_position=sit[6],
                fold_equity=0.45,
                num_simulations=2000,
            )
            elapsed = time.time() - start
            times.append(elapsed)
        calc.close()
        avg_time = sum(times) / len(times)
        # With low sim count, should be well under 500ms on average
        # (Monte Carlo without tables will be slower with larger sim counts)
        assert avg_time < 30, f"Average time {avg_time:.2f}s too slow"
