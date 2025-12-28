<<<<<<< HEAD
import streamlit as st
import sqlite3
import pandas as pd

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
=======
import streamlit as st
import sqlite3
import pandas as pd

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
>>>>>>> 9fa752d5c80fb25887288b10a3f5bfdc90cc6f57
