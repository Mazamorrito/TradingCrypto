# data_formatter.py

import pandas as pd
import numpy as np

def clean_mt5_data(input_path: str, output_path: str) -> None:
    """
    Loads malformed MT5 export data, cleans and formats columns, 
    and saves the result to a new CSV.

    NOTE: The MT5 export is missing the day (DD) component. This script 
    artificially sets the day to '01' to allow backtesting software to run,
    but the resulting data will only reflect the 1st of each month.
    """
    try:
        # Load the tab-delimited data
        df = pd.read_csv(input_path, delimiter='\t')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # 1. Rename columns to standard backtesting names
    df.rename(columns={
        '<DATE>': 'date_raw',
        '<TIME>': 'time_of_day',
        '<OPEN>': 'open',
        '<HIGH>': 'high',
        '<LOW>': 'low',
        '<CLOSE>': 'close',
        '<TICKVOL>': 'tick_volume'
    }, inplace=True)

    # 2. Extract YYYY.MM and combine with time_of_day, forcing day to '01'
    def combine_and_force_day(row):
        date_part = str(row['date_raw'])
        time_part = str(row['time_of_day'])
        
        # Use string splitting, which is robust for the format 'ID.YYYY.MM'
        parts = date_part.split('.')
        
        if len(parts) >= 3:
             # Take YYYY (parts[1]) and MM (parts[2])
             year_month = f"{parts[1]}.{parts[2]}"
             # Force day '01'
             date_str_forced = year_month + '.01' 
             return date_str_forced + ' ' + time_part
        return np.nan

    df['datetime_str'] = df.apply(combine_and_force_day, axis=1)

    # 3. Parse the combined string into a datetime object (Format: YYYY.MM.DD HH:MM:SS)
    df['time'] = pd.to_datetime(df['datetime_str'], format='%Y.%m.%d %H:%M:%S', errors='coerce')

    # 4. Clean up and select final columns
    df.dropna(subset=['time'], inplace=True)
    df.set_index('time', inplace=True)
    
    # Final desired columns for a backtest CSV (excluding the raw columns)
    df_cleaned = df[['open', 'high', 'low', 'close', 'tick_volume']].copy()

    # 5. Save the cleaned DataFrame
    df_cleaned.to_csv(output_path)
    print(f"Cleaned data saved to {output_path}")

if __name__ == '__main__':
    # You would run this with your file name
    clean_mt5_data('BTCUSDM15.csv', 'BTCUSDM15_CLEANED.csv')