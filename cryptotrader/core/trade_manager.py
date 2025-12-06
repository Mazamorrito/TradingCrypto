# core/trade_manager.py

import MetaTrader5 as mt5
from persistence.trade_log import TradeLog
from config.settings import MT5_MAGIC_NUMBER, DEFAULT_DEVIATION, DEFAULT_VOLUME

class TradeManager:
    """Centralized trade placement logic."""
    
    def __init__(self, logger: TradeLog, deviation=DEFAULT_DEVIATION, magic=MT5_MAGIC_NUMBER):
        self.logger = logger
        self.deviation = deviation
        self.magic = magic
        # NOTE: SL and TP are handled by PnLManager, so we enforce 0.0 for MT5
        self.sl = 0.0 
        self.tp = 0.0

    def place_order(self, symbol: str, side: str, volume: float, comment: str,magic: int = None):
        """
        Places a market order with SL/TP set to 0.0 (handled externally by PnLManager).
        
        :param symbol: Trading symbol (e.g., "EURUSD")
        :param side: "buy" or "sell"
        :param volume: Lot size
        :param comment: Strategy or trade identifier
        :return: Order ticket number on success, None on failure
        """
        if not mt5.symbol_select(symbol, True):
            print(f"❌ Failed to select symbol {symbol}")
            return None
            
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print(f"❌ Failed to get tick info for {symbol}")
            return None

        # Determine the execution price and trade type
        if side.lower() == "buy":
            price = tick.ask
            order_type = mt5.ORDER_TYPE_BUY
            action = mt5.TRADE_ACTION_DEAL
        elif side.lower() == "sell":
            price = tick.bid
            order_type = mt5.ORDER_TYPE_SELL
            action = mt5.TRADE_ACTION_DEAL
        else:
            print(f"Invalid side: {side}")
            return None

        # --- MT5 Request Dictionary ---
        request = {
            "action": action,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": self.sl, 
            "tp": self.tp, # Enforcing 0.0 as per design
            "deviation": self.deviation,
            "magic": magic,
            "comment": comment,
            "type_filling": mt5.ORDER_FILLING_IOC, # Immediate-or-Cancel
        }
        
        # Send the order
        result = mt5.order_send(request)
        
        # Log the result
        self.logger.log_trade_placement(result, symbol, side, volume, price, self.sl, self.tp, comment)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            ticket = result.order
            print(f"✅ {side.upper()} order placed for {symbol} at {price}. Ticket: {ticket}")
            return ticket
        else:
            error_code = result.retcode if result else "N/A"
            error_desc = mt5.last_error()
            print(f"❌ Order failed ({error_code}): {error_desc}")
            return None
            
    def close_position(self, position_info, reason: str):
        """
        Sends a market request to close a specific position.
        """
        ticket = position_info.ticket
        symbol = position_info.symbol
        volume = position_info.volume
        
        if position_info.type == mt5.ORDER_TYPE_BUY:
            trade_type = mt5.ORDER_TYPE_SELL
            close_price = mt5.symbol_info_tick(symbol).bid
        elif position_info.type == mt5.ORDER_TYPE_SELL:
            trade_type = mt5.ORDER_TYPE_BUY
            close_price = mt5.symbol_info_tick(symbol).ask
        else:
            print(f"Error: Unknown position type {position_info.type} for ticket {ticket}")
            return None

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": trade_type,
            "position": ticket,
            "price": close_price,
            "deviation": self.deviation, 
            "magic": self.magic, 
            "comment": f"Auto-Close: {reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        self.logger.log_position_close(position_info, result, reason)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"  [Close] ✅ Position {ticket} closed successfully. Reason: {reason}")
        else:
            print(f"  [Close] ❌ Failed to close position {ticket}. Error: {mt5.last_error()}")
            
        return result