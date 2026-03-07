"""EV Calculator: computes EV_fold, EV_call, EV_raise for any situation."""

from dataclasses import dataclass

from .equity_lookup import EquityLookup
from .range_model import get_fold_equity, get_position_range
from poker_ev_system.simulator.monte_carlo import equity_vs_range, equity_vs_hand
from poker_ev_system.simulator.hand_evaluator import parse_cards


@dataclass
class EVResult:
    """Result of an EV calculation."""
    ev_fold: float
    ev_call: float
    ev_raise: float
    equity: float
    pot_odds: float
    breakeven_equity: float
    recommended_action: str
    recommended_ev: float


class EVCalculator:
    """Calculate EV for fold/call/raise decisions."""

    def __init__(self, db_path: str | None = None, use_tables: bool = True):
        """Initialize calculator.

        Args:
            db_path: Path to equity SQLite DB.
            use_tables: If True, try precalculated tables first. If False, always use Monte Carlo.
        """
        self._lookup = None
        self._use_tables = use_tables
        if use_tables:
            try:
                self._lookup = EquityLookup(db_path)
            except FileNotFoundError:
                self._use_tables = False

    def close(self):
        if self._lookup:
            self._lookup.close()

    def calculate(
        self,
        hero_cards: list[str],
        board_cards: list[str] | None,
        pot_bb: float,
        bet_bb: float,
        stack_bb: float,
        hero_position: str,
        villain_position: str | None = None,
        raise_size_bb: float | None = None,
        fold_equity: float | None = None,
        num_simulations: int = 10000,
    ) -> EVResult:
        """Calculate EV for all actions.

        Args:
            hero_cards: 2 cards in standard notation (e.g., ['As', 'Kd']).
            board_cards: 0-5 community cards, or None/[] for preflop.
            pot_bb: Current pot in big blinds.
            bet_bb: Opponent's bet to call (0 if check).
            stack_bb: Hero's remaining stack in big blinds.
            hero_position: Hero's position.
            villain_position: Villain's position (for range estimation).
            raise_size_bb: Size of hero's raise (default: 2.5x bet or pot).
            fold_equity: Override fold equity (default from config).
            num_simulations: Monte Carlo sims if tables unavailable.

        Returns:
            EVResult with all EV values and recommendation.
        """
        hero = parse_cards(hero_cards)
        board = parse_cards(board_cards) if board_cards else []

        # Get equity
        equity = self._get_equity(
            hero, board, hero_position, villain_position,
            stack_bb, pot_bb, bet_bb, num_simulations
        )

        # Calculate pot odds
        if bet_bb > 0:
            call_amount = bet_bb
            pot_after_call = pot_bb + call_amount
            pot_odds = call_amount / (pot_after_call + call_amount)
            breakeven_equity = call_amount / (pot_bb + 2 * call_amount)
        else:
            call_amount = 0
            pot_odds = 0
            breakeven_equity = 0

        # EV_fold = 0 (reference)
        ev_fold = 0.0

        # EV_call = (equity * pot_total) - ((1 - equity) * call_amount)
        if bet_bb > 0:
            pot_total = pot_bb + call_amount  # pot after everyone calls
            ev_call = (equity * pot_total) - ((1 - equity) * call_amount)
        else:
            ev_call = 0.0  # checking is free

        # EV_raise
        if fold_equity is None:
            fold_equity = get_fold_equity()

        if raise_size_bb is None:
            if bet_bb > 0:
                raise_size_bb = bet_bb * 2.5  # standard 2.5x raise
            else:
                raise_size_bb = pot_bb * 0.75  # 3/4 pot bet

        pot_if_called = pot_bb + raise_size_bb + bet_bb  # pot if villain calls
        ev_raise = (
            fold_equity * pot_bb +
            (1 - fold_equity) * (equity * pot_if_called - (1 - equity) * raise_size_bb)
        )

        # Determine recommendation
        evs = {"FOLD": ev_fold, "CALL": ev_call, "RAISE": ev_raise}
        if bet_bb == 0:
            # Can't fold to a check; compare CHECK vs BET(raise)
            evs = {"CHECK": 0.0, "BET": ev_raise}

        best_action = max(evs, key=evs.get)
        best_ev = evs[best_action]

        return EVResult(
            ev_fold=ev_fold,
            ev_call=ev_call,
            ev_raise=ev_raise,
            equity=equity,
            pot_odds=pot_odds,
            breakeven_equity=breakeven_equity,
            recommended_action=best_action,
            recommended_ev=best_ev,
        )

    def _get_equity(
        self, hero, board, hero_pos, villain_pos,
        stack_bb, pot_bb, bet_bb, num_sims
    ) -> float:
        """Get equity either from tables or Monte Carlo."""
        # Try precalculated tables first
        if self._use_tables and self._lookup:
            eq = self._lookup.lookup(hero, board, hero_pos, stack_bb, pot_bb, bet_bb)
            if eq is not None:
                return eq

        # Fallback: Monte Carlo vs villain range
        v_pos = villain_pos or "CO"  # default assumption
        villain_range = get_position_range(v_pos)

        # Use fewer sims per hand for range calc
        sims_per = max(100, num_sims // max(len(villain_range), 1))
        return equity_vs_range(hero, villain_range, board, sims_per)
