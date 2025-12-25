from database_setup import get_db_connection
import yfinance as yf
import pandas as pd
from datetime import datetime

# Define the global stock symbols we are fetching as a list
SYMBOLS = ['IBM', 'MSFT', 'AAPL']


def clear_existing_data():
    """
    Clears the stock data table before appending new data.
    """
    Get the connection using our centralized function
    conn = get_db_connection()
    cursor = conn.cursor()

    # NOTE: Ensure 'stock data' is the correct table name
    cursor.execute("DELETE FROM 'stock data'")
    conn.commit()
    conn.close() # Best practice: close connection when done
    print("Existing database data cleared.")


def fetch_and_store_data(symbol):
    """
    Fetches stock data for a symbol and stores it. (You will need to implement the rest of this function)
    """
    # Example usage inside this function:
    conn = get_db_connection()
    cursor = conn.cursor()
    # ... your logic here ...
    pass