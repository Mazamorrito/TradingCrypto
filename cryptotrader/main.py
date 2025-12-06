# main.py

import MetaTrader5 as mt5
import time
from datetime import datetime
from typing import Tuple

# --- Import Core Components ---
from persistence.trade_log import TradeLog
from core.symbol_data import SymbolData
from core.trade_manager import TradeManager
from market_watch.global_vwap_watch import GlobalVwapWatch

from config.settings import TRADING_SYMBOLS

# --- Import Strategies ---
from strategies.RSI_HVT import RsiMeanReversion
from strategies.AdaptativeScalper import AdaptiveVolatilityScalper
# --- Main Logic ---
def main_loop(loop_interval=5):
    """
    The main execution loop that initializes the bot and coordinates all components 
    across all configured symbols.
    """
    
    if not TRADING_SYMBOLS:
        print("❌ ERROR: TRADING_SYMBOLS list in config/settings.py is empty. Cannot run.")
        return

    # 1. Initialize MT5 Connection
    if not mt5.initialize():
        print(f"❌ MT5 Initialization failed. Error: {mt5.last_error()}")
        return

    print("✅ MetaTrader5 connection established.")

    # 2. Initialize Managers and Utilities
    trade_logger = TradeLog()
    symbol_data = SymbolData()
    trade_manager = TradeManager(logger=trade_logger)
    market_watch = GlobalVwapWatch(symbol_data=symbol_data)
    
    # 3. Initialize Strategies (No symbols passed here, they are passed during execution)
    strategies = [
        RsiMeanReversion(trade_manager, symbol_data),
        AdaptiveVolatilityScalper(trade_manager, symbol_data)
    ]
    print(f"🤖 Initialized {len(strategies)} trading strategies for {len(TRADING_SYMBOLS)} symbols.")
    print("-" * 50)
    
    # 4. Core Execution Loop
    try:
        while True:
            start_time = time.time()
            print(f"\n--- Cycle Start: {datetime.now().strftime('%H:%M:%S')} ---")
            
            # A. Get ALL Current Open Positions globally once per cycle
            all_positions: Tuple[mt5.TradePosition] = mt5.positions_get()
            if all_positions is None:
                all_positions = tuple()
            
            # C. Iterate through ALL Configured Symbols
            for symbol in TRADING_SYMBOLS:
                
                print(f"\n--- Processing {symbol} ---")
                
                # 1. Global Market Analysis for the current symbol
                market_state = market_watch.analyze_market(symbol)
                
                # Print analysis only for active symbols
                if market_state.get('vwap') is not None:
                    print("♥")
                    market_watch.print_analysis(market_state)

                # 2. Filter positions relevant to the current symbol for strategy checks
                positions_for_symbol = tuple(p for p in all_positions if p.symbol == symbol)
                
                # 3. Strategy Execution
                for strategy in strategies:
                    # Pass the symbol, market state, and only relevant positions
                    strategy.check_for_entry(symbol, market_state, positions_for_symbol)
            
            # D. Control Loop Timing
            end_time = time.time()
            elapsed_time = end_time - start_time
            sleep_time = max(0, loop_interval - elapsed_time)
            
            print(f"\nCycle completed in {elapsed_time:.2f}s. Sleeping for {sleep_time:.2f}s.")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n👋 Position manager stopped by user.")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
    finally:
        mt5.shutdown()
        print("MetaTrader5 connection shut down.")


if __name__ == "__main__":
    # IMPORTANT: Ensure your MT5 terminal is running and you have data for the symbol
    main_loop(loop_interval=5)