"""Fast equity lookup from precalculated SQLite tables."""

import sqlite3
import os

from poker_ev_system.simulator.table_builder import (
    DB_PATH, categorize_hand, classify_board_texture,
    classify_spr, classify_bet_size, _get_rank_char, _is_suited,
)


class EquityLookup:
    """Fast equity lookup using precalculated tables."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DB_PATH
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Equity database not found at {self.db_path}. "
                "Run table_builder.py first to generate it."
            )
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA cache_size=10000")
        self._cache = {}

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def lookup(
        self,
        hero: list[int],
        board: list[int],
        position: str,
        stack_bb: float,
        pot_bb: float,
        bet_bb: float,
    ) -> float | None:
        """Look up precalculated equity.

        Args:
            hero: 2 treys card ints.
            board: 0-5 community cards.
            position: Player position (UTG/MP/HJ/CO/BTN/BB).
            stack_bb: Stack in big blinds.
            pot_bb: Pot in big blinds.
            bet_bb: Opponent bet in big blinds.

        Returns:
            Equity as float 0-1, or None if no data found.
        """
        r1 = _get_rank_char(hero[0])
        r2 = _get_rank_char(hero[1])
        suited = _is_suited(hero[0], hero[1])
        hand_cat = categorize_hand(r1, r2, suited)
        board_tex = classify_board_texture(board)
        spr = classify_spr(stack_bb, pot_bb)
        bet_size = classify_bet_size(bet_bb, pot_bb)

        if len(board) == 0:
            street = "preflop"
        elif len(board) == 3:
            street = "flop"
        elif len(board) == 4:
            street = "turn"
        else:
            street = "river"

        pos = position.upper()

        cache_key = (hand_cat, board_tex, pos, street, spr, bet_size)
        if cache_key in self._cache:
            return self._cache[cache_key]

        c = self._conn.cursor()
        c.execute(
            "SELECT equity FROM equity WHERE "
            "hand_category=? AND board_texture=? AND position=? AND "
            "street=? AND spr=? AND bet_size=?",
            cache_key,
        )
        row = c.fetchone()
        if row:
            self._cache[cache_key] = row[0]
            return row[0]

        # Fallback: try without bet_size specificity
        c.execute(
            "SELECT AVG(equity) FROM equity WHERE "
            "hand_category=? AND board_texture=? AND street=?",
            (hand_cat, board_tex, street),
        )
        row = c.fetchone()
        if row and row[0] is not None:
            self._cache[cache_key] = row[0]
            return row[0]

        return None
