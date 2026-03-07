"""Phase 2 & 3 tests: Monte Carlo simulator (hand vs hand and hand vs range)."""

import pytest
from poker_ev_system.simulator.hand_evaluator import parse_cards
from poker_ev_system.simulator.monte_carlo import equity_vs_hand, equity_vs_range
from poker_ev_system.engine.range_model import expand_hand_notation, get_top_percent_range


class TestEquityVsHand:
    """Phase 2: Basic heads-up equity calculations."""

    def test_aa_vs_kk_preflop(self):
        """AA vs KK should be ~81-83% equity."""
        hero = parse_cards(["As", "Ad"])
        villain = parse_cards(["Kh", "Kd"])
        eq = equity_vs_hand(hero, villain, num_simulations=50000)
        assert 0.79 <= eq <= 0.85, f"AA vs KK equity {eq:.4f} out of range"

    def test_aks_vs_72o_preflop(self):
        """AKs vs 72o should be ~66-68%."""
        hero = parse_cards(["Ah", "Kh"])
        villain = parse_cards(["7s", "2d"])
        eq = equity_vs_hand(hero, villain, num_simulations=50000)
        assert 0.64 <= eq <= 0.70, f"AKs vs 72o equity {eq:.4f} out of range"

    def test_coinflip_ak_vs_qq(self):
        """AKo vs QQ should be ~43-46% (classic coinflip)."""
        hero = parse_cards(["As", "Kd"])
        villain = parse_cards(["Qh", "Qc"])
        eq = equity_vs_hand(hero, villain, num_simulations=50000)
        assert 0.41 <= eq <= 0.48, f"AK vs QQ equity {eq:.4f} out of range"

    def test_set_vs_overpair_on_flop(self):
        """Set of 7s vs AA on 7-high flop should be ~90%+."""
        hero = parse_cards(["7s", "7d"])
        villain = parse_cards(["As", "Ad"])
        board = parse_cards(["7h", "5c", "2s"])
        eq = equity_vs_hand(hero, villain, board, num_simulations=30000)
        assert eq >= 0.87, f"Set vs overpair equity {eq:.4f} too low"

    def test_flush_draw_vs_pair_flop(self):
        """Flush draw vs top pair should be ~35-45%."""
        hero = parse_cards(["Ah", "Th"])  # nut flush draw
        villain = parse_cards(["Ks", "Qd"])  # top pair K
        board = parse_cards(["Kh", "7h", "3c"])
        eq = equity_vs_hand(hero, villain, board, num_simulations=30000)
        assert 0.30 <= eq <= 0.50, f"Flush draw vs pair equity {eq:.4f} out of range"

    def test_dominated_hand(self):
        """AK vs AQ (dominated) should be ~72-76%."""
        hero = parse_cards(["As", "Kd"])
        villain = parse_cards(["Ah", "Qd"])
        eq = equity_vs_hand(hero, villain, num_simulations=50000)
        assert 0.70 <= eq <= 0.78, f"AK vs AQ equity {eq:.4f} out of range"

    def test_symmetry(self):
        """equity(A,B) + equity(B,A) should be ~1.0."""
        hero = parse_cards(["Jh", "Td"])
        villain = parse_cards(["9s", "9c"])
        eq1 = equity_vs_hand(hero, villain, num_simulations=30000)
        eq2 = equity_vs_hand(villain, hero, num_simulations=30000)
        assert abs(eq1 + eq2 - 1.0) < 0.03, f"Symmetry broken: {eq1} + {eq2} != 1.0"


class TestEquityVsRange:
    """Phase 3: Equity vs range of hands."""

    def test_aa_vs_top20(self):
        """AA vs top 20% should be ~82-86% (AA dominates most hands in range)."""
        hero = parse_cards(["As", "Ad"])
        villain_range = get_top_percent_range(20)
        eq = equity_vs_range(hero, villain_range, num_simulations_per_hand=200)
        assert 0.80 <= eq <= 0.88, f"AA vs top 20% equity {eq:.4f} out of range"

    def test_72o_vs_top20(self):
        """72o vs top 20% should be very low (~25-35%)."""
        hero = parse_cards(["7s", "2d"])
        villain_range = get_top_percent_range(20)
        eq = equity_vs_range(hero, villain_range, num_simulations_per_hand=200)
        assert 0.20 <= eq <= 0.40, f"72o vs top 20% equity {eq:.4f} out of range"


class TestRangeExpansion:
    def test_pocket_pair(self):
        combos = expand_hand_notation("AA")
        assert len(combos) == 6  # C(4,2) = 6

    def test_suited(self):
        combos = expand_hand_notation("AKs")
        assert len(combos) == 4  # 4 suits

    def test_offsuit(self):
        combos = expand_hand_notation("AKo")
        assert len(combos) == 12  # 4*3 = 12

    def test_top_percent(self):
        combos = get_top_percent_range(10)
        assert len(combos) > 100
        assert len(combos) < 200  # ~133 combos = 10% of 1326
