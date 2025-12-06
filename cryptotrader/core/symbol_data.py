# core/symbol_data.py

import MetaTrader5 as mt5
import pandas as pd
from typing import Optional, List, Dict
import numpy as np

class SymbolData:
    """Utility class for fetching data and calculating indicators."""

    def __init__(self):
        # A simple cache can be added here if performance is critical
        pass

    def get_ohlc_bars(self, symbol: str, timeframe: int, count: int) -> Optional[pd.DataFrame]:
        """Fetches OHLC data from MT5 and returns a pandas DataFrame."""
        try:
            bars = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if bars is None or len(bars) == 0:
                print(f"Error fetching data for {symbol}: {mt5.last_error()}")
                return None
                
            df = pd.DataFrame(bars)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            return df
        except Exception as e:
            print(f"An error occurred in get_ohlc_bars: {e}")
            return None

    def calculate_vwap(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        """Calculates the Volume Weighted Average Price (VWAP)."""
        if 'tick_volume' not in df.columns or len(df) == 0:
            return None
            
        # --- VWAP Calculation Logic starts here (CORRECTLY INDENTED) ---
        # Typical price (H + L + C) / 3
        df['TypicalPrice'] = (df['high'] + df['low'] + df['close']) / 3
        # TypicalPrice * Volume
        df['TPV'] = df['TypicalPrice'] * df['tick_volume']
        
        # Cumulative Sums
        df['CumTPV'] = df['TPV'].cumsum()
        df['CumVolume'] = df['tick_volume'].cumsum()
        
        # VWAP = Cumulative(TP * Volume) / Cumulative(Volume)
        vwap = df['CumTPV'] / df['CumVolume']
        
        return vwap.to_numpy()
        # --- VWAP Calculation Logic ends here ---

    def calculate_sma(self, df: pd.DataFrame, period: int) -> Optional[np.ndarray]:
        """Calculates the Simple Moving Average (SMA) of the close price."""
        if len(df) < period:
            return None
        # Use pandas rolling mean function for calculation
        sma = df['close'].rolling(window=period, min_periods=period).mean()
        return sma.to_numpy()

    def calculate_support_resistance(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Placeholder for complex S/R calculation logic.
        """
        if len(df) < 5: 
             return {"support": 0.0, "resistance": 0.0}

        return {
            "support": df['low'].tail(20).min(),
            "resistance": df['high'].tail(20).max()
        }

    def calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> Optional[np.ndarray]:
        """Placeholder for RSI calculation."""
        return None