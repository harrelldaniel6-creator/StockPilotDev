import streamlit as st
import sqlite3
import pandas as pd

def create_database():
    """Creates the database and necessary tables if they don't exist."""
    conn = sqlite3.connect('stockpilot.db')
    cursor = conn.cursor()
    Create the reorder_alerts table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reorder_alerts (
            id INTEGER PRIMARY KEY,
            alert_date TEXT,
            product_name TEXT,
        )
    ''')
    conn.commit()
    conn.close()

# Fetch data and display it
create_database() # <-- Add this line
alert_data = get_reorder_alerts()

def get_reorder_alerts():
    """Fetches all alerts from the database."""
    conn = sqlite3.connect('stockpilot.db') # Connect to your existing DB
    query = "SELECT * FROM reorder_alerts ORDER BY alert_date DESC"
    df = pd.read_sql_query(query, conn) # Use pandas to read SQL data into a DataFrame
    conn.close()
    return df

st.title("StockPilot Re-Order Alerts Dashboard")

# Fetch data and display it
alert_data = get_reorder_alerts()

if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    st.subheader("Recent Alerts")
    st.dataframe(alert_data) # Displays the data nicely in a table format

def get_reorder_alerts():
    """Fetches all alerts from the database."""
    conn = sqlite3.connect('stockpilot.db') # Connect to your existing DB
    query = "SELECT * FROM reorder_alerts ORDER BY alert_date DESC"
    df = pd.read_sql_query(query, conn) # Use pandas to read SQL data into a DataFrame
    conn.close()
    return df

st.title("StockPilot Re-Order Alerts Dashboard")

# Fetch data and display it
alert_data = get_reorder_alerts()

if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    st.subheader("Recent Alerts")
    st.dataframe(alert_data) # Displays the data nicely in a table format

