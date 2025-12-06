# strategies/vwap_trend_continuation.py

from core.trade_manager import TradeManager
from core.symbol_data import SymbolData
from config.settings import DEFAULT_VOLUME, MT5_MAGIC_NUMBER
from typing import Dict, Any
import MetaTrader5 as mt5

# Unique Magic Number for this strategy
STRATEGY_MAGIC = MT5_MAGIC_NUMBER + 1 

class VwapTrendContinuation:
    """
    VWAP Trend Continuation (The "Bounce" Strategy):
    Trades placed on a pullback to the VWAP line within a confirmed strong trend.
    """
    def __init__(self, trade_manager: TradeManager, symbol_data: SymbolData):
        self.trade_manager = trade_manager
        self.symbol_data = symbol_data
        self.volume = DEFAULT_VOLUME
        
    def check_for_entry(self,symbol:str, market_state: Dict[str, Any], open_positions: tuple):
        """
        Analyzes the market state and local price action to place a trade.
        """
        confirmation = market_state.get('confirmation')
        trend = market_state.get('trend')
        vwap = market_state.get('vwap')
        current_price = market_state.get('current_price')

        # Check for existing open trade for this strategy
        if any(p.magic == STRATEGY_MAGIC and p.symbol == symbol for p in open_positions):
            return
        
        # 1. Global Sentiment Check (Enforce directional bias)
        is_buy_allowed = confirmation in ["STRONG_BUY", "WEAK_BUY"]
        is_sell_allowed = confirmation in ["STRONG_SELL", "WEAK_SELL"]
        
        if not (is_buy_allowed or is_sell_allowed):
            return 
            
        # 2. Local Condition: Check for "Bounce" signal (e.g., last 2 bars)
        df = self.symbol_data.get_ohlc_bars(symbol, mt5.TIMEFRAME_M5, 3)
        
        # Simplistic "bounce" check: previous bar touched VWAP, current bar closed away.
        prev_close = df['close'].iloc[-2]
        
        # --- BUY BOUNCE ---
        # Condition: Strong BUY trend AND price bounced off VWAP support
        if is_buy_allowed and trend == "UPTREND" and prev_close < vwap and current_price > vwap:
            self.trade_manager.place_order(
                symbol=symbol,
                side="buy",
                volume=self.volume,
                comment="VWAP_BOUNCE_BUY",
            )
            
        # --- SELL BOUNCE ---
        # Condition: Strong SELL trend AND price bounced off VWAP resistance
        elif is_sell_allowed and trend == "DOWNTREND" and prev_close > vwap and current_price < vwap:
            self.trade_manager.place_order(
                symbol=symbol,
                side="sell",
                volume=self.volume,
                comment="VWAP_BOUNCE_SELL",
            )