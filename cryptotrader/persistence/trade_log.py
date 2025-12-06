# persistence/trade_log.py

import csv
from datetime import datetime
import MetaTrader5 as mt5
class TradeLog:
    """
    Handles logging of trade requests, execution results, and PnL actions.
    """
    
    def __init__(self, filename="trades.csv"):
        self.filename = filename
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Creates the CSV file with headers if it doesn't exist."""
        try:
            with open(self.filename, 'r', newline='') as f:
                # Check if file has content (i.e., headers)
                if not f.read(1):
                    raise FileNotFoundError
        except FileNotFoundError:
            with open(self.filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Action", "Ticket", "Symbol", "Side", 
                    "Volume", "Price", "SL", "TP", "Comment", "Status", "Details"
                ])
                
    def _log(self, action, ticket, symbol, side, volume, price, sl, tp, comment, status, details=""):
        """Internal method to write a record to the CSV."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, action, ticket, symbol, side, 
                volume, price, sl, tp, comment, status, details
            ])

    def log_trade_placement(self, result, symbol, side, volume, price, sl, tp, comment):
        """Logs the result of an mt5.order_send attempt."""
        ticket = result.order if result and result.order != 0 else "N/A"
        status = "SUCCESS" if result and result.retcode == 10009 else "FAILURE"
        details = str(result)
        
        self._log(
            "PLACE", ticket, symbol, side, volume, price, sl, tp, 
            comment, status, details
        )

    def log_position_close(self, position_info, result, reason):
        """Logs the closing of an existing position."""
        ticket = position_info.ticket
        symbol = position_info.symbol
        side = "BUY" if position_info.type == mt5.ORDER_TYPE_BUY else "SELL"
        volume = position_info.volume
        
        status = "CLOSED" if result and result.retcode == 10009 else "CLOSE_FAIL"
        details = f"Reason: {reason}. Result: {str(result)}"
        
        self._log(
            "CLOSE", ticket, symbol, side, volume, position_info.price_current, 
            0.0, 0.0, reason, status, details
        )