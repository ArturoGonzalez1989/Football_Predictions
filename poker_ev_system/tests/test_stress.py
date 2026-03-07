"""Phase 7 stress test: 500 consecutive situations, determinism, and timing."""

import time
import random
import pytest
from poker_ev_system.engine.ev_calculator import EVCalculator

RANKS = "A K Q J T 9 8 7 6 5 4 3 2".split()
SUITS = list("shdc")
POSITIONS = ["UTG", "MP", "HJ", "CO", "BTN", "SB", "BB"]


def random_card(exclude: set) -> str:
    """Generate a random card not in exclude set."""
    while True:
        card = random.choice(RANKS) + random.choice(SUITS)
        if card not in exclude:
            exclude.add(card)
            return card


def random_situation(rng: random.Random):
    """Generate a random poker situation."""
    used = set()
    c1 = random_card(used)
    c2 = random_card(used)

    # Random street: 0=preflop, 3=flop, 4=turn, 5=river
    num_board = rng.choice([0, 0, 3, 3, 4, 5])  # weight preflop/flop more
    board = [random_card(used) for _ in range(num_board)]

    pot = round(rng.uniform(2, 50), 1)
    bet = round(rng.uniform(0, pot * 2), 1)
    stack = round(rng.uniform(10, 200), 1)
    h_pos = rng.choice(POSITIONS)
    v_pos = rng.choice(POSITIONS)

    return {
        "hero_cards": [c1, c2],
        "board_cards": board if board else None,
        "pot_bb": pot,
        "bet_bb": bet,
        "stack_bb": stack,
        "hero_position": h_pos,
        "villain_position": v_pos,
        "fold_equity": 0.45,
        "num_simulations": 500,
    }


class TestStress500:
    """Run 500 consecutive random situations and verify stability."""

    def test_500_situations_no_crashes(self):
        """500 random situations must all complete without error."""
        calc = EVCalculator(use_tables=True)
        rng = random.Random(12345)
        errors = []
        times = []

        for i in range(500):
            sit = random_situation(rng)
            try:
                start = time.time()
                result = calc.calculate(**sit)
                elapsed = time.time() - start
                times.append(elapsed)

                # Basic sanity checks
                assert 0 <= result.equity <= 1, f"Iter {i}: equity {result.equity} out of range"
                assert result.ev_fold == 0.0, f"Iter {i}: ev_fold not 0"
                assert result.recommended_action in ("FOLD", "CALL", "RAISE", "CHECK", "BET")
            except Exception as e:
                errors.append(f"Iter {i}: {e}")

        calc.close()

        # Report
        if times:
            avg_ms = sum(times) / len(times) * 1000
            max_ms = max(times) * 1000
            p95_ms = sorted(times)[int(len(times) * 0.95)] * 1000
            print(f"\n=== STRESS TEST RESULTS ===")
            print(f"Completed: {500 - len(errors)}/500")
            print(f"Avg time: {avg_ms:.1f}ms")
            print(f"Max time: {max_ms:.1f}ms")
            print(f"P95 time: {p95_ms:.1f}ms")

        assert len(errors) == 0, f"{len(errors)} errors:\n" + "\n".join(errors[:10])

    def test_determinism_with_tables(self):
        """Same situation should always return the same result with tables."""
        calc = EVCalculator(use_tables=True)

        sit = {
            "hero_cards": ["As", "Kd"],
            "board_cards": ["Qh", "Jh", "2c"],
            "pot_bb": 10,
            "bet_bb": 7,
            "stack_bb": 83,
            "hero_position": "BTN",
            "villain_position": "BB",
            "fold_equity": 0.45,
            "num_simulations": 1000,
        }

        r1 = calc.calculate(**sit)
        r2 = calc.calculate(**sit)
        calc.close()

        # With tables, equity lookup is deterministic
        assert r1.equity == r2.equity
        assert r1.ev_call == r2.ev_call
        assert r1.ev_raise == r2.ev_raise
        assert r1.recommended_action == r2.recommended_action

    def test_all_positions_work(self):
        """Every position should produce valid results."""
        calc = EVCalculator(use_tables=True)
        for pos in POSITIONS:
            result = calc.calculate(
                hero_cards=["Ah", "Kd"],
                board_cards=None,
                pot_bb=6,
                bet_bb=3,
                stack_bb=97,
                hero_position=pos,
                villain_position="CO",
                fold_equity=0.45,
                num_simulations=500,
            )
            assert 0 <= result.equity <= 1, f"Position {pos} failed"
        calc.close()

    def test_all_streets_work(self):
        """Every street should produce valid results."""
        calc = EVCalculator(use_tables=True)
        boards = {
            "preflop": None,
            "flop": ["Qh", "Jh", "2c"],
            "turn": ["Qh", "Jh", "2c", "7d"],
            "river": ["Qh", "Jh", "2c", "7d", "3s"],
        }
        for street, board in boards.items():
            result = calc.calculate(
                hero_cards=["As", "Kd"],
                board_cards=board,
                pot_bb=10,
                bet_bb=5,
                stack_bb=85,
                hero_position="BTN",
                villain_position="CO",
                fold_equity=0.45,
                num_simulations=500,
            )
            assert 0 <= result.equity <= 1, f"Street {street} failed"
        calc.close()

    def test_end_to_end_under_500ms(self):
        """With precalculated tables, responses should be well under 500ms."""
        calc = EVCalculator(use_tables=True)
        times = []
        for _ in range(100):
            start = time.time()
            calc.calculate(
                hero_cards=["Jh", "Td"],
                board_cards=["9c", "8s", "2h"],
                pot_bb=12,
                bet_bb=8,
                stack_bb=80,
                hero_position="CO",
                villain_position="BTN",
                fold_equity=0.45,
                num_simulations=500,
            )
            times.append(time.time() - start)
        calc.close()

        avg_ms = sum(times) / len(times) * 1000
        max_ms = max(times) * 1000
        assert max_ms < 500, f"Max response {max_ms:.1f}ms exceeds 500ms"
        print(f"\nTable lookup: avg={avg_ms:.2f}ms, max={max_ms:.2f}ms")
