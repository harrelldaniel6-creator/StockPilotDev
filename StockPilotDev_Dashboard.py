import streamlit as st
import pandas as pd
import sqlite3
import os


# --- FUNCTION DEFINITIONS ---

def get_reorder_alerts():
    """Fetches reorder alerts data from the database."""
    conn = sqlite3.connect('stockpilot.db')
    query = "SELECT * FROM reorder_alerts ORDER BY alert_date DESC"
    alert_data = pd.read_sql_query(query, conn)
    conn.close()
    return alert_data


def create_database():
    """Creates the database and necessary tables if they don't exist."""
    conn = sqlite3.connect('stockpilot.db')
    cursor = conn.cursor()
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
    Analyzes sales data, calculates alerts for items with < 7 days stock remaining,
    and inserts them into the database.
    """
    conn = sqlite3.connect('stockpilot.db')
    cursor = conn.cursor()

    # Clear existing alerts before adding new ones
    cursor.execute("DELETE FROM reorder_alerts")
    conn.commit()

    # --- INVENTORY ANALYSIS LOGIC ---

    # 1. Ensure 'Order Date' is a datetime object
    sales_data_df['Order Date'] = pd.to_datetime(sales_data_df['Order Date'])

    # 2. Calculate average daily sales (ADS) for each item type
    total_sales_per_item = sales_data_df.groupby('Item Type')['Units Sold'].sum()
    days_covered = (sales_data_df['Order Date'].max() - sales_data_df['Order Date'].min()).days + 1
    avg_daily_sales = total_sales_per_item / days_covered

    # 3. Determine alerts based on 7-day threshold (using dummy current stock of 10)
    reorder_threshold_days = 7
    required_stock = avg_daily_sales * reorder_threshold_days
    potential_alerts = required_stock[required_stock > 10].index.tolist()

    # 4. Create alerts_df DataFrame with the required columns
    alerts_list = []
    current_date = pd.Timestamp.today().strftime('%Y-%m-%d')
    for item_type in potential_alerts:
        alerts_list.append({'alert_date': current_date, 'product_name': item_type})

    alerts_df = pd.DataFrame(alerts_list)

    # --- END ANALYSIS LOGIC ---

    # Insert the new alerts into the database
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
    st.dataframe(alert_data) # Displays the data nicely in a table format