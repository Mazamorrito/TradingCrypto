import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
import MetaTrader5 as mt5

# --- HELPER FUNCTIONS ---

def calculate_true_range(df: pd.DataFrame) -> pd.Series:
    """Calculates the True Range (TR) for volatility."""
    high_low = df['high'] - df['low']
    high_prev_close = np.abs(df['high'] - df['close'].shift(1))
    low_prev_close = np.abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    return tr

def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Calculates the Average True Range (ATR)."""
    tr = calculate_true_range(df)
    # Use exponential smoothing (standard for ATR)
    return tr.ewm(span=period, adjust=False).mean()

def calculate_vwap_series(df: pd.DataFrame) -> pd.Series:
    """Calculates the Volume Weighted Average Price (VWAP) as a cumulative series."""
    # Use Typical Price (H+L+C)/3
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_vol'] = df['tp'] * df['tick_volume']
    
    # VWAP is the cumulative sum of (TP * Volume) / cumulative sum of Volume
    vwap_series = df['tp_vol'].cumsum() / df['tick_volume'].cumsum()
    return vwap_series

# ----------------------------------------------------------------------
# MODULE 1: VOLATILITY REGIME DETECTION (ATR Z-Score)
# ----------------------------------------------------------------------

class VolatilityRegimeModule:
    
    ATR_PERIOD = 14     # Period for the current ATR calculation
    ZSCORE_PERIOD = 200 # Lookback period for Mean/StdDev calculation
    DATA_BARS = ZSCORE_PERIOD + 1 # Min bars needed
    
    def __init__(self, symbol_data):
        self.symbol_data = symbol_data
        
    def get_volatility_zscore(self, symbol: str, timeframe=mt5.TIMEFRAME_M5) -> float:
        """
        Calculates the ATR Z-Score to determine if the market is trending (high vol) 
        or ranging (low vol) relative to its recent history.
        """
        # Fetch enough data for the long ZSCORE_PERIOD
        df = self.symbol_data.get_ohlc_bars(symbol, timeframe, self.DATA_BARS)
        
        if df is None or len(df) < self.DATA_BARS:
            return 0.0 # Default to neutral
            
        # 1. Calculate the ATR series
        atr_series = calculate_atr(df, self.ATR_PERIOD)
        
        # We need enough ATR values for the ZSCORE_PERIOD
        if len(atr_series.dropna()) < self.ZSCORE_PERIOD:
             return 0.0

        # 2. Calculate Mean and Standard Deviation over the ZSCORE_PERIOD
        # We look at the ATR values BEFORE the current bar for stable stats
        recent_atr = atr_series.iloc[-self.ZSCORE_PERIOD-1:-1]
        
        mean_atr = recent_atr.mean()
        std_atr = recent_atr.std()
        current_atr = atr_series.iloc[-1]
        
        # Avoid division by zero
        if std_atr == 0:
            return 0.0
            
        # 3. Calculate the ATR Z-Score
        atr_zscore = (current_atr - mean_atr) / std_atr
        
        return atr_zscore

# ----------------------------------------------------------------------
# MODULE 2: LIQUIDITY AND VOLUME STRUCTURE (VWAP Bands)
# ----------------------------------------------------------------------

class VwapStructureModule:
    
    TIMEFRAME = mt5.TIMEFRAME_D1 # Typically VWAP is calculated intraday, using daily bars for simplicity here
    
    def __init__(self, symbol_data):
        self.symbol_data = symbol_data
        
    def get_vwap_bands(self, symbol: str, num_bars: int = 200) -> Dict[str, float]:
        """
        Calculates VWAP and its volume-weighted standard deviation bands 
        to identify structural support/resistance.
        
        Returns the last VWAP and its +1/+2 SD bands.
        """
        
        # Fetch the data. Ensure it has 'tick_volume'
        df = self.symbol_data.get_ohlc_bars(symbol, self.TIMEFRAME, num_bars)
        
        # Check for required columns
        if df is None or 'tick_volume' not in df.columns or len(df) < 2:
            return {"VWAP": np.nan, "SD1_P": np.nan, "SD2_P": np.nan, "SD1_N": np.nan, "SD2_N": np.nan}
        
        # 1. Calculate VWAP series
        vwap_series = calculate_vwap_series(df)
        last_vwap = vwap_series.iloc[-1]
        
        # 2. Calculate the volume-weighted standard deviation (VSD)
        
        # Calculate Typical Price and deviations
        df['tp'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Calculate deviation of TP from VWAP
        df['deviation'] = df['tp'] - vwap_series
        df['dev_sq_vol'] = (df['deviation'] ** 2) * df['tick_volume']
        
        # VSD is sqrt( (Cumulative Sum of (Dev^2 * Vol)) / (Cumulative Sum of Vol) )
        vsd_series = np.sqrt(df['dev_sq_vol'].cumsum() / df['tick_volume'].cumsum())
        last_vsd = vsd_series.iloc[-1]
        
        # 3. Define Bands
        
        results = {
            "VWAP": last_vwap,
            "SD1_P": last_vwap + (1 * last_vsd), # +1 Standard Deviation
            "SD2_P": last_vwap + (2 * last_vsd), # +2 Standard Deviation
            "SD1_N": last_vwap - (1 * last_vsd), # -1 Standard Deviation
            "SD2_N": last_vwap - (2 * last_vsd), # -2 Standard Deviation
            "VSD": last_vsd
        }
        
        return results