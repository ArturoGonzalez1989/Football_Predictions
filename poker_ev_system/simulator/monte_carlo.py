"""Monte Carlo equity simulator for NLHE."""

import random
from multiprocessing import Pool, cpu_count
from treys import Deck

from .hand_evaluator import evaluate_hand, parse_card, RANKS, SUITS


def _make_all_cards() -> list[int]:
    """Generate all 52 cards as treys ints."""
    from treys import Card
    cards = []
    for r in RANKS:
        for s in SUITS:
            cards.append(Card.new(r + s))
    return cards


ALL_CARDS = _make_all_cards()


def equity_vs_hand(
    hero: list[int],
    villain: list[int],
    board: list[int] | None = None,
    num_simulations: int = 50000,
) -> float:
    """Calculate equity of hero vs a specific villain hand via Monte Carlo.

    Args:
        hero: 2 treys card ints.
        villain: 2 treys card ints.
        board: 0-5 community cards (treys ints). None or [] for preflop.
        num_simulations: Number of random runouts to simulate.

    Returns:
        Hero equity as float between 0.0 and 1.0.
    """
    if board is None:
        board = []
    dead = set(hero + villain + board)
    remaining = [c for c in ALL_CARDS if c not in dead]
    cards_needed = 5 - len(board)

    wins = 0
    ties = 0
    for _ in range(num_simulations):
        runout = random.sample(remaining, cards_needed)
        full_board = board + runout
        rank_h = evaluate_hand(hero, full_board)
        rank_v = evaluate_hand(villain, full_board)
        if rank_h < rank_v:
            wins += 1
        elif rank_h == rank_v:
            ties += 1

    return (wins + ties / 2) / num_simulations


def _worker_equity_vs_hand(args):
    """Worker function for parallel equity calculation."""
    hero, villain, board, num_sims = args
    return equity_vs_hand(hero, villain, board, num_sims)


def equity_vs_hand_parallel(
    hero: list[int],
    villain: list[int],
    board: list[int] | None = None,
    num_simulations: int = 100000,
    num_workers: int | None = None,
) -> float:
    """Parallel version of equity_vs_hand."""
    if num_workers is None:
        num_workers = min(cpu_count(), 8)
    sims_per_worker = num_simulations // num_workers
    args = [(hero, villain, board, sims_per_worker) for _ in range(num_workers)]
    with Pool(num_workers) as pool:
        results = pool.map(_worker_equity_vs_hand, args)
    return sum(results) / len(results)


def equity_vs_range(
    hero: list[int],
    villain_range: list[list[int]],
    board: list[int] | None = None,
    num_simulations_per_hand: int = 1000,
) -> float:
    """Calculate equity of hero vs a range of villain hands.

    Args:
        hero: 2 treys card ints.
        villain_range: List of possible villain hands (each is 2 treys card ints).
        board: 0-5 community cards.
        num_simulations_per_hand: Simulations per villain hand combo.

    Returns:
        Average equity across all villain hands in range.
    """
    if board is None:
        board = []
    dead_hero = set(hero + board)

    # Filter out villain hands that conflict with hero/board cards
    valid_hands = [
        v for v in villain_range
        if not (set(v) & dead_hero)
    ]

    if not valid_hands:
        raise ValueError("No valid villain hands after removing card conflicts.")

    total_equity = 0.0
    for vh in valid_hands:
        eq = equity_vs_hand(hero, vh, board, num_simulations_per_hand)
        total_equity += eq

    return total_equity / len(valid_hands)


def _worker_equity_vs_range_batch(args):
    """Worker: compute equity for a batch of villain hands."""
    hero, villain_hands, board, sims_per_hand = args
    total = 0.0
    for vh in villain_hands:
        total += equity_vs_hand(hero, vh, board, sims_per_hand)
    return total, len(villain_hands)


def equity_vs_range_parallel(
    hero: list[int],
    villain_range: list[list[int]],
    board: list[int] | None = None,
    num_simulations_per_hand: int = 1000,
    num_workers: int | None = None,
) -> float:
    """Parallel version of equity_vs_range."""
    if board is None:
        board = []
    dead_hero = set(hero + board)
    valid_hands = [v for v in villain_range if not (set(v) & dead_hero)]

    if not valid_hands:
        raise ValueError("No valid villain hands after removing card conflicts.")

    if num_workers is None:
        num_workers = min(cpu_count(), 8)

    # Split hands across workers
    chunk_size = max(1, len(valid_hands) // num_workers)
    chunks = [
        valid_hands[i:i + chunk_size]
        for i in range(0, len(valid_hands), chunk_size)
    ]

    args = [(hero, chunk, board, num_simulations_per_hand) for chunk in chunks]
    with Pool(num_workers) as pool:
        results = pool.map(_worker_equity_vs_range_batch, args)

    total_eq = sum(r[0] for r in results)
    total_hands = sum(r[1] for r in results)
    return total_eq / total_hands
