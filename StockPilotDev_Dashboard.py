import streamlit as st
import pandas as pd
import sqlite3
import os
import shopify  # Make sure to import the new library

# --- SHOPIFY API CONFIGURATION ---
# !! REPLACE THESE PLACEHOLDER VALUES WITH YOUR ACTUAL CREDENTIALS !!
SHOPIFY_SHOP_URL = "stockpilotdev.myshopify.com"
SHOPIFY_API_KEY = "f2b14664e55eba76e5d2aefae8903b21"
SHOPIFY_API_PASSWORD = "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"


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


def fetch_sales_data_from_shopify():
    """Fetches recent orders from Shopify API and returns a pandas DataFrame."""
    try:
        # Establish connection session
        api_url = f"https://{SHOPIFY_API_KEY}:{SHOPIFY_API_PASSWORD}@{SHOPIFY_SHOP_URL}/admin"
        shopify.ShopifyResource.set_site(api_url)

        st.info("Fetching recent orders from Shopify API...")
        orders = shopify.Order.find(status='any', limit=100)  # Fetch up to 100 recent orders

        sales_data = []
        for order in orders:
            order_date = order.created_at
            for line_item in order.line_items:
                sales_data.append({
                    'Order Date': order_date,
                    'Item Type': line_item.title,
                    'Units Sold': line_item.quantity
                })

        # Format the data into the structure our analysis function expects
        sales_df = pd.DataFrame(sales_data)
        st.success(f"Successfully fetched {len(sales_df)} line items from Shopify.")
        return sales_df

    except Exception as e:
        st.error(f"Error fetching data from Shopify API: {e}")
        return None


# --- MAIN APPLICATION LOGIC ---

st.set_page_config(page_title="StockPilot Dashboard", layout="wide")
st.title("StockPilot Re-Order Alerts Dashboard")

create_database()

# --- SIDEBAR FOR INPUTS AND FETCH BUTTON ---
with st.sidebar:
    st.subheader("Data Input & Analysis")

    # Use API Fetch button instead of CSV Uploader
    if st.button("Fetch Latest Data from Shopify API"):
        client_data_df = fetch_sales_data_from_shopify()
        if client_data_df is not None and not client_data_df.empty:
            st.session_state['client_data'] = client_data_df
        elif client_data_df is not None and client_data_df.empty:
            st.warning("No sales data found for analysis.")

# Check if data exists in session state before proceeding
if 'client_data' in st.session_state and not st.session_state['client_data'].empty:
    client_data_df = st.session_state['client_data']

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

# --- DISPLAY ALERTS IN MAIN AREA ---
st.subheader("Recent Alerts")
alert_data = get_reorder_alerts()

if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    # Use an alert box style for alerts
    for index, row in alert_data.iterrows():
        st.warning(f"🚨 Reorder needed for **{row['product_name']}** (Alert Date: {row['alert_date']})")