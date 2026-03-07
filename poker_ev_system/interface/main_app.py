"""Main desktop application for Poker EV System - Tkinter interface."""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poker_ev_system.engine.ev_calculator import EVCalculator, EVResult


class PokerEVApp:
    """Main application window for the Poker EV Calculator."""

    POSITIONS = ["UTG", "MP", "HJ", "CO", "BTN", "SB", "BB"]
    CARD_RANKS = "A K Q J T 9 8 7 6 5 4 3 2".split()
    CARD_SUITS = ["s", "h", "d", "c"]

    def __init__(self, root: tk.Tk, calculator: EVCalculator | None = None):
        self.root = root
        self.root.title("Poker EV Calculator")
        self.root.geometry("800x650")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(True, True)

        self.calculator = calculator or EVCalculator(use_tables=True)

        # Variables
        self.hero_card1 = tk.StringVar(value="")
        self.hero_card2 = tk.StringVar(value="")
        self.board_cards = tk.StringVar(value="")
        self.pot_bb = tk.StringVar(value="6")
        self.bet_bb = tk.StringVar(value="4")
        self.stack_bb = tk.StringVar(value="100")
        self.hero_pos = tk.StringVar(value="BTN")
        self.villain_pos = tk.StringVar(value="CO")
        self.raise_size = tk.StringVar(value="")

        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Helvetica", 16, "bold"),
                        background="#1a1a2e", foreground="#e0e0e0")
        style.configure("Input.TLabel", font=("Helvetica", 11),
                        background="#1a1a2e", foreground="#c0c0c0")
        style.configure("Big.TLabel", font=("Helvetica", 14, "bold"),
                        background="#1a1a2e", foreground="#ffffff")
        style.configure("Result.TLabel", font=("Helvetica", 12),
                        background="#1a1a2e", foreground="#ffffff")
        style.configure("Green.TLabel", font=("Helvetica", 18, "bold"),
                        background="#1a1a2e", foreground="#00ff88")
        style.configure("Red.TLabel", font=("Helvetica", 18, "bold"),
                        background="#1a1a2e", foreground="#ff4444")
        style.configure("Neutral.TLabel", font=("Helvetica", 18, "bold"),
                        background="#1a1a2e", foreground="#ffaa00")

        main = ttk.Frame(self.root, padding=15)
        main.pack(fill=tk.BOTH, expand=True)
        main.configure(style="TFrame")
        style.configure("TFrame", background="#1a1a2e")

        # Title
        ttk.Label(main, text="POKER EV CALCULATOR", style="Title.TLabel").grid(
            row=0, column=0, columnspan=4, pady=(0, 10))

        # --- Input Section ---
        input_frame = ttk.LabelFrame(main, text="Situation Input", padding=10)
        input_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=5)
        style.configure("TLabelframe", background="#1a1a2e", foreground="#e0e0e0")
        style.configure("TLabelframe.Label", background="#1a1a2e", foreground="#e0e0e0")

        row = 0
        # Hero cards
        ttk.Label(input_frame, text="Hero Cards (e.g. As Kd):", style="Input.TLabel").grid(
            row=row, column=0, sticky="w", padx=5)
        e1 = ttk.Entry(input_frame, textvariable=self.hero_card1, width=5, font=("Courier", 12))
        e1.grid(row=row, column=1, padx=2)
        e2 = ttk.Entry(input_frame, textvariable=self.hero_card2, width=5, font=("Courier", 12))
        e2.grid(row=row, column=2, padx=2)
        self._first_entry = e1

        row += 1
        ttk.Label(input_frame, text="Board (e.g. Ah Td 5c):", style="Input.TLabel").grid(
            row=row, column=0, sticky="w", padx=5)
        ttk.Entry(input_frame, textvariable=self.board_cards, width=20, font=("Courier", 12)).grid(
            row=row, column=1, columnspan=3, sticky="w", padx=2)

        row += 1
        ttk.Label(input_frame, text="Pot (bb):", style="Input.TLabel").grid(
            row=row, column=0, sticky="w", padx=5)
        ttk.Entry(input_frame, textvariable=self.pot_bb, width=8, font=("Courier", 12)).grid(
            row=row, column=1, padx=2)
        ttk.Label(input_frame, text="Bet to call (bb):", style="Input.TLabel").grid(
            row=row, column=2, sticky="w", padx=5)
        ttk.Entry(input_frame, textvariable=self.bet_bb, width=8, font=("Courier", 12)).grid(
            row=row, column=3, padx=2)

        row += 1
        ttk.Label(input_frame, text="Stack (bb):", style="Input.TLabel").grid(
            row=row, column=0, sticky="w", padx=5)
        ttk.Entry(input_frame, textvariable=self.stack_bb, width=8, font=("Courier", 12)).grid(
            row=row, column=1, padx=2)
        ttk.Label(input_frame, text="Raise size (bb):", style="Input.TLabel").grid(
            row=row, column=2, sticky="w", padx=5)
        ttk.Entry(input_frame, textvariable=self.raise_size, width=8, font=("Courier", 12)).grid(
            row=row, column=3, padx=2)

        row += 1
        ttk.Label(input_frame, text="Hero Position:", style="Input.TLabel").grid(
            row=row, column=0, sticky="w", padx=5)
        pos_combo = ttk.Combobox(input_frame, textvariable=self.hero_pos,
                                  values=self.POSITIONS, width=6, font=("Courier", 11))
        pos_combo.grid(row=row, column=1, padx=2)
        ttk.Label(input_frame, text="Villain Position:", style="Input.TLabel").grid(
            row=row, column=2, sticky="w", padx=5)
        ttk.Combobox(input_frame, textvariable=self.villain_pos,
                     values=self.POSITIONS, width=6, font=("Courier", 11)).grid(
            row=row, column=3, padx=2)

        # Calculate button
        row += 1
        calc_btn = ttk.Button(input_frame, text="CALCULATE (Enter)",
                               command=self._calculate)
        calc_btn.grid(row=row, column=0, columnspan=2, pady=10, sticky="ew")

        clear_btn = ttk.Button(input_frame, text="CLEAR (Esc)",
                                command=self._clear)
        clear_btn.grid(row=row, column=2, columnspan=2, pady=10, sticky="ew")

        # --- Output Section ---
        self.output_frame = ttk.LabelFrame(main, text="Results", padding=15)
        self.output_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=10)
        main.rowconfigure(2, weight=1)
        main.columnconfigure(0, weight=1)

        # Recommendation (big text)
        self.rec_label = ttk.Label(self.output_frame, text="Enter situation and press Enter",
                                    style="Neutral.TLabel")
        self.rec_label.grid(row=0, column=0, columnspan=4, pady=5)

        # EV values
        self.ev_fold_label = ttk.Label(self.output_frame, text="FOLD: 0 bb (ref)", style="Result.TLabel")
        self.ev_fold_label.grid(row=1, column=0, padx=10, pady=3)

        self.ev_call_label = ttk.Label(self.output_frame, text="CALL: --", style="Result.TLabel")
        self.ev_call_label.grid(row=1, column=1, padx=10, pady=3)

        self.ev_raise_label = ttk.Label(self.output_frame, text="RAISE: --", style="Result.TLabel")
        self.ev_raise_label.grid(row=1, column=2, padx=10, pady=3)

        # Equity details
        self.equity_label = ttk.Label(self.output_frame, text="Equity: --", style="Big.TLabel")
        self.equity_label.grid(row=2, column=0, columnspan=2, pady=5, sticky="w", padx=10)

        self.potodds_label = ttk.Label(self.output_frame, text="Pot Odds: --", style="Big.TLabel")
        self.potodds_label.grid(row=2, column=2, columnspan=2, pady=5, sticky="w", padx=10)

        self.be_label = ttk.Label(self.output_frame, text="Breakeven: --", style="Result.TLabel")
        self.be_label.grid(row=3, column=0, columnspan=4, pady=3, sticky="w", padx=10)

        self.time_label = ttk.Label(self.output_frame, text="", style="Result.TLabel")
        self.time_label.grid(row=4, column=0, columnspan=4, pady=3, sticky="w", padx=10)

        # Shortcuts help
        help_text = "Shortcuts: Enter=Calculate | Esc=Clear | Ctrl+Q=Quit | Tab=Next field"
        ttk.Label(main, text=help_text, style="Input.TLabel").grid(
            row=3, column=0, columnspan=4, pady=5)

    def _setup_shortcuts(self):
        self.root.bind("<Return>", lambda e: self._calculate())
        self.root.bind("<Escape>", lambda e: self._clear())
        self.root.bind("<Control-q>", lambda e: self.root.quit())
        self.root.bind("<Control-Q>", lambda e: self.root.quit())

    def _clear(self):
        self.hero_card1.set("")
        self.hero_card2.set("")
        self.board_cards.set("")
        self.pot_bb.set("6")
        self.bet_bb.set("4")
        self.stack_bb.set("100")
        self.raise_size.set("")
        self.rec_label.configure(text="Enter situation and press Enter", style="Neutral.TLabel")
        self.ev_fold_label.configure(text="FOLD: 0 bb (ref)")
        self.ev_call_label.configure(text="CALL: --")
        self.ev_raise_label.configure(text="RAISE: --")
        self.equity_label.configure(text="Equity: --")
        self.potodds_label.configure(text="Pot Odds: --")
        self.be_label.configure(text="Breakeven: --")
        self.time_label.configure(text="")
        self._first_entry.focus_set()

    def _calculate(self):
        try:
            c1 = self.hero_card1.get().strip()
            c2 = self.hero_card2.get().strip()
            if not c1 or not c2:
                messagebox.showwarning("Input", "Enter both hero cards.")
                return

            board_str = self.board_cards.get().strip()
            board = board_str.split() if board_str else []

            pot = float(self.pot_bb.get())
            bet = float(self.bet_bb.get())
            stack = float(self.stack_bb.get())
            h_pos = self.hero_pos.get()
            v_pos = self.villain_pos.get()

            raise_sz = None
            rs = self.raise_size.get().strip()
            if rs:
                raise_sz = float(rs)

            start = time.time()
            result = self.calculator.calculate(
                hero_cards=[c1, c2],
                board_cards=board if board else None,
                pot_bb=pot,
                bet_bb=bet,
                stack_bb=stack,
                hero_position=h_pos,
                villain_position=v_pos,
                raise_size_bb=raise_sz,
            )
            elapsed = time.time() - start

            self._display_result(result, elapsed)

        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    def _display_result(self, r: EVResult, elapsed: float):
        # Main recommendation
        if r.recommended_ev > 0:
            style = "Green.TLabel"
        elif r.recommended_ev < -0.5:
            style = "Red.TLabel"
        else:
            style = "Neutral.TLabel"

        self.rec_label.configure(
            text=f"{r.recommended_action}  ({r.recommended_ev:+.2f} bb)",
            style=style
        )

        # EV values
        self.ev_fold_label.configure(text=f"FOLD: 0.00 bb")
        self.ev_call_label.configure(text=f"CALL: {r.ev_call:+.2f} bb")
        self.ev_raise_label.configure(text=f"RAISE: {r.ev_raise:+.2f} bb")

        # Equity
        self.equity_label.configure(text=f"Equity: {r.equity*100:.1f}%")
        self.potodds_label.configure(text=f"Pot Odds: {r.pot_odds*100:.1f}%")
        self.be_label.configure(text=f"Breakeven equity needed: {r.breakeven_equity*100:.1f}%")
        self.time_label.configure(text=f"Calculated in {elapsed*1000:.0f}ms")


def main():
    """Launch the Poker EV Calculator application."""
    root = tk.Tk()
    app = PokerEVApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
