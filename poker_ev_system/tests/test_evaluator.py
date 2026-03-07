"""Phase 1 tests: Hand evaluator using treys."""

import pytest
from poker_ev_system.simulator.hand_evaluator import (
    parse_card, parse_cards, evaluate_hand, determine_winner,
    hand_rank_class, hand_class_string,
)


class TestParseCard:
    def test_basic_cards(self):
        assert parse_card("As") is not None
        assert parse_card("Kh") is not None
        assert parse_card("2c") is not None
        assert parse_card("Td") is not None

    def test_case_insensitive_rank(self):
        assert parse_card("as") == parse_card("As")

    def test_invalid_rank(self):
        with pytest.raises(ValueError):
            parse_card("Xs")

    def test_invalid_suit(self):
        with pytest.raises(ValueError):
            parse_card("Ax")

    def test_invalid_length(self):
        with pytest.raises(ValueError):
            parse_card("A")


class TestDetermineWinner:
    """Verify at least 20 hand matchups with known outcomes."""

    def test_aa_vs_kk(self):
        """As Ad beats Kh Kd on board 2c 3h 9s (no straight/flush possible)."""
        h1 = parse_cards(["As", "Ad"])
        h2 = parse_cards(["Kh", "Kd"])
        board = parse_cards(["2c", "3h", "9s", "7d", "4c"])
        assert determine_winner(h1, h2, board) == 1

    def test_flush_vs_straight(self):
        h1 = parse_cards(["Ah", "Kh"])  # flush
        h2 = parse_cards(["Ts", "9s"])  # straight
        board = parse_cards(["Qh", "Jh", "8h", "2c", "3d"])
        assert determine_winner(h1, h2, board) == 1

    def test_straight_vs_two_pair(self):
        h1 = parse_cards(["Ts", "9d"])  # straight
        h2 = parse_cards(["Qc", "8c"])  # pair of Q
        board = parse_cards(["Qh", "Jh", "8h", "2c", "3d"])
        assert determine_winner(h1, h2, board) == 1

    def test_full_house_vs_flush(self):
        h1 = parse_cards(["Qs", "Qd"])  # full house Q Q Q 8 8
        h2 = parse_cards(["Ah", "2h"])  # flush
        board = parse_cards(["Qh", "8h", "8s", "5h", "3c"])
        assert determine_winner(h1, h2, board) == 1

    def test_quads_vs_full_house(self):
        h1 = parse_cards(["9s", "9d"])  # quads
        h2 = parse_cards(["Ks", "Kd"])  # full house
        board = parse_cards(["9h", "9c", "Kh", "2c", "3d"])
        assert determine_winner(h1, h2, board) == 1

    def test_straight_flush_vs_quads(self):
        h1 = parse_cards(["8h", "7h"])  # straight flush
        h2 = parse_cards(["As", "Ad"])  # trips
        board = parse_cards(["6h", "5h", "4h", "Ac", "2d"])
        assert determine_winner(h1, h2, board) == 1

    def test_pair_vs_high_card(self):
        h1 = parse_cards(["2s", "2d"])
        h2 = parse_cards(["Ah", "Kd"])
        board = parse_cards(["9c", "7h", "5s", "3d", "4c"])
        assert determine_winner(h1, h2, board) == 1

    def test_higher_pair_wins(self):
        h1 = parse_cards(["Ks", "Kd"])
        h2 = parse_cards(["Qs", "Qd"])
        board = parse_cards(["2c", "3h", "9s", "7d", "4c"])
        assert determine_winner(h1, h2, board) == 1

    def test_two_pair_vs_one_pair(self):
        h1 = parse_cards(["As", "9d"])  # two pair AA 99
        h2 = parse_cards(["Kh", "Qd"])  # pair of K
        board = parse_cards(["Ah", "9h", "Ks", "2c", "3d"])
        assert determine_winner(h1, h2, board) == 1

    def test_trips_vs_two_pair(self):
        h1 = parse_cards(["9s", "9d"])  # trips
        h2 = parse_cards(["Ah", "Kd"])  # two pair
        board = parse_cards(["9h", "Ac", "Ks", "2c", "3d"])
        assert determine_winner(h1, h2, board) == 1

    def test_tie_same_hand(self):
        h1 = parse_cards(["As", "2d"])
        h2 = parse_cards(["Ah", "2c"])
        board = parse_cards(["Kh", "Ks", "Qh", "Jd", "Td"])
        # Both play the board straight AKQJT
        assert determine_winner(h1, h2, board) == 0

    def test_higher_kicker(self):
        h1 = parse_cards(["As", "Kd"])
        h2 = parse_cards(["Ah", "Qd"])
        board = parse_cards(["Ac", "9h", "5s", "3d", "2c"])
        assert determine_winner(h1, h2, board) == 1

    def test_low_straight_vs_high_card(self):
        h1 = parse_cards(["5s", "4d"])
        h2 = parse_cards(["Ah", "Kd"])
        board = parse_cards(["3c", "2h", "6s", "9d", "Tc"])
        # h1 has straight 2-6
        assert determine_winner(h1, h2, board) == 1

    def test_nut_flush_vs_second_nut(self):
        h1 = parse_cards(["Ah", "2h"])
        h2 = parse_cards(["Kh", "3h"])
        board = parse_cards(["Qh", "Jh", "9s", "4c", "5d"])
        assert determine_winner(h1, h2, board) == 1

    def test_board_plays(self):
        """Both players play the board."""
        h1 = parse_cards(["2s", "3d"])
        h2 = parse_cards(["2h", "3c"])
        board = parse_cards(["As", "Ks", "Qs", "Js", "Ts"])
        assert determine_winner(h1, h2, board) == 0

    def test_set_vs_overpair(self):
        h1 = parse_cards(["7s", "7d"])  # set of 7s
        h2 = parse_cards(["Ah", "Ad"])  # overpair AA
        board = parse_cards(["7h", "5c", "2s", "9d", "Tc"])
        assert determine_winner(h1, h2, board) == 1

    def test_higher_straight(self):
        h1 = parse_cards(["Ks", "Qd"])  # K-high straight
        h2 = parse_cards(["9h", "8d"])  # 9-high straight
        board = parse_cards(["Jc", "Th", "9s", "5d", "2c"])
        assert determine_winner(h1, h2, board) == 1

    def test_full_house_higher(self):
        """KKK55 beats JJJ55."""
        h1 = parse_cards(["Ks", "Kd"])  # KKK55 full house
        h2 = parse_cards(["Js", "Jd"])  # JJJ55 full house
        board = parse_cards(["Kh", "Jc", "5s", "5d", "2c"])
        assert determine_winner(h1, h2, board) == 1

    def test_wheel_straight(self):
        """A-5 straight (wheel)."""
        h1 = parse_cards(["As", "5d"])  # wheel
        h2 = parse_cards(["Kh", "Qd"])  # K high
        board = parse_cards(["2c", "3h", "4s", "9d", "Tc"])
        assert determine_winner(h1, h2, board) == 1

    def test_three_of_a_kind_kicker(self):
        h1 = parse_cards(["As", "9d"])  # trip 9s, A kicker
        h2 = parse_cards(["Kh", "9h"])  # trip 9s, K kicker
        board = parse_cards(["9s", "9c", "2s", "3d", "5c"])
        assert determine_winner(h1, h2, board) == 1


class TestHandClassification:
    def test_classify_pair(self):
        cards = parse_cards(["As", "Ad"])
        board = parse_cards(["2c", "3h", "9s", "7d", "4c"])
        rank = evaluate_hand(cards, board)
        cls = hand_rank_class(rank)
        assert hand_class_string(cls) == "Pair"

    def test_classify_straight(self):
        cards = parse_cards(["Ts", "9d"])
        board = parse_cards(["8c", "7h", "6s", "2d", "3c"])
        rank = evaluate_hand(cards, board)
        cls = hand_rank_class(rank)
        assert hand_class_string(cls) == "Straight"
