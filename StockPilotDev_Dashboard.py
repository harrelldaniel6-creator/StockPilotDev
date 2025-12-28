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
                   CREATE TABLE IF NOT EXISTS reorder_alerts
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY,
                       alert_date
                       TEXT,
                       product_name
                       TEXT
                   )
                   ''')
    conn.commit()
    conn.close()


def analyze_data_and_generate_alerts(sales_data_df):
    """
    Analyzes sales data, calculates alerts, and inserts them into the database.
    """
    conn = sqlite3.connect('stockpilot.db')
    cursor = conn.cursor()

    # Clear existing alerts before adding new ones to avoid duplicates
    cursor.execute("DELETE FROM reorder_alerts")
    conn.commit()

    # --- YOUR ANALYSIS LOGIC GOES HERE ---
    # Example: You would analyze 'sales_data_df' here to determine reorder points.
    # The output should be a new DataFrame with 'alert_date' and 'product_name' columns.

    # Placeholder logic: We'll assume your analysis results in a DataFrame called 'alerts_df'
    # alerts_df = perform_complex_analysis(sales_data_df)

    # For demonstration, let's create a dummy alert:
    alerts_df = pd.DataFrame({
        'alert_date': [pd.Timestamp.today().strftime('%Y-%m-%d')],
        'product_name': ['Sample Product Name that needs reordering']
    })

    # Insert the new alerts into the database
    # 'if_exists="append"' adds new rows without recreating the table
    alerts_df.to_sql('reorder_alerts', conn, if_exists='append', index=False)

    conn.close()
    st.success(f"Analysis complete. {len(alerts_df)} new alerts generated.")


# --- MAIN APPLICATION LOGIC ---

st.title("StockPilot Re-Order Alerts Dashboard")

# --- CSV UPLOAD FEATURE ---

st.subheader("Upload Client Sales Data (CSV)")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    try:
        # Read the CSV file into a pandas DataFrame
        client_data_df = pd.read_csv(uploaded_file)
        st.success("File uploaded successfully! Starting analysis...")

        # Call the analysis function
        analyze_data_and_generate_alerts(client_data_df)

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
    st.dataframe(alert_data)  # Displays the data nicely in a table format