import streamlit as st
import pandas as pd
import sqlite3
import os

# --- FUNCTION DEFINITIONS ---

def get_reorder_alerts():
    """Fetches reorder alerts data from the database."""
    conn = sqlite3.connect('stockpilot.db')
    # Use your actual SELECT query here:
    query = "SELECT * FROM reorder_alerts ORDER BY alert_date DESC"
    alert_data = pd.read_sql_query(query, conn)
    conn.close()
    return alert_data

def create_database():
    """Creates the database and necessary tables if they don't exist."""
    conn = sqlite3.connect('stockpilot.db')
    cursor = conn.cursor()
    # Create the reorder_alerts table if it doesn't exist. Add all your necessary columns here:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reorder_alerts (
            id INTEGER PRIMARY KEY,
            alert_date TEXT,
            product_name TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- MAIN APPLICATION LOGIC ---

st.title("StockPilot Re-Order Alerts Dashboard")

# Call the database creation function first
create_database()

# Fetch data and display it
alert_data = get_reorder_alerts()

if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    st.subheader("Recent Alerts")
    st.dataframe(alert_data) # Displays the data nicely in a table format