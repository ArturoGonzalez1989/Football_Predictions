"""Range model: loads ranges from ranges.json and expands hand notations to card combos."""

import json
import os
from itertools import combinations
from treys import Card

from poker_ev_system.simulator.hand_evaluator import RANKS, SUITS

_RANK_CHARS = list(RANKS)
_SUIT_CHARS = list(SUITS)

# Map rank char to index for ordering
_RANK_IDX = {r: i for i, r in enumerate(_RANK_CHARS)}


def _card_int(rank: str, suit: str) -> int:
    return Card.new(rank + suit)


def expand_hand_notation(notation: str) -> list[list[int]]:
    """Expand a hand notation like 'AKs', 'TT', 'AKo' into all card combos.

    Returns list of [card1, card2] pairs.
    """
    if len(notation) == 2:
        # Pocket pair: e.g., 'AA'
        r = notation[0].upper()
        suits_combos = list(combinations(_SUIT_CHARS, 2))
        return [[_card_int(r, s1), _card_int(r, s2)] for s1, s2 in suits_combos]
    elif len(notation) == 3:
        r1 = notation[0].upper()
        r2 = notation[1].upper()
        qualifier = notation[2].lower()
        if qualifier == 's':
            # Suited: same suit
            return [[_card_int(r1, s), _card_int(r2, s)] for s in _SUIT_CHARS]
        elif qualifier == 'o':
            # Offsuit: different suits
            combos = []
            for s1 in _SUIT_CHARS:
                for s2 in _SUIT_CHARS:
                    if s1 != s2:
                        combos.append([_card_int(r1, s1), _card_int(r2, s2)])
            return combos
        else:
            raise ValueError(f"Unknown qualifier '{qualifier}' in '{notation}'")
    else:
        raise ValueError(f"Invalid hand notation: '{notation}'")


def load_ranges(json_path: str | None = None) -> dict:
    """Load ranges from ranges.json file."""
    if json_path is None:
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "ranges.json"
        )
    with open(json_path, "r") as f:
        return json.load(f)


def get_position_range(position: str, json_path: str | None = None) -> list[list[int]]:
    """Get all card combos for a position's open range.

    Args:
        position: One of UTG, MP, HJ, CO, BTN, SB, BB.
        json_path: Optional path to ranges.json.

    Returns:
        List of [card1, card2] combos.
    """
    ranges_data = load_ranges(json_path)
    pos = position.upper()
    if pos not in ranges_data["open_ranges"]:
        raise ValueError(f"Unknown position: {pos}. Available: {list(ranges_data['open_ranges'].keys())}")

    hands = ranges_data["open_ranges"][pos]["hands"]
    all_combos = []
    for h in hands:
        all_combos.extend(expand_hand_notation(h))
    return all_combos


def get_top_percent_range(percent: float) -> list[list[int]]:
    """Get approximately the top N% of hands by standard preflop ranking.

    Uses a simplified ordering: pairs > suited broadway > offsuit broadway > suited connectors > etc.
    """
    # Standard preflop hand rankings (approximate, top to bottom)
    _ORDERED_HANDS = [
        "AA", "KK", "QQ", "AKs", "JJ", "AQs", "KQs", "AJs", "KJs", "TT",
        "AKo", "ATs", "QJs", "KTs", "QTs", "JTs", "99", "AQo", "A9s", "KQo",
        "88", "K9s", "T9s", "A8s", "Q9s", "J9s", "AJo", "A5s", "77", "A7s",
        "KJo", "A4s", "A3s", "A6s", "QJo", "66", "K8s", "T8s", "A2s", "98s",
        "J8s", "ATo", "Q8s", "K7s", "KTo", "55", "JTo", "87s", "QTo", "44",
        "33", "22", "K6s", "97s", "K5s", "76s", "T7s", "K4s", "K3s", "K2s",
        "Q7s", "86s", "65s", "J7s", "54s", "Q6s", "75s", "96s", "Q5s", "64s",
        "Q4s", "Q3s", "T6s", "Q2s", "A9o", "53s", "85s", "J6s", "J5s", "J4s",
        "J3s", "43s", "74s", "J2s", "63s", "A8o", "95s", "T5s", "52s", "T4s",
        "T3s", "T2s", "42s", "84s", "93s", "73s", "A7o", "92s", "62s", "K9o",
        "A5o", "82s", "A6o", "A4o", "32s", "A3o", "K8o", "A2o", "T9o", "Q9o",
        "J9o", "K7o", "K6o", "K5o", "K4o", "K3o", "K2o", "98o", "Q8o", "87o",
        "J8o", "76o", "Q7o", "97o", "T8o", "Q6o", "65o", "86o", "54o", "Q5o",
        "Q4o", "Q3o", "Q2o", "T7o", "96o", "75o", "J7o", "64o", "J6o", "53o",
        "85o", "J5o", "J4o", "J3o", "J2o", "43o", "74o", "T6o", "95o", "63o",
        "T5o", "52o", "T4o", "T3o", "84o", "T2o", "42o", "93o", "73o", "92o",
        "62o", "82o", "32o"
    ]

    # Total combos: 1326 (52 choose 2)
    # Each pair = 6 combos, each suited = 4, each offsuit = 12
    target = int(1326 * percent / 100)
    combos = []
    for h in _ORDERED_HANDS:
        combos.extend(expand_hand_notation(h))
        if len(combos) >= target:
            break
    return combos[:target] if len(combos) > target else combos


def get_fold_equity(json_path: str | None = None) -> float:
    """Get default fold equity from config."""
    data = load_ranges(json_path)
    return data.get("default_fold_equity_vs_bet", 0.45)


def get_cbet_frequency(json_path: str | None = None) -> float:
    """Get default c-bet frequency from config."""
    data = load_ranges(json_path)
    return data.get("default_cbet_frequency", 0.65)
