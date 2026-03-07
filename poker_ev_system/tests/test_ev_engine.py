"""Phase 5 tests: EV engine calculations."""

import pytest
from poker_ev_system.engine.ev_calculator import EVCalculator


@pytest.fixture
def calc():
    """Calculator without precalculated tables (Monte Carlo only)."""
    c = EVCalculator(use_tables=False)
    yield c
    c.close()


class TestEVCalculations:
    """Test EV calculations with known situations."""

    def test_easy_call_high_equity(self, calc):
        """50% equity, pot odds 33% -> clearly profitable call."""
        result = calc.calculate(
            hero_cards=["As", "Ad"],
            board_cards=["2c", "3h", "9s"],
            pot_bb=10,
            bet_bb=5,
            stack_bb=95,
            hero_position="BTN",
            villain_position="CO",
            fold_equity=0.45,
            num_simulations=5000,
        )
        assert result.ev_call > 0, f"EV call should be positive: {result.ev_call}"
        assert result.equity > 0.5, f"AA equity should be > 50%: {result.equity}"

    def test_clear_fold_low_equity(self, calc):
        """Trash hand vs tight range, big bet -> should fold."""
        result = calc.calculate(
            hero_cards=["7s", "2d"],
            board_cards=["As", "Kh", "Qd"],
            pot_bb=10,
            bet_bb=10,
            stack_bb=80,
            hero_position="BB",
            villain_position="UTG",
            fold_equity=0.1,
            num_simulations=5000,
        )
        assert result.ev_call < 0, f"72o vs UTG on AKQ should be negative EV call: {result.ev_call}"

    def test_check_situation(self, calc):
        """When bet=0, we should get CHECK vs BET recommendation."""
        result = calc.calculate(
            hero_cards=["As", "Kd"],
            board_cards=["Ah", "9c", "5s"],
            pot_bb=8,
            bet_bb=0,
            stack_bb=92,
            hero_position="BTN",
            villain_position="BB",
            fold_equity=0.5,
            num_simulations=5000,
        )
        assert result.recommended_action in ("CHECK", "BET")
        assert result.ev_fold == 0

    def test_pot_odds_calculation(self, calc):
        """Verify pot odds math."""
        result = calc.calculate(
            hero_cards=["Ks", "Qd"],
            board_cards=None,
            pot_bb=6,
            bet_bb=3,
            stack_bb=97,
            hero_position="CO",
            villain_position="BTN",
            fold_equity=0.45,
            num_simulations=3000,
        )
        # pot_odds = 3 / (6 + 3 + 3) = 0.25
        # breakeven = 3 / (6 + 6) = 0.25
        assert abs(result.breakeven_equity - 0.25) < 0.01

    def test_ev_fold_always_zero(self, calc):
        """EV fold is always 0 (reference)."""
        result = calc.calculate(
            hero_cards=["Ts", "9s"],
            board_cards=["Jh", "8d", "2c"],
            pot_bb=12,
            bet_bb=8,
            stack_bb=80,
            hero_position="CO",
            villain_position="BTN",
            fold_equity=0.45,
            num_simulations=3000,
        )
        assert result.ev_fold == 0.0

    def test_all_in_high_equity(self, calc):
        """Strong hand, short stack -> raise/call should be +EV."""
        result = calc.calculate(
            hero_cards=["As", "Ah"],
            board_cards=None,
            pot_bb=3,
            bet_bb=10,
            stack_bb=15,
            hero_position="BB",
            villain_position="BTN",
            fold_equity=0.3,
            num_simulations=5000,
        )
        assert result.ev_call > 0

    def test_preflop_no_board(self, calc):
        """Preflop calculation should work with empty board."""
        result = calc.calculate(
            hero_cards=["Jh", "Jd"],
            board_cards=[],
            pot_bb=3,
            bet_bb=6,
            stack_bb=94,
            hero_position="CO",
            villain_position="UTG",
            fold_equity=0.4,
            num_simulations=3000,
        )
        assert 0 < result.equity < 1
        assert result.recommended_action in ("FOLD", "CALL", "RAISE")

    def test_equity_range(self, calc):
        """Equity should always be between 0 and 1."""
        result = calc.calculate(
            hero_cards=["5s", "5d"],
            board_cards=["Kh", "Qd", "Jc", "Ts"],
            pot_bb=20,
            bet_bb=15,
            stack_bb=65,
            hero_position="BB",
            villain_position="CO",
            fold_equity=0.3,
            num_simulations=3000,
        )
        assert 0 <= result.equity <= 1

    def test_result_has_all_fields(self, calc):
        """Verify EVResult contains all required fields."""
        result = calc.calculate(
            hero_cards=["Ah", "Kh"],
            board_cards=["Qh", "Jh", "2c"],
            pot_bb=10,
            bet_bb=7,
            stack_bb=83,
            hero_position="BTN",
            villain_position="BB",
            fold_equity=0.45,
            num_simulations=3000,
        )
        assert hasattr(result, 'ev_fold')
        assert hasattr(result, 'ev_call')
        assert hasattr(result, 'ev_raise')
        assert hasattr(result, 'equity')
        assert hasattr(result, 'pot_odds')
        assert hasattr(result, 'breakeven_equity')
        assert hasattr(result, 'recommended_action')
        assert hasattr(result, 'recommended_ev')

    def test_raise_ev_with_fold_equity(self, calc):
        """High fold equity should make raise more attractive."""
        r_low = calc.calculate(
            hero_cards=["Td", "9d"],
            board_cards=["8c", "7s", "2h"],
            pot_bb=10, bet_bb=5, stack_bb=85,
            hero_position="CO", villain_position="BB",
            fold_equity=0.2, num_simulations=3000,
        )
        r_high = calc.calculate(
            hero_cards=["Td", "9d"],
            board_cards=["8c", "7s", "2h"],
            pot_bb=10, bet_bb=5, stack_bb=85,
            hero_position="CO", villain_position="BB",
            fold_equity=0.7, num_simulations=3000,
        )
        assert r_high.ev_raise > r_low.ev_raise

    def test_river_situation(self, calc):
        """River calculation with 5 board cards."""
        result = calc.calculate(
            hero_cards=["As", "Kd"],
            board_cards=["Ah", "9c", "5s", "3d", "2c"],
            pot_bb=25,
            bet_bb=12,
            stack_bb=63,
            hero_position="BTN",
            villain_position="BB",
            fold_equity=0.4,
            num_simulations=3000,
        )
        assert result.equity > 0

    def test_turn_situation(self, calc):
        """Turn calculation with 4 board cards."""
        result = calc.calculate(
            hero_cards=["Qh", "Jh"],
            board_cards=["Th", "9s", "2c", "7h"],
            pot_bb=15,
            bet_bb=10,
            stack_bb=75,
            hero_position="CO",
            villain_position="BTN",
            fold_equity=0.45,
            num_simulations=3000,
        )
        assert 0 < result.equity < 1

    def test_minimum_bet_situation(self, calc):
        """Very small bet relative to pot."""
        result = calc.calculate(
            hero_cards=["6s", "6d"],
            board_cards=["Ac", "Kh", "3s"],
            pot_bb=20,
            bet_bb=2,
            stack_bb=78,
            hero_position="BB",
            villain_position="BTN",
            fold_equity=0.45,
            num_simulations=3000,
        )
        # Small bet = good pot odds, could be +EV call even with low equity
        assert result.breakeven_equity < 0.15

    def test_overbet_situation(self, calc):
        """Large overbet relative to pot."""
        result = calc.calculate(
            hero_cards=["Jd", "Td"],
            board_cards=["9c", "8s", "2h"],
            pot_bb=10,
            bet_bb=20,
            stack_bb=70,
            hero_position="CO",
            villain_position="BTN",
            fold_equity=0.3,
            num_simulations=3000,
        )
        # Overbet means need more equity to call
        assert result.breakeven_equity > 0.3
