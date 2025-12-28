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


def analyze_data_and_generate_alerts(sales_data_df, current_stock_levels):
    """
    Analyzes sales data, calculates alerts for items with < 7 days stock remaining,
    using actual current stock levels, and inserts them into the database.
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

    # 3. Determine alerts based on 7-day threshold using provided current stock levels
    reorder_threshold_days = 7
    required_stock_for_period = avg_daily_sales * reorder_threshold_days

    alerts_list = []
    current_date = pd.Timestamp.today().strftime('%Y-%m-%d')

    for item_type, required_stock in required_stock_for_period.items():
        # Use the stock level provided in the form
        current_stock = current_stock_levels.get(item_type, 0)
        if current_stock < required_stock:
            alerts_list.append({'alert_date': current_date, 'product_name': item_type})

    alerts_df = pd.DataFrame(alerts_list)

    # --- END ANALYSIS LOGIC ---

    # Insert the new alerts into the database
    alerts_df.to_sql('reorder_alerts', conn, if_exists='append', index=False)

    conn.close()
    st.success(f"Analysis complete. {len(alerts_df)} new alerts generated.")


# --- MAIN APPLICATION LOGIC ---

st.title("StockPilot Re-Order Alerts Dashboard")

# Call the database creation function FIRST so the table exists
create_database()

# --- CSV UPLOAD FEATURE AND STOCK FORM ---

st.subheader("Upload Client Sales Data (CSV)")
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    try:
        client_data_df = pd.read_csv(uploaded_file)

        # Display the form for stock levels
        st.subheader("Enter Current Stock Levels")
        with st.form("stock_level_form"):
            # Identify unique products from the uploaded file
            unique_products = client_data_df['Item Type'].unique()
            stock_inputs = {}
            for product in unique_products:
                stock_inputs[product] = st.number_input(f"Stock for '{product}'", min_value=0, value=0, step=1)

            submitted = st.form_submit_button("Run Analysis and Generate Alerts")

            if submitted:
                st.success("File uploaded successfully! Starting analysis...")
                # Call the analysis function with the stock inputs
                analyze_data_and_generate_alerts(client_data_df, stock_inputs)

    except Exception as e:
        st.error(f"An error occurred during file processing: {e}")

# --- DISPLAY ALERTS ---

# Fetch data and display it
alert_data = get_reorder_alerts()

if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    st.subheader("Recent Alerts")
    st.dataframe(alert_data)  # Displays the data nicely in a table format