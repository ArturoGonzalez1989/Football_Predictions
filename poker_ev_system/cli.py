"""CLI interface for the Poker EV Calculator.

Usage:
    # Single calculation
    python -m poker_ev_system calc --hero AsAd --board QhJhTs --pot 12 --bet 8 --stack 92 --pos BTN

    # Interactive mode
    python -m poker_ev_system play --stack 100 --pos BTN

    # Quick preflop check
    python -m poker_ev_system preflop --hero AKs --pos CO --vs UTG
"""

import argparse
import sys
import re

from poker_ev_system.engine.ev_calculator import EVCalculator, EVResult


def _parse_hand(hand_str: str) -> list[str]:
    """Parse hand input: 'AsKd' or 'As Kd' or 'As,Kd' → ['As', 'Kd']."""
    hand_str = hand_str.strip().replace(",", " ")
    # Try splitting on space first
    parts = hand_str.split()
    if len(parts) == 2:
        return parts
    # Try pairs of chars: 'AsKd' → ['As', 'Kd']
    if len(hand_str) == 4:
        return [hand_str[:2], hand_str[2:]]
    raise ValueError(f"Cannot parse hand: '{hand_str}'. Use format like 'AsKd' or 'As Kd'.")


def _parse_board(board_str: str) -> list[str] | None:
    """Parse board: 'QhJhTs' → ['Qh', 'Jh', 'Ts'], or None."""
    if not board_str or board_str.lower() in ("none", "-", ""):
        return None
    board_str = board_str.strip().replace(",", " ").replace("/", " ")
    parts = board_str.split()
    if len(parts) >= 3:
        return parts
    # Parse continuous string: 'QhJhTs' → ['Qh', 'Jh', 'Ts']
    cards = re.findall(r'[2-9TJQKA][shdc]', board_str, re.IGNORECASE)
    if len(cards) >= 3:
        return cards
    raise ValueError(f"Cannot parse board: '{board_str}'. Use format like 'QhJhTs' or 'Qh Jh Ts'.")


PREFLOP_MAP = {
    "AA": ["As", "Ad"], "KK": ["Ks", "Kd"], "QQ": ["Qs", "Qd"],
    "JJ": ["Js", "Jd"], "TT": ["Ts", "Td"], "99": ["9s", "9d"],
    "88": ["8s", "8d"], "77": ["7s", "7d"], "66": ["6s", "6d"],
    "55": ["5s", "5d"], "44": ["4s", "4d"], "33": ["3s", "3d"],
    "22": ["2s", "2d"],
}


def _parse_preflop_hand(notation: str) -> list[str]:
    """Parse canonical notation: 'AKs' → ['Ah','Kh'], 'AKo' → ['Ah','Kd'], 'AA' → ['As','Ad']."""
    notation = notation.strip()
    if notation in PREFLOP_MAP:
        return PREFLOP_MAP[notation]
    if len(notation) == 3 and notation[2] in "so":
        r1, r2, suit_type = notation[0], notation[1], notation[2]
        if suit_type == "s":
            return [f"{r1}h", f"{r2}h"]
        else:
            return [f"{r1}h", f"{r2}d"]
    # Fallback to regular parse
    return _parse_hand(notation)


def _format_result(result: EVResult, hero_str: str, board_str: str | None) -> str:
    """Format EVResult for terminal display."""
    lines = []
    lines.append("")
    lines.append(f"  Hand: {hero_str}" + (f"  Board: {board_str}" if board_str else "  (Preflop)"))
    lines.append(f"  {'─' * 44}")
    lines.append(f"  Equity:          {result.equity:.1%}")
    lines.append(f"  Pot Odds:        {result.pot_odds:.1%}")
    lines.append(f"  Breakeven Eq:    {result.breakeven_equity:.1%}")
    lines.append(f"  {'─' * 44}")
    lines.append(f"  EV(fold):  {result.ev_fold:+.2f} BB")
    lines.append(f"  EV(call):  {result.ev_call:+.2f} BB")
    lines.append(f"  EV(raise): {result.ev_raise:+.2f} BB")
    lines.append(f"  {'─' * 44}")

    action = result.recommended_action
    ev = result.recommended_ev
    if ev > 2:
        strength = "STRONG"
    elif ev > 0.5:
        strength = "GOOD"
    elif ev > 0:
        strength = "MARGINAL"
    else:
        strength = "NEUTRAL"

    lines.append(f"  >>> {action} ({strength}, EV: {ev:+.2f} BB) <<<")
    lines.append("")
    return "\n".join(lines)


def cmd_calc(args):
    """Execute a single EV calculation."""
    hero = _parse_hand(args.hero)
    board = _parse_board(args.board) if args.board else None

    calc = EVCalculator(use_tables=not args.no_tables)
    result = calc.calculate(
        hero_cards=hero,
        board_cards=board,
        pot_bb=args.pot,
        bet_bb=args.bet,
        stack_bb=args.stack,
        hero_position=args.pos.upper(),
        villain_position=args.vs.upper() if args.vs else None,
        fold_equity=args.fold_equity,
        num_simulations=args.sims,
    )
    calc.close()

    print(_format_result(result, args.hero, args.board))


def cmd_preflop(args):
    """Quick preflop lookup."""
    hero = _parse_preflop_hand(args.hero)

    calc = EVCalculator(use_tables=True)
    result = calc.calculate(
        hero_cards=hero,
        board_cards=None,
        pot_bb=args.pot,
        bet_bb=args.bet,
        stack_bb=args.stack,
        hero_position=args.pos.upper(),
        villain_position=args.vs.upper() if args.vs else None,
        fold_equity=args.fold_equity,
        num_simulations=1000,
    )
    calc.close()

    print(_format_result(result, args.hero, None))


def cmd_play(args):
    """Interactive session mode."""
    print("Poker EV Calculator - Interactive Mode")
    print(f"Stack: {args.stack} BB | Position: {args.pos}")
    print("Type 'quit' to exit, 'help' for commands.\n")

    calc = EVCalculator(use_tables=not args.no_tables)
    stack = args.stack
    position = args.pos.upper()
    hand_num = 0

    while True:
        try:
            raw = input(f"[{position} {stack:.0f}BB] Hand> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not raw:
            continue
        if raw.lower() in ("quit", "exit", "q"):
            print("Session ended.")
            break
        if raw.lower() == "help":
            print("  Enter hand: AsKd or AKs (canonical)")
            print("  Then follow prompts for board/pot/bet")
            print("  Commands: stack <N>, pos <POS>, quit")
            continue
        if raw.lower().startswith("stack "):
            try:
                stack = float(raw.split()[1])
                print(f"  Stack set to {stack:.0f} BB")
            except (IndexError, ValueError):
                print("  Usage: stack <number>")
            continue
        if raw.lower().startswith("pos "):
            position = raw.split()[1].upper()
            print(f"  Position set to {position}")
            continue

        # Parse hero hand
        try:
            if len(raw) <= 3 and not any(c in raw for c in "shdc"):
                hero = _parse_preflop_hand(raw)
            else:
                hero = _parse_hand(raw)
        except ValueError as e:
            print(f"  Error: {e}")
            continue

        hand_num += 1

        # Get board
        try:
            board_raw = input("  Board (or Enter for preflop)> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break
        board = None
        if board_raw:
            try:
                board = _parse_board(board_raw)
            except ValueError as e:
                print(f"  Error: {e}")
                continue

        # Get pot and bet
        try:
            pot_raw = input("  Pot (BB) [6]> ").strip()
            pot = float(pot_raw) if pot_raw else 6.0
            bet_raw = input("  Bet to call (BB) [3]> ").strip()
            bet = float(bet_raw) if bet_raw else 3.0
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break
        except ValueError:
            print("  Invalid number.")
            continue

        # Get villain position
        try:
            vs_raw = input("  Villain position [CO]> ").strip()
            vs = vs_raw.upper() if vs_raw else "CO"
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        result = calc.calculate(
            hero_cards=[hero[0], hero[1]],
            board_cards=board,
            pot_bb=pot,
            bet_bb=bet,
            stack_bb=stack,
            hero_position=position,
            villain_position=vs,
            fold_equity=0.45,
            num_simulations=args.sims,
        )

        hero_display = f"{hero[0]}{hero[1]}"
        board_display = " ".join(board) if board else None
        print(_format_result(result, hero_display, board_display))

    calc.close()


def main(argv=None):
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="poker-ev",
        description="Poker EV Calculator - compute optimal decisions",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # calc command
    p_calc = subparsers.add_parser("calc", help="Single EV calculation")
    p_calc.add_argument("--hero", required=True, help="Hero cards (e.g., AsKd)")
    p_calc.add_argument("--board", default=None, help="Board cards (e.g., QhJhTs)")
    p_calc.add_argument("--pot", type=float, required=True, help="Pot size in BB")
    p_calc.add_argument("--bet", type=float, required=True, help="Bet to call in BB")
    p_calc.add_argument("--stack", type=float, default=100, help="Stack in BB (default: 100)")
    p_calc.add_argument("--pos", default="BTN", help="Hero position (default: BTN)")
    p_calc.add_argument("--vs", default=None, help="Villain position")
    p_calc.add_argument("--fold-equity", type=float, default=None, help="Override fold equity")
    p_calc.add_argument("--sims", type=int, default=10000, help="Monte Carlo sims (default: 10000)")
    p_calc.add_argument("--no-tables", action="store_true", help="Force Monte Carlo (skip tables)")
    p_calc.set_defaults(func=cmd_calc)

    # preflop command
    p_pre = subparsers.add_parser("preflop", help="Quick preflop lookup")
    p_pre.add_argument("--hero", required=True, help="Hand notation (e.g., AKs, QQ, T9o)")
    p_pre.add_argument("--pot", type=float, default=6, help="Pot in BB (default: 6)")
    p_pre.add_argument("--bet", type=float, default=3, help="Bet to call in BB (default: 3)")
    p_pre.add_argument("--stack", type=float, default=100, help="Stack in BB (default: 100)")
    p_pre.add_argument("--pos", default="BTN", help="Hero position (default: BTN)")
    p_pre.add_argument("--vs", default=None, help="Villain position")
    p_pre.add_argument("--fold-equity", type=float, default=None, help="Override fold equity")
    p_pre.set_defaults(func=cmd_preflop)

    # play command
    p_play = subparsers.add_parser("play", help="Interactive session")
    p_play.add_argument("--stack", type=float, default=100, help="Starting stack in BB")
    p_play.add_argument("--pos", default="BTN", help="Starting position")
    p_play.add_argument("--sims", type=int, default=5000, help="Monte Carlo sims")
    p_play.add_argument("--no-tables", action="store_true", help="Force Monte Carlo")
    p_play.set_defaults(func=cmd_play)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
