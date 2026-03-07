"""Build precalculated equity tables in SQLite via Monte Carlo simulation."""

import sqlite3
import os
import random
import time
from multiprocessing import Pool, cpu_count
from treys import Card

from .hand_evaluator import evaluate_hand, RANKS, SUITS, parse_card
from .monte_carlo import ALL_CARDS

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "equity_tables.db"
)

# Hand categories
HAND_CATEGORIES = {
    "pocket_pair": "Pocket Pair",
    "suited_connectors": "Suited Connectors",
    "suited_broadway": "Suited Broadway",
    "offsuit_broadway": "Offsuit Broadway",
    "suited_gapper": "Suited Gapper",
    "offsuit_connectors": "Offsuit Connectors",
    "trash": "Trash / Other",
}

BROADWAY_RANKS = set("AKQJT")
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}

POSITIONS = ["UTG", "MP", "HJ", "CO", "BTN", "BB"]
STREETS = ["preflop", "flop", "turn", "river"]
SPR_RANGES = ["0-1", "1-3", "3-6", "6-13", "13+"]
BET_SIZES = ["0.25x", "0.5x", "0.75x", "1x", "1.5x+"]
BOARD_TEXTURES = [
    "monotone_high", "monotone_medium", "monotone_low",
    "twotone_high", "twotone_medium", "twotone_low",
    "rainbow_high", "rainbow_medium", "rainbow_low",
    "paired", "preflop",
]


def categorize_hand(card1_rank: str, card2_rank: str, suited: bool) -> str:
    """Categorize a starting hand."""
    r1 = RANK_VALUES.get(card1_rank, 0)
    r2 = RANK_VALUES.get(card2_rank, 0)
    if r1 < r2:
        r1, r2 = r2, r1
        card1_rank, card2_rank = card2_rank, card1_rank

    if card1_rank == card2_rank:
        return "pocket_pair"

    gap = r1 - r2
    both_broadway = card1_rank in BROADWAY_RANKS and card2_rank in BROADWAY_RANKS

    if suited:
        if both_broadway:
            return "suited_broadway"
        elif gap == 1:
            return "suited_connectors"
        elif gap <= 3:
            return "suited_gapper"
        else:
            return "trash"
    else:
        if both_broadway:
            return "offsuit_broadway"
        elif gap == 1:
            return "offsuit_connectors"
        else:
            return "trash"


def classify_board_texture(board: list[int]) -> str:
    """Classify board texture for indexing."""
    if not board:
        return "preflop"

    # Extract suits and ranks
    suits = [Card.get_suit_int(c) for c in board]
    ranks = [Card.get_rank_int(c) for c in board]

    # Check for paired board
    if len(set(ranks)) < len(ranks):
        return "paired"

    # Suit texture
    unique_suits = len(set(suits))
    if unique_suits == 1:
        suit_label = "monotone"
    elif unique_suits == 2:
        suit_label = "twotone"
    else:
        suit_label = "rainbow"

    # Rank height (0=2 .. 12=A)
    avg_rank = sum(ranks) / len(ranks)
    if avg_rank >= 9:  # average T+
        height = "high"
    elif avg_rank >= 5:  # average 7-9
        height = "medium"
    else:
        height = "low"

    return f"{suit_label}_{height}"


def classify_spr(stack: float, pot: float) -> str:
    """Classify stack-to-pot ratio."""
    if pot <= 0:
        return "13+"
    spr = stack / pot
    if spr <= 1:
        return "0-1"
    elif spr <= 3:
        return "1-3"
    elif spr <= 6:
        return "3-6"
    elif spr <= 13:
        return "6-13"
    else:
        return "13+"


def classify_bet_size(bet: float, pot: float) -> str:
    """Classify bet size relative to pot."""
    if pot <= 0:
        return "0.5x"
    ratio = bet / pot
    if ratio <= 0.375:
        return "0.25x"
    elif ratio <= 0.625:
        return "0.5x"
    elif ratio <= 0.875:
        return "0.75x"
    elif ratio <= 1.25:
        return "1x"
    else:
        return "1.5x+"


def _get_rank_char(card: int) -> str:
    """Get rank character from a treys card int."""
    return Card.STR_RANKS[Card.get_rank_int(card)]


def _get_suit_char(card: int) -> str:
    """Get suit character from a treys card int."""
    suit_int = Card.get_suit_int(card)
    suit_map = {1: 's', 2: 'h', 4: 'd', 8: 'c'}
    return suit_map.get(suit_int, '?')


def _is_suited(c1: int, c2: int) -> bool:
    return Card.get_suit_int(c1) == Card.get_suit_int(c2)


def init_db(db_path: str | None = None):
    """Initialize the SQLite database with the equity table schema."""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS equity (
            hand_category TEXT NOT NULL,
            board_texture TEXT NOT NULL,
            position TEXT NOT NULL,
            street TEXT NOT NULL,
            spr TEXT NOT NULL,
            bet_size TEXT NOT NULL,
            equity REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            PRIMARY KEY (hand_category, board_texture, position, street, spr, bet_size)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_lookup ON equity(hand_category, board_texture, street)")
    conn.commit()
    conn.close()


def _simulate_batch(args) -> list[tuple]:
    """Worker: simulate a batch of random hands and return aggregated results.

    Returns list of (hand_cat, board_texture, street, equity, count) tuples.
    """
    batch_size, seed = args
    random.seed(seed)
    results = {}  # (hand_cat, board_texture, street) -> (total_equity, count)

    for _ in range(batch_size):
        # Deal random cards
        deck = list(ALL_CARDS)
        random.shuffle(deck)

        hero = [deck[0], deck[1]]
        villain = [deck[2], deck[3]]
        board_full = deck[4:9]

        # Categorize hero hand
        r1 = _get_rank_char(hero[0])
        r2 = _get_rank_char(hero[1])
        suited = _is_suited(hero[0], hero[1])
        hand_cat = categorize_hand(r1, r2, suited)

        # Evaluate at each street
        for street, num_board in [("preflop", 0), ("flop", 3), ("turn", 4), ("river", 5)]:
            board = board_full[:num_board]
            board_tex = classify_board_texture(board)

            # Evaluate hands
            if num_board < 3:
                # For preflop, run a mini-sim (5 random boards)
                wins = 0
                total = 5
                remaining = [c for c in ALL_CARDS if c not in hero and c not in villain]
                for _ in range(total):
                    rb = random.sample(remaining, 5)
                    rh = evaluate_hand(hero, rb)
                    rv = evaluate_hand(villain, rb)
                    if rh < rv:
                        wins += 1
                    elif rh == rv:
                        wins += 0.5
                eq = wins / total
            else:
                # Complete the board if needed
                if num_board < 5:
                    remaining = [c for c in ALL_CARDS if c not in hero and c not in villain and c not in board]
                    extra = random.sample(remaining, 5 - num_board)
                    full_b = board + extra
                else:
                    full_b = board
                rh = evaluate_hand(hero, full_b)
                rv = evaluate_hand(villain, full_b)
                if rh < rv:
                    eq = 1.0
                elif rh == rv:
                    eq = 0.5
                else:
                    eq = 0.0

            key = (hand_cat, board_tex, street)
            if key in results:
                old_eq, old_cnt = results[key]
                results[key] = (old_eq + eq, old_cnt + 1)
            else:
                results[key] = (eq, 1)

    return [(k[0], k[1], k[2], v[0], v[1]) for k, v in results.items()]


def build_tables(
    num_simulations: int = 10_000_000,
    db_path: str | None = None,
    num_workers: int | None = None,
    progress_callback=None,
):
    """Build precalculated equity tables via Monte Carlo simulation.

    Args:
        num_simulations: Total hands to simulate.
        db_path: Path to SQLite DB.
        num_workers: Number of parallel workers.
        progress_callback: Optional callable(completed, total) for progress.
    """
    if db_path is None:
        db_path = DB_PATH
    if num_workers is None:
        num_workers = min(cpu_count(), 8)

    init_db(db_path)

    batch_size = num_simulations // num_workers
    args = [(batch_size, random.randint(0, 2**31)) for _ in range(num_workers)]

    print(f"Starting simulation: {num_simulations:,} hands across {num_workers} workers...")
    start = time.time()

    # Aggregate results across all workers
    aggregated = {}  # (hand_cat, board_tex, street) -> (total_eq, count)

    with Pool(num_workers) as pool:
        for i, result_batch in enumerate(pool.imap_unordered(_simulate_batch, args)):
            for hand_cat, board_tex, street, total_eq, count in result_batch:
                key = (hand_cat, board_tex, street)
                if key in aggregated:
                    old_eq, old_cnt = aggregated[key]
                    aggregated[key] = (old_eq + total_eq, old_cnt + count)
                else:
                    aggregated[key] = (total_eq, count)
            if progress_callback:
                progress_callback(i + 1, num_workers)
            print(f"  Worker {i+1}/{num_workers} done.")

    elapsed = time.time() - start
    print(f"Simulation complete in {elapsed:.1f}s. Writing {len(aggregated)} entries to DB...")

    # Write to SQLite - expand across all position/spr/bet_size combos
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM equity")  # Clear old data

    rows = []
    for (hand_cat, board_tex, street), (total_eq, count) in aggregated.items():
        avg_equity = total_eq / count
        for pos in POSITIONS:
            for spr in SPR_RANGES:
                for bet in BET_SIZES:
                    rows.append((hand_cat, board_tex, pos, street, spr, bet, avg_equity, count))

    c.executemany(
        "INSERT OR REPLACE INTO equity VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows
    )
    conn.commit()
    conn.close()
    print(f"Done. {len(rows)} rows written to {db_path}")
    return len(rows)


if __name__ == "__main__":
    build_tables(num_simulations=10_000_000)
