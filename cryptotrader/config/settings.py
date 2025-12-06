# config/settings.py

import MetaTrader5 as mt5
# --- TRADING PARAMETERS ---
# Identifier for trades placed by this bot
MT5_MAGIC_NUMBER = 20240901 
# Slippage in points allowed for market orders
DEFAULT_DEVIATION = 20    
# Standard Volume/Lot Size
DEFAULT_VOLUME = 0.1     
# Timeframe for Market Watch analysis
MARKET_WATCH_TIMEFRAME = mt5.TIMEFRAME_M15 
# Number of bars to fetch for analysis
MARKET_WATCH_BAR_COUNT = 300 

# --- PNL MANAGEMENT (USD/Account Currency) ---
# Maximum positive profit before position is closed
TAKE_PROFIT_USD = 1.0   
# Maximum loss before position is closed
STOP_LOSS_USD = -10.0  
# Profit level at which the trailing stop feature becomes active
TRAILING_ACTIVATION_USD = 1.0 
# Profit distance to trail behind the peak profit once activated
TRAILING_STEP_USD = 0.20   
# Acceptable profit range for break-even close (USD, e.g., $0.50)
BREAKEVEN_THRESHOLD = 0.5

TRADING_SYMBOLS = [
    ## "EURUSD", 
    ## "GBPUSD", 
    ## "USDJPY", 
    ## "GOLD",
    ## "GBPJPY",
    "BTCUSD",
    "ETHUSD", 
]