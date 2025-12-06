# market_watch/global_vwap_watch.py
import MetaTrader5 as mt5
from typing import Dict, Any
import numpy as np
from core.symbol_data import SymbolData
from config.settings import MARKET_WATCH_TIMEFRAME, MARKET_WATCH_BAR_COUNT

TIMEFRAME_STRINGS = {
    mt5.TIMEFRAME_M1: "M1",
    mt5.TIMEFRAME_M5: "M5",
    mt5.TIMEFRAME_M15: "M15",
    mt5.TIMEFRAME_H1: "H1",
    mt5.TIMEFRAME_D1: "D1",
}

class GlobalVwapWatch:
    """
    Analyzes the market based on VWAP, price action, and support/resistance 
    to provide a directional bias and confirmation signal.
    """
    
    def __init__(self, symbol_data: SymbolData):
        self.symbol_data = symbol_data
        self.timeframe = MARKET_WATCH_TIMEFRAME
        self.bar_count = MARKET_WATCH_BAR_COUNT
        
    def analyze_market(self, symbol: str) -> Dict[str, Any]:
        """
        Calculates indicators and determines the current market state for the given symbol.
        
        :param symbol: The trading symbol (e.g., "EURUSD")
        :return: A dictionary containing the market state and confirmation.
        """
        
        # 1. Fetch Data
        df = self.symbol_data.get_ohlc_bars(symbol, self.timeframe, self.bar_count)
        if df is None or df.empty:
            return {"trend": "ERROR", "confirmation": "NEUTRAL", "vwap": None, "current_price": None}
        
        # 2. Calculate VWAP
        vwap_array = self.symbol_data.calculate_vwap(df)
        if vwap_array is None or len(vwap_array) == 0:
            return {"trend": "ERROR", "confirmation": "NEUTRAL", "vwap": None, "current_price": df['close'].iloc[-1]}
            
        current_price = df['close'].iloc[-1]
        current_vwap = vwap_array[-1]
        
        # 3. Determine Trend and Bias (VWAP Logic)
        trend = "CONSOLIDATION"
        bias = "NEUTRAL"
        
        # VWAP Slope: Compare the last N VWAP values (e.g., last 10)
        vwap_lookback = 10
        if len(vwap_array) > vwap_lookback:
            vwap_change = vwap_array[-1] - vwap_array[-vwap_lookback]
            
            if vwap_change > 0:
                trend = "UPTREND"
            elif vwap_change < 0:
                trend = "DOWNTREND"
            # Otherwise, remains CONSOLIDATION

        # Price Position vs. VWAP: Stronger bias when price is consistently above/below
        if current_price > current_vwap:
            bias = "BULLISH"
        elif current_price < current_vwap:
            bias = "BEARISH"
            
        # 4. Determine Support and Resistance (using utility placeholders)
        sr_levels = self.symbol_data.calculate_support_resistance(df)
        support = sr_levels.get("support", 0.0)
        resistance = sr_levels.get("resistance", 0.0)
        
        # 5. Confirmation Logic (Combining Trend and Bias)
        confirmation = "NEUTRAL"
        
        if trend == "UPTREND" and bias == "BULLISH":
            # Price above VWAP AND VWAP sloping up
            confirmation = "STRONG_BUY"
        elif trend == "DOWNTREND" and bias == "BEARISH":
            # Price below VWAP AND VWAP sloping down
            confirmation = "STRONG_SELL"
        elif trend == "CONSOLIDATION" and (current_price < support or current_price > resistance):
            # Price near S/R in consolidation is often considered neutral or a range trade setup
            confirmation = "NEUTRAL" 
        elif bias != "NEUTRAL":
            # Price above VWAP but VWAP is flat/down (e.g., "weak buy")
            confirmation = "WEAK_BUY" if bias == "BULLISH" else "WEAK_SELL"


        # 6. Return the Market State Dictionary
        return {
            "symbol": symbol,
            "timeframe": self.timeframe,
            "current_price": current_price,
            "vwap": current_vwap,
            "trend": trend,
            "bias": bias,
            "support": support,
            "resistance": resistance,
            "confirmation": confirmation
        }

    # Helper function to print the result cleanly
    def print_analysis(self, result: Dict[str, Any]):
        """Prints the market analysis result in a clean format."""
        tf_str = TIMEFRAME_STRINGS.get(result['timeframe'], str(result['timeframe']))
        
        print("--- Market Watch Analysis ---")
        print(f"Symbol: {result['symbol']} @ {tf_str}")
        print(f"Price: {result['current_price']:.4f} | VWAP: {result['vwap']:.4f}")
        print(f"Trend: **{result['trend']}** | Bias: **{result['bias']}**")
        print(f"S/R: S={result['support']:.4f}, R={result['resistance']:.4f}")
        print(f"CONFIRMATION: **{result['confirmation']}**")
        print("-----------------------------")