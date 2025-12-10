# strategies/vwap_trend_continuation.py

from core.trade_manager import TradeManager
from core.symbol_data import SymbolData
# CRITICAL FIX: Import the shared timeframe setting
from config.settings import DEFAULT_VOLUME, MT5_MAGIC_NUMBER, MARKET_WATCH_TIMEFRAME 
from typing import Dict, Any, Optional

# Unique Magic Number for this strategy
STRATEGY_MAGIC = MT5_MAGIC_NUMBER + 1 

class VwapTrendContinuation:
    """
    VWAP Trend Continuation (The "Bounce" Strategy):
    Trades placed on a pullback to the VWAP line within a confirmed strong trend.
    (Entry logic fixed to use a more robust "touch and close" condition)
    """
    def __init__(self, trade_manager: TradeManager, symbol_data: SymbolData):
        self.trade_manager = trade_manager
        self.symbol_data = symbol_data
        self.volume = DEFAULT_VOLUME
        
    def check_for_entry(self, symbol: str, market_state: Dict[str, Any], open_positions: tuple) -> Optional[str]:
        """
        FIXED LOGIC: Uses a "VWAP Touch and Close" condition for better signal generation 
        in backtesting, combined with the GlobalVwapWatch trend.
        """
        # 0. Enforce single position constraint
        if open_positions:
            return None 

        trend = market_state.get('trend')
        vwap = market_state.get('vwap')
        current_price = market_state.get('current_price')
        
        # Check for invalid indicator data
        if vwap is None or current_price is None:
            return None
        
        # 1. Get the current bar's OHLC data to check the 'touch' (Count=2 ensures we get the current bar's full data)
        df = self.symbol_data.get_ohlc_bars(symbol, timeframe=MARKET_WATCH_TIMEFRAME, count=2) 
        
        if df.empty or len(df) < 2:
            return None

        current_bar = df.iloc[-1]
        current_high = current_bar['high']
        current_low = current_bar['low']
        
        # --- BUY BOUNCE/CONTINUATION ---
        # 1. Must be in an uptrend ("UPTREND")
        # 2. Price must have touched VWAP (current bar's low <= VWAP)
        # 3. Bar must have closed *above* VWAP for confirmation
        if (trend == "UPTREND" and 
            current_low <= vwap and 
            current_price > vwap):
            # 
            return "buy"
            
        # --- SELL BOUNCE/CONTINUATION ---
        # 1. Must be in a downtrend ("DOWNTREND")
        # 2. Price must have touched VWAP (current bar's high >= VWAP)
        # 3. Bar must have closed *below* VWAP for confirmation
        elif (trend == "DOWNTREND" and 
              current_high >= vwap and 
              current_price < vwap):
            # 
            return "sell"
            
        return None

    def place_order(self, symbol: str, side: str):
        """
        Executes the trade using the TradeManager. (Live Trading)
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