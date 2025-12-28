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
    Returns a detailed DataFrame of the analysis.
    """
    conn = sqlite3.connect('stockpilot.db')
    cursor = conn.cursor()

    # Clear existing alerts before adding new ones
    cursor.execute("DELETE FROM reorder_alerts")
    conn.commit()

    # --- INVENTORY ANALYSIS LOGIC ---

    sales_data_df['Order Date'] = pd.to_datetime(sales_data_df['Order Date'])
    total_sales_per_item = sales_data_df.groupby('Item Type')['Units Sold'].sum()
    days_covered = (sales_data_df['Order Date'].max() - sales_data_df['Order Date'].min()).days + 1
    avg_daily_sales = (total_sales_per_item / days_covered).round(2)

    reorder_threshold_days = 7
    required_stock_for_period = (avg_daily_sales * reorder_threshold_days).round(2)

    alerts_list = []
    detailed_analysis_list = []
    current_date = pd.Timestamp.today().strftime('%Y-%m-%d')

    for item_type, required_stock in required_stock_for_period.items():
        current_stock = current_stock_levels.get(item_type, 0)

        detailed_analysis_list.append({
            'Product Name': item_type,
            'Avg Daily Sales': avg_daily_sales[item_type],
            f'Required Stock ({reorder_threshold_days} Days)': required_stock,
            'Current Stock Input': current_stock,
            'Reorder Needed': 'Yes' if current_stock < required_stock else 'No'
        })

        if current_stock < required_stock:
            alerts_list.append({'alert_date': current_date, 'product_name': item_type})

    alerts_df = pd.DataFrame(alerts_list)
    detailed_analysis_df = pd.DataFrame(detailed_analysis_list)

    # Insert the new alerts into the database
    alerts_df.to_sql('reorder_alerts', conn, if_exists='append', index=False)

    conn.close()
    st.success(f"Analysis complete. {len(alerts_df)} new alerts generated.")
    return detailed_analysis_df


# --- MAIN APPLICATION LOGIC ---

st.title("StockPilot Re-Order Alerts Dashboard")

create_database()

# --- SIDEBAR FOR UPLOAD AND INPUTS ---
with st.sidebar:
    st.subheader("Data Input & Analysis")
    uploaded_file = st.file_uploader("Upload Client Sales Data (CSV)", type="csv")

if uploaded_file is not None:
    try:
        client_data_df = pd.read_csv(uploaded_file)

        # Display the form for stock levels in the main area
        st.subheader("Enter Current Stock Levels")
        with st.form("stock_level_form"):
            unique_products = client_data_df['Item Type'].unique()
            stock_inputs = {}
            # Use columns for a cleaner input form
            cols = st.columns(3)
            for i, product in enumerate(unique_products):
                with cols[i % 3]:
                    stock_inputs[product] = st.number_input(f"Stock for '{product}'", min_value=0, value=0, step=1)

            submitted = st.form_submit_button("Run Analysis and Generate Alerts")

            if submitted:
                # Call the analysis function and capture the detailed results
                full_results_df = analyze_data_and_generate_alerts(client_data_df, stock_inputs)

                # Display the full results right after analysis completes using a container
                with st.container():
                    st.subheader("Full Inventory Analysis Results")
                    st.dataframe(full_results_df)

    except Exception as e:
        st.error(f"An error occurred during file processing: {e}")

# --- DISPLAY ALERTS IN MAIN AREA ---

alert_data = get_reorder_alerts()

st.subheader("Recent Alerts")
if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    # Use an alert box style for alerts
    for index, row in alert_data.iterrows():
        st.warning(f"🚨 Reorder needed for **{row['product_name']}** (Alert Date: {row['alert_date']})")