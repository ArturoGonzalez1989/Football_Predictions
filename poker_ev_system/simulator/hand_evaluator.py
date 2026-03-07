"""Wrapper over the treys library for hand evaluation in NLHE."""

from treys import Card, Evaluator, Deck

_evaluator = Evaluator()

# Rank chars and suit chars for parsing
RANKS = "23456789TJQKA"
SUITS = "shdc"


def parse_card(notation: str) -> int:
    """Parse a card from standard notation (e.g., 'As', 'Kh', 'Td') to treys int.

    Accepts both 'As' and 'as' (case-insensitive for rank, lowercase suit).
    """
    if len(notation) != 2:
        raise ValueError(f"Invalid card notation: '{notation}'. Must be 2 chars (e.g., 'As').")
    rank = notation[0].upper()
    suit = notation[1].lower()
    if rank not in RANKS:
        raise ValueError(f"Invalid rank '{rank}'. Must be one of: {RANKS}")
    if suit not in SUITS:
        raise ValueError(f"Invalid suit '{suit}'. Must be one of: s, h, d, c")
    return Card.new(rank + suit)


def parse_cards(notations: list[str]) -> list[int]:
    """Parse a list of card notations to treys ints."""
    return [parse_card(n) for n in notations]


def evaluate_hand(hole_cards: list[int], board: list[int]) -> int:
    """Evaluate a hand. Returns treys rank (lower is better).

    Args:
        hole_cards: List of 2 treys card ints.
        board: List of 3-5 treys card ints.

    Returns:
        Integer rank (1 = Royal Flush, 7462 = worst hand).
    """
    return _evaluator.evaluate(board, hole_cards)


def hand_rank_class(rank: int) -> int:
    """Get the hand class (1=Straight Flush .. 9=High Card) from a treys rank."""
    return _evaluator.get_rank_class(rank)


def hand_class_string(class_int: int) -> str:
    """Get human-readable string for a hand class."""
    return _evaluator.class_to_string(class_int)


def determine_winner(
    hand1: list[int], hand2: list[int], board: list[int]
) -> int:
    """Determine winner between two hands on a given board.

    Returns:
        1 if hand1 wins, 2 if hand2 wins, 0 if tie.
    """
    rank1 = evaluate_hand(hand1, board)
    rank2 = evaluate_hand(hand2, board)
    if rank1 < rank2:
        return 1
    elif rank2 < rank1:
        return 2
    else:
        return 0


def get_fresh_deck(exclude: list[int] | None = None) -> Deck:
    """Get a fresh 52-card deck, optionally excluding specific cards."""
    deck = Deck()
    if exclude:
        deck.cards = [c for c in deck.cards if c not in exclude]
    return deck
