import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Type
from datetime import datetime
import csv 
import re

# IMPORTANT: Mock wrappers for external imports are used to maintain stability
try:
    from strategies.vwap_trend_continuation import VwapTrendContinuation, STRATEGY_MAGIC
    from market_watch.global_vwap_watch import GlobalVwapWatch
    from config.settings import DEFAULT_VOLUME, MARKET_WATCH_BAR_COUNT, MT5_MAGIC_NUMBER, MARKET_WATCH_TIMEFRAME 
except ImportError as e:
    print(f"Warning: Could not fully import dependencies. Using mock wrappers. Error: {e}")
    # Define fallbacks if real imports fail
    STRATEGY_MAGIC = 20240902 # Fallback Magic Number
    DEFAULT_VOLUME = 0.1
    MARKET_WATCH_BAR_COUNT = 300
    
    # Mock classes for missing components (required to run the backtester logic)
    class VwapTrendContinuation:
        STRATEGY_MAGIC = STRATEGY_MAGIC
        def __init__(self, tm, sd): self.trade_manager = tm; self.symbol_data = sd
        def check_for_entry(self, *args, **kwargs): return None
    class GlobalVwapWatch:
        def __init__(self, sd): self.symbol_data = sd
        def analyze_market(self, symbol): return {'trend': 'NEUTRAL', 'vwap': None, 'current_price': None}

current_bar = None 

# --- Mock Classes for Backtesting (Unchanged core logic) ---

class MockTradeManager:
    """Simulates the TradeManager for backtesting, including basic PnL calculation."""
    def __init__(self, tp_points: float, sl_points: float): 
        self.trades = []
        self.open_positions = [] 
        self.tp_price_diff = tp_points  
        self.sl_price_diff = sl_points  
        self.closed_trades_count = 0
    
    def place_order(self, symbol: str, side: str, volume: float, comment: str, magic: int):
        global current_bar
        if any(p['magic'] == magic for p in self.open_positions): return
        if current_bar is not None:
             position = {'symbol': symbol, 'type': 1 if side == 'buy' else 0, 'volume': volume, 'comment': comment, 'magic': magic, 'entry_price': current_bar.close, 'entry_time': current_bar.name}
             self.open_positions.append(position)
             self.trades.append(f"Entry: {side.upper()} @ {current_bar.name} at {current_bar.close:.5f} (Magic: {magic})") 

    def check_for_close(self, current_price: float, symbol: str):
        closed_positions = []
        for pos in self.open_positions:
            if pos['symbol'] != symbol: continue
            if pos['type'] == 1: pnl_price_diff = current_price - pos['entry_price']
            else: pnl_price_diff = pos['entry_price'] - current_price
            
            if pnl_price_diff >= self.tp_price_diff:
                self.trades.append(f"Close: TP hit at {current_bar.name} (Entry: {pos['entry_price']:.5f}, Close: {current_price:.5f}) - PROFIT")
                self.closed_trades_count += 1
                closed_positions.append(pos)
                continue
            
            if pnl_price_diff <= self.sl_price_diff:
                self.trades.append(f"Close: SL hit at {current_bar.name} (Entry: {pos['entry_price']:.5f}, Close: {current_price:.5f}) - LOSS")
                self.closed_trades_count += 1
                closed_positions.append(pos)
                continue
        for pos in closed_positions: self.open_positions.remove(pos)

class MockSymbolData:
    """Mocks the SymbolData class to return only the data slices needed and calculate indicators."""
    def __init__(self, df: pd.DataFrame): 
        self.data_df = df
        self.current_idx = 0 
    
    def get_ohlc_bars(self, symbol: str, timeframe: int, count: int) -> pd.DataFrame:
        if self.current_idx < 0: return pd.DataFrame()
        start_idx = max(0, self.current_idx - count + 1)
        end_idx = self.current_idx + 1 
        df_slice = self.data_df.iloc[start_idx:end_idx].copy()
        required_cols = ['open', 'high', 'low', 'close', 'tick_volume']
        if all(col in df_slice.columns for col in required_cols): return df_slice[required_cols]
        return pd.DataFrame()

    def calculate_vwap(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        if 'tick_volume' not in df.columns or len(df) == 0 or df['tick_volume'].sum() == 0: return None
        df['TypicalPrice'] = (df['high'] + df['low'] + df['close']) / 3
        df['TPV'] = df['TypicalPrice'] * df['tick_volume']
        df['CumTPV'] = df['TPV'].cumsum()
        df['CumVolume'] = df['tick_volume'].cumsum()
        vwap = df['CumTPV'] / df['CumVolume'].replace(0, np.nan) 
        return vwap.to_numpy()

    def calculate_support_resistance(self, df: pd.DataFrame) -> Dict[str, float]:
        LOOKBACK_PERIOD = 50
        if len(df) < LOOKBACK_PERIOD: 
             return {"support": df['low'].min() if not df.empty else 0.0, 
                     "resistance": df['high'].max() if not df.empty else 0.0}
        recent_data = df.tail(LOOKBACK_PERIOD)
        return {"support": recent_data['low'].min(), "resistance": recent_data['high'].max()}


class Backtester:
    """Core class for simulating strategy execution."""
    
    def __init__(self, file_path: str, strategies: List[Type], tp_points: float, sl_points: float):
        self.tp_points = tp_points
        self.sl_points = sl_points
        
        self.trade_manager = MockTradeManager(tp_points, sl_points) 
        
        self.data = self._load_and_clean_data(file_path) # Load data first
        self.symbol_data = MockSymbolData(self.data) 
        
        # Use GlobalVwapWatch as imported or the Mock version if import failed
        if 'GlobalVwapWatch' in globals() and GlobalVwapWatch.__name__ != 'GlobalVwapWatch':
            self.market_watch = GlobalVwapWatch(symbol_data=self.symbol_data)
        else:
            self.market_watch = GlobalVwapWatch(symbol_data=self.symbol_data) # Use the fallback mock
            
        self.strategies = [s(self.trade_manager, self.symbol_data) for s in strategies]
        
    def _load_and_clean_data(self, file_path: str) -> pd.DataFrame:
        """
        Loads pre-cleaned CSV data directly, assuming a standard format: 
        Index = 'time' (datetime), Columns = 'open', 'high', 'low', 'close', 'tick_volume'.
        """
        print(f"\n--- Starting Data Load from Cleaned File: {file_path} ---")
        try:
            # Load the data, expecting the 'time' column to be the index and datetime formatted
            df = pd.read_csv(
                file_path, 
                index_col='time', 
                parse_dates=True
            )
            
        except FileNotFoundError:
            print(f"❌ ERROR: Cleaned data file not found at '{file_path}'. Check filename.")
            return pd.DataFrame()
        except Exception as e:
            print(f"❌ Error loading cleaned CSV file: {e}")
            return pd.DataFrame()

        # Final check for required columns
        required_cols = ['open', 'high', 'low', 'close', 'tick_volume']
        if not all(col in df.columns for col in required_cols):
             print(f"❌ Error: Cleaned DataFrame missing required OHLCV columns: {set(required_cols) - set(df.columns)}")
             return pd.DataFrame()

        # Ensure correct column subset and types
        df = df[required_cols].copy()
        try:
             df = df.astype(float)
        except:
             print("Warning: Could not cast OHLCV columns to float. Proceeding with existing types.")
        
        print(f"Data loaded successfully. Total bars: {len(df)}")
        return df


    def _run_trade_cycle(self, symbol: str, current_bar_data: pd.Series):
        """Processes one bar of data through the market watch and strategies."""
        global current_bar 
        current_bar = current_bar_data 
        
        # 1. PnL Check/Close
        current_price = current_bar.close 
        self.trade_manager.check_for_close(current_price, symbol)
        
        # 2. Indicator Calculation (uses self.symbol_data.current_idx = i - 1)
        market_state = self.market_watch.analyze_market(symbol)
        
        # 3. Strategy Check/Entry
        # Advance the index temporarily so strategies can see the full *current* bar (Bar i)
        self.symbol_data.current_idx += 1 

        all_positions = self.trade_manager.open_positions
        positions_for_symbol = tuple(p for p in all_positions if p['symbol'] == symbol)

        for strategy in self.strategies:
            signal = strategy.check_for_entry(symbol, market_state, positions_for_symbol)
            
            if signal in ['buy', 'sell']:
                magic_number = getattr(strategy, 'STRATEGY_MAGIC', STRATEGY_MAGIC)
                self.trade_manager.place_order(symbol=symbol, side=signal, volume=DEFAULT_VOLUME, 
                                               comment=f"{strategy.__class__.__name__}_{signal.upper()}", 
                                               magic=magic_number)
                break 

        # CRITICAL: Revert the index back for the next iteration's indicator calculation
        self.symbol_data.current_idx -= 1
        


    def run_backtest(self, symbol: str = "BTCUSD"):
        """Iterates through the data, simulating the trading environment bar by bar."""
        print(f"\nStarting backtest for {symbol}...")
        
        if self.data.empty:
            print("Backtest data is empty. Cannot run backtest.")
            return

        # Start past the minimum required bars for indicator calculation
        start_index = MARKET_WATCH_BAR_COUNT 

        for i in range(start_index, len(self.data)):
            
            # Set index for indicator calculation on the NEXT line (Bar i-1)
            self.symbol_data.current_idx = i - 1 
            
            current_bar_data = self.data.iloc[i]
            current_bar_data.name = current_bar_data.name.to_pydatetime() 
            
            self._run_trade_cycle(symbol, current_bar_data)
            
        # Final Report
        t = self.trade_manager.closed_trades_count
        print("\n" + "="*50); print("📊 BACKTEST RESULTS SUMMARY 📊"); print("="*50)
        print(f"Total Trades Closed: **{t}**")
        print(f"Final Open Positions: {len(self.trade_manager.open_positions)}")
        print("Detailed trade log (Entries/Exits):")
        for trade_log in self.trade_manager.trades:
             print(f"- {trade_log}")
        print("="*50)


if __name__ == '__main__':
    
    # Use a safe mock wrapper for strategy logic
    class VwapTrendContinuationWrapper: 
        STRATEGY_MAGIC = STRATEGY_MAGIC 
        def __init__(self, trade_manager, symbol_data):
            self.trade_manager = trade_manager
            self.symbol_data = symbol_data
        def check_for_entry(self, symbol, market_state, open_positions):
            try:
                # Attempt to import the real strategy logic for execution
                from strategies.vwap_trend_continuation import VwapTrendContinuation as RealStrategy
                return RealStrategy(self.trade_manager, self.symbol_data).check_for_entry(symbol, market_state, open_positions)
            except ImportError:
                 return None # Fail gracefully if real strategy is not found

    STRATEGIES_TO_TEST = [
        VwapTrendContinuationWrapper, # Your fixed, signals-generating strategy
    ]
    
    # 🎯 IMPORTANT: Expecting the cleaned CSV file
    file_path = 'BTCUSDM15_CLEANED.csv' 
    
    try:
        # Realistic Scalping Parameters for BTCUSD
        TP_POINTS_FOR_SCALPING = 1.5    # $1.50 price change to hit TP
        SL_POINTS = -10.0             # -$10.00 price change to hit SL
        
        tester = Backtester(file_path, STRATEGIES_TO_TEST, 
                            tp_points=TP_POINTS_FOR_SCALPING, 
                            sl_points=SL_POINTS)
        tester.run_backtest(symbol="BTCUSD") 
        
        # --- EXPORT TRADE LOG TO CSV FOR ANALYSIS ---
        if tester.trade_manager.trades:
            log_file = 'trade_log.csv'
            
            # Simple Text Export
            with open(log_file, 'w', newline='') as f:
                 f.write("Trade_Log_Entry\n")
                 for trade_log in tester.trade_manager.trades:
                     f.write(f'"{trade_log}"\n')
            print(f"\nTrade log saved to {log_file} for detailed analysis.")
        # --------------------------------------------
        
    except Exception as e:
        print(f"An error occurred during backtesting: {e}")
        print("Ensure the file path is correct and all dependencies are correctly initialized.")