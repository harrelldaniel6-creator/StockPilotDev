import pandas as pd
import sqlite3
import os


def generate_stock_analysis_report():
    print("--- Starting Stock Analysis Report Generation ---")

    # Connect to the database
    conn = sqlite3.connect('stockpilot.db')
    df = pd.read_sql_query("SELECT * FROM stock_data", conn)
    conn.close()

    if df.empty:
        print("Error: Database is empty. Please run fetch_data.py first.")
        return

    # Ensure date column is datetime for analysis
    df['trade_date'] = pd.to_datetime(df['trade_date'])

    # Get unique symbols
    symbols = df['symbol'].unique()

    report_data = []

    for symbol in symbols:
        # Filter data for the specific symbol
        symbol_df = df[df['symbol'] == symbol].copy()

        # Sort by date (important for rolling/pct_change)
        symbol_df.sort_values('trade_date', inplace=True)

        # Calculate daily returns
        symbol_df['daily_return'] = symbol_df['adjusted_close'].pct_change() * 100

        # Calculate 7-day rolling average of returns
        symbol_df['rolling_avg_return'] = symbol_df['daily_return'].rolling(window=7).mean()

        # Calculate volatility (standard deviation of daily returns)
        volatility = symbol_df['daily_return'].std()

        # Get recent performance metrics
        latest_close = symbol_df['adjusted_close'].iloc[-1]
        avg_daily_return = symbol_df['daily_return'].mean()

        report_data.append({
            'Symbol': symbol,
            'Latest Close': f"${latest_close:.2f}",
            'Avg Daily Return (%)': f"{avg_daily_return:.3f}%",
            'Volatility (Std Dev) (%)': f"{volatility:.3f}%",
            'Data Points': len(symbol_df)
        })

    # Print a nicely formatted summary using pandas
    report_df = pd.DataFrame(report_data)
    print("\n")
    print(report_df.to_markdown(index=False))
    print("\n--- Report Generation Complete ---")


if __name__ == "__main__":
    generate_stock_analysis_report()