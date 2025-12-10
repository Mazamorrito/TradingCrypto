import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import strategy files (assumes they are available in the running environment)
from strategies.vwap_trend_continuation import VwapTrendContinuation, STRATEGY_MAGIC
from strategies.vwap_snr_confirmation import VwapSnrConfirmation
from market_watch.global_vwap_watch import GlobalVwapWatch
from config.settings import DEFAULT_VOLUME, MARKET_WATCH_BAR_COUNT

# Global variable to pass current bar data simply (used by MockTradeManager)
current_bar = None 

# --- Mock Classes for Backtesting ---
class MockTradeManager:
    def __init__(self): self.trades, self.open_positions = [], []
    def place_order(self, symbol: str, side: str, volume: float, comment: str):
        global current_bar
        if not self.open_positions and current_bar is not None:
             self.open_positions.append({'symbol': symbol, 'type': 1 if side == 'buy' else 0, 'volume': volume, 'comment': comment, 'magic': STRATEGY_MAGIC, 'entry_price': current_bar.close, 'entry_time': current_bar.name})
             self.trades.append(f"Entry: {side.upper()} @ {current_bar.name} at {current_bar.close:.4f}")
    def close_position(self, pos, reason: str):
        if pos in self.open_positions: self.open_positions.remove(pos)

class MockSymbolData:
    def __init__(self, df: pd.DataFrame): self.data_df, self.current_idx = df, 0
    def get_ohlc_bars(self, symbol: str, timeframe: int, count: int) -> pd.DataFrame:
        start_idx = max(0, self.current_idx - count + 1); end_idx = self.current_idx + 1
        if end_idx < 3: return pd.DataFrame()
        df_slice = self.data_df.iloc[start_idx:end_idx].copy()
        # The base DataFrame now has 'tick_volume' due to the fix in _load_data
        return df_slice[['open', 'high', 'low', 'close', 'tick_volume']]
    def calculate_vwap(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        if 'tick_volume' not in df.columns or len(df) == 0: return None
        df['TypicalPrice'] = (df['high'] + df['low'] + df['close']) / 3
        df['TPV'] = df['TypicalPrice'] * df['tick_volume']
        df['CumTPV'] = df['TPV'].cumsum()
        df['CumVolume'] = df['tick_volume'].cumsum()
        return (df['CumTPV'] / df['CumVolume']).to_numpy()
    def calculate_support_resistance(self, df: pd.DataFrame) -> Dict[str, float]:
        if len(df) < 5: return {"support": 0.0, "resistance": 0.0}
        return {"support": df['low'].tail(20).min(), "resistance": df['high'].tail(20).max()}

# --- Backtester Core ---
class Backtester:
    # 💥 CHANGE 1: Accept a list of strategy classes
    def __init__(self, data_file_path: str, strategy_classes: List[Type], tp_points: float = 100.0, sl_points: float = -50.0):
        self.data_file_path, self.tp, self.sl = data_file_path, tp_points / 10000, sl_points / 10000
        self.results: List[Dict[str, Any]] = []
        self.df = self._load_data()
        self.symbol_data = MockSymbolData(self.df)
        self.trade_manager = MockTradeManager()
        self.vwap_watch = GlobalVwapWatch(self.symbol_data)
        
        # 💥 CHANGE 2: Instantiate all strategies
        self.strategies = [StrategyClass(self.trade_manager, self.symbol_data) for StrategyClass in strategy_classes]
        
    def _load_data(self) -> pd.DataFrame:
        df = pd.read_csv(self.data_file_path, sep='\t', header=None, names=['DATE', 'TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'TICKVOL', 'VOL', 'SPREAD'], skiprows=1)
        df['DATE'] = df['DATE'].astype(str).str.split('.').str[-2:].str.join('.')
        df.set_index(pd.to_datetime(df['DATE'] + ' ' + df['TIME'], format='%Y.%m %H:%M:%S'), inplace=True)
        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={'tickvol': 'tick_volume'}, inplace=True) 
        return df[['open', 'high', 'low', 'close', 'tick_volume', 'vol', 'spread']]
        
    def _run_pnl_check(self, current_bar: pd.Series):
        positions_to_close = []
        # Check PnL for ALL open positions
        for pos in self.trade_manager.open_positions.copy():
            entry_price, is_buy = pos['entry_price'], pos['type'] == 1
            if is_buy and current_bar.high >= entry_price + self.tp:
                self.results.append({'result': 'SUCCESS', 'time': current_bar.name, 'reason': 'TP Hit'}); positions_to_close.append(pos)
            elif not is_buy and current_bar.low <= entry_price - self.tp:
                self.results.append({'result': 'SUCCESS', 'time': current_bar.name, 'reason': 'TP Hit'}); positions_to_close.append(pos)
            elif is_buy and current_bar.low <= entry_price + self.sl:
                self.results.append({'result': 'FAILURE', 'time': current_bar.name, 'reason': 'SL Hit'}); positions_to_close.append(pos)
            elif not is_buy and current_bar.high >= entry_price - self.sl:
                self.results.append({'result': 'FAILURE', 'time': current_bar.name, 'reason': 'SL Hit'}); positions_to_close.append(pos)
        for pos in positions_to_close: self.trade_manager.close_position(pos, 'PnL_Triggered')

    def run_backtest(self, symbol: str = "BACKTEST_SYMBOL"):
        if self.df.empty: return print("❌ Error: Data not loaded or DataFrame is empty.")
        print(f"--- Starting Backtest on {len(self.df)} bars with {len(self.strategies)} strategies ---")
        
        for idx in range(MARKET_WATCH_BAR_COUNT + 1, len(self.df)):
            self.symbol_data.current_idx = idx
            global current_bar
            current_bar = self.df.iloc[idx]
            
            # 1. PnL Check
            if self.trade_manager.open_positions: self._run_pnl_check(current_bar)

            # 2. Market Watch Analysis (Run once per bar)
            market_state = self.vwap_watch.analyze_market(symbol)
            
            # 💥 CHANGE 3: Loop through all strategies for entry check
            current_open_positions = tuple(self.trade_manager.open_positions)
            
            for strategy in self.strategies:
                # IMPORTANT: Strategies are responsible for checking their own magic number
                signal = strategy.check_for_entry(symbol, market_state, current_open_positions) 
                
                if signal in ["buy", "sell"]:
                    # The strategy object holds its unique STRATEGY_MAGIC
                    # We pass the required magic number for the MockTradeManager to enforce the single-trade-per-strategy rule.
                    magic_number = getattr(strategy, 'STRATEGY_MAGIC', STRATEGY_MAGIC)
                    self.trade_manager.place_order(symbol=symbol, side=signal, volume=DEFAULT_VOLUME, comment=f"{strategy.__class__.__name__}_{signal.upper()}", magic=magic_number)

        # Final Report
        s, f, t = [r for r in self.results if r['result'] == 'SUCCESS'], [r for r in self.results if r['result'] == 'FAILURE'], len(self.results)
        print("\n" + "="*50); print("📊 BACKTEST RESULTS SUMMARY 📊"); print("="*50)
        print(f"Total Trades Closed: **{t}** | Successes: **{len(s)}** | Failures: **{len(f)}**")
        if t > 0: print(f"Success Rate: **{(len(s) / t) * 100:.2f}%**")
        else: print("No trades closed.")
        print("Final Open Positions:", len(self.trade_manager.open_positions))
        print("="*50)

if __name__ == '__main__':
    STRATEGIES_TO_TEST = [
        VwapTrendContinuation,
        VwapSnrConfirmation,
        # YourSecondStrategy,
        # YourThirdStrategy,
    ]
    file_path = 'BTCUSDM15.csv' 
    try:
        tester = Backtester(file_path, tp_points=100.0, sl_points=-50.0)
        tester.run_backtest()
    except Exception as e:
        print(f"An error occurred during backtesting: {e}")
        print("Ensure the file path is correct and the dependencies (like pandas) are installed.")