import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime

# Define the global stock symbols we are fetching as a list
SYMBOLS = ['IBM', 'MSFT', 'AAPL']


def clear_existing_data(conn):
    """Clears the stock_data table before appending new data."""
    cursor = conn.cursor()
    # SQL command to delete all rows in the table
    cursor.execute("DELETE FROM stock_data")
    conn.commit()
    print("Existing database data cleared.")


def fetch_and_store_data(symbol):
    """Fetches stock data using yfinance and stores it in the database."""

    try:
        # Fetch historical data (yfinance automatically adjusts for splits/dividends)
        ticker = yf.Ticker(symbol)
        data_df = ticker.history(period="100d")

        if data_df.empty:
            print(f"Error: No data found for symbol {symbol}. Check the symbol name.")
            return

        # ... (Data processing logic remains the same) ...
        data_df.rename(columns={'Close': 'adjusted_close', 'Volume': 'volume'}, inplace=True)
        data_df = data_df[['adjusted_close', 'volume']]
        data_df['symbol'] = symbol
        data_df.reset_index(inplace=True)
        data_df.rename(columns={'Date': 'trade_date'}, inplace=True)
        data_df['trade_date'] = pd.to_datetime(data_df['trade_date']).dt.date

        # Connect to SQLite database
        conn = sqlite3.connect('stockpilot.db')

        # We will clear the data only once before the loop starts in __main__

        # Use pandas .to_sql function to insert data into the table
        data_df.to_sql('stock_data', conn, if_exists='append', index=False)

        conn.commit()
        conn.close()
        print(f"Successfully fetched and stored data for {symbol}")

    except Exception as e:
        print(f"An error occurred for {symbol}: {e}")


if __name__ == "__main__":
    # Connect once to clear all data
    conn = sqlite3.connect('stockpilot.db')
    clear_existing_data(conn)
    conn.close()

    # Loop through all defined symbols and fetch new data for each one
    for stock_symbol in SYMBOLS:
        fetch_and_store_data(stock_symbol)
