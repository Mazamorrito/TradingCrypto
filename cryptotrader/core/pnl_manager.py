# core/pnl_manager.py

import MetaTrader5 as mt5
from typing import Dict
from core.trade_manager import TradeManager
from config.settings import (
    TAKE_PROFIT_USD, STOP_LOSS_USD, TRAILING_ACTIVATION_USD, 
    TRAILING_STEP_USD, BREAKEVEN_THRESHOLD
)

class PnLManager:
    """
    Manages closing open positions based on money-based TP, SL, and Trailing Stop.
    
    Uses an internal dictionary to track the maximum profit achieved for each position.
    """
    
    def __init__(self, trade_manager: TradeManager):
        self.trade_manager = trade_manager
        # Dictionary to store the highest profit reached for each ticket
        # Format: {ticket_number: max_profit_usd}
        self.peak_profits: Dict[int, float] = {}
        
        self.TAKE_PROFIT = TAKE_PROFIT_USD
        self.STOP_LOSS = STOP_LOSS_USD
        self.TRAILING_ACTIVATION = TRAILING_ACTIVATION_USD
        self.TRAILING_STEP = TRAILING_STEP_USD
        self.BREAKEVEN_TH = BREAKEVEN_THRESHOLD

    def check_and_close_positions(self, positions: tuple):
        """
        Iterates over all open positions and applies the closing logic.
        """
        if positions is None:
            # Handle the case where mt5.positions_get() returns None
            self.peak_profits.clear() # Clear state if no positions are returned
            return

        current_tickets = {p.ticket for p in positions}
        
        # 1. Cleanup: Remove tickets that are no longer open from the tracker
        old_tickets = list(self.peak_profits.keys())
        for ticket in old_tickets:
            if ticket not in current_tickets:
                del self.peak_profits[ticket]
        
        # 2. Main Processing Loop
        for position in positions:
            ticket = position.ticket
            current_profit = position.profit
            
            # --- Update Peak Profit ---
            # Initialize or update the peak profit for this ticket
            current_peak = self.peak_profits.get(ticket, -float('inf'))
            self.peak_profits[ticket] = max(current_peak, current_profit)
            current_peak = self.peak_profits[ticket]
            
            # --- 2.1. PRIMARY CLOSING LOGIC (Hard TP/SL) ---
            if current_profit >= self.TAKE_PROFIT:
                self.trade_manager.close_position(position, "Take Profit (Money)")
                continue

            if current_profit <= self.STOP_LOSS:
                self.trade_manager.close_position(position, "Stop Loss (Money)")
                continue
                
            # --- 2.2. TRAILING STOP LOGIC ---
            if current_profit >= self.TRAILING_ACTIVATION:
                # Calculate the safe exit level based on peak profit
                trailing_level = current_peak - self.TRAILING_STEP
                
                # Close if the current profit has fallen below the trailing level
                if current_profit <= trailing_level:
                    self.trade_manager.close_position(position, f"Trailing Stop (Locking in {trailing_level:.2f}$)")
                    continue
            
            # --- 2.3. BREAK-EVEN CLOSE (Time-Based/Flat) ---
            # Assuming time-based logic will be added in the main loop or a wrapper
            # For now, we only check for flat/break-even closure if the P&L is near zero.
            if abs(current_profit) <= self.BREAKEVEN_TH:
                # NOTE: Additional time-based check will be needed here if implemented.
                pass # Decision to close based on time/break-even is often separated

            # Output status for observation
            print(f"[PnL] T{ticket}: P/L={current_profit:.2f}, Peak={current_peak:.2f}, SL_Trail={current_peak - self.TRAILING_STEP:.2f}")