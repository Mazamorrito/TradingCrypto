# strategies/vwap_trend_continuation.py

from core.trade_manager import TradeManager
from core.symbol_data import SymbolData
from config.settings import DEFAULT_VOLUME, MT5_MAGIC_NUMBER
from typing import Dict, Any, Optional
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
        
    def check_for_entry(self, symbol: str, market_state: Dict[str, Any], open_positions: tuple) -> Optional[str]:
        """
        Analyzes the market state and local price action to determine the trade side.
        
        :param symbol: The trading symbol.
        :param market_state: The analysis result from GlobalVwapWatch.
        :param open_positions: Tuple of existing open positions (required to enforce single trade per symbol/strategy).
        :return: "buy", "sell", or None.
        """
        confirmation = market_state.get('confirmation')
        trend = market_state.get('trend')
        vwap = market_state.get('vwap')
        current_price = market_state.get('current_price')

        # 1. Check for existing open trade for this strategy
        # This prevents double entry in live trading and helps backtesting simulate the constraint.
        if any(p.magic == STRATEGY_MAGIC and p.symbol == symbol for p in open_positions):
            return None
        
        # 2. Global Sentiment Check (Enforce directional bias)
        is_buy_allowed = confirmation in ["STRONG_BUY", "WEAK_BUY"]
        is_sell_allowed = confirmation in ["STRONG_SELL", "WEAK_SELL"]
        
        if not (is_buy_allowed or is_sell_allowed):
            return None
            
        # 3. Local Condition: Check for "Bounce" signal (e.g., last 2 bars)
        # We need at least 3 bars (current, previous, and one more for calculation stability)
        df = self.symbol_data.get_ohlc_bars(symbol, mt5.TIMEFRAME_M5, 3) 
        
        if df.empty or len(df) < 3:
             return None # Not enough data for bounce check

        # Simplistic "bounce" check: previous bar closed on one side of VWAP, current bar closed on the other.
        # Ensure we check the previous bar's close price.
        prev_close = df['close'].iloc[-2]
        
        # --- BUY BOUNCE ---
        # Condition: Strong BUY trend AND price bounced off VWAP support
        # (Previous close < VWAP AND Current close > VWAP) within an uptrend
        if is_buy_allowed and trend == "UPTREND" and prev_close < vwap and current_price > vwap:
            return "buy"
            
        # --- SELL BOUNCE ---
        # Condition: Strong SELL trend AND price bounced off VWAP resistance
        # (Previous close > VWAP AND Current close < VWAP) within a downtrend
        elif is_sell_allowed and trend == "DOWNTREND" and prev_close > vwap and current_price < vwap:
            return "sell"
            
        return None

    def place_order(self, symbol: str, side: str):
        """
        Executes the trade using the TradeManager.
        This method is used primarily for LIVE TRADING.
        
        :param symbol: The trading symbol.
        :param side: "buy" or "sell".
        """
        if side == "buy":
            self.trade_manager.place_order(
                symbol=symbol,
                side="buy",
                volume=self.volume,
                comment="VWAP_BOUNCE_BUY",
                magic=STRATEGY_MAGIC
            )
        elif side == "sell":
            self.trade_manager.place_order(
                symbol=symbol,
                side="sell",
                volume=self.volume,
                comment="VWAP_BOUNCE_SELL",
                magic=STRATEGY_MAGIC
            )