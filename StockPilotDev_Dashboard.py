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

# --- CSV UPLOAD FEATURE ---

st.subheader("Upload Client Sales Data (CSV)")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    try:
        # Read the CSV file into a pandas DataFrame
        client_data_df = pd.read_csv(uploaded_file)
        st.success("File uploaded successfully!")
        st.write("Preview of the uploaded data:")
        st.dataframe(client_data_df.head())

        # Here is where you will add your analysis logic later:
        # analyze_data_and_generate_alerts(client_data_df)

    except Exception as e:
        st.error(f"An error occurred during file processing: {e}")

# --- DISPLAY ALERTS ---

# Call the database creation function first
create_database()

# Fetch data and display it
alert_data = get_reorder_alerts()

if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    st.subheader("Recent Alerts")
    st.dataframe(alert_data) # Displays the data nicely in a table format