import streamlit as st
import pandas as pd
import sqlite3
import os
import shopify
from streamlit.web.server import Server as StreamlitServer

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


def convert_df_to_csv(df):
    """Converts a DataFrame to a CSV string for download."""
    return df.to_csv(index=False).encode('utf-8')


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

        sales_df = pd.DataFrame(sales_data)
        st.success(f"Successfully fetched {len(sales_df)} line items from Shopify.")
        return sales_df

    except Exception as e:
        st.error(f"Error fetching data from Shopify API: {e}")
        return None


def fetch_inventory_levels_from_shopify(product_titles):
    """Fetches current inventory levels for specified products from Shopify API."""
    try:
        api_url = f"https://{SHOPIFY_API_KEY}:{SHOPIFY_API_PASSWORD}@{SHOPIFY_SHOP_URL}/admin"
        shopify.ShopifyResource.set_site(api_url)

        st.info("Fetching current inventory levels from Shopify API...")
        inventory_levels = {}

        for title in product_titles:
            products_collection = shopify.Product.find(title=title)

            if products_collection and hasattr(products_collection, 'variants'):
                product = products_collection
                for variant in product.variants:
                    inv_levels = shopify.InventoryLevel.find(inventory_item_ids=variant.inventory_item_id)
                    for level in inv_levels:
                        inventory_levels[title] = level.available
                        break
                    if title in inventory_levels:
                        break

        st.success("Successfully fetched current inventory levels from Shopify.")
        return inventory_levels

    except Exception as e:
        st.error(f"Error fetching inventory levels from Shopify API: {e}")
        return {}


# --- MAIN APPLICATION LOGIC ---

st.set_page_config(page_title="StockPilot Dashboard", layout="wide")
st.title("StockPilot Re-Order Alerts Dashboard")

if 'client_data' not in st.session_state:
    st.session_state['client_data'] = pd.DataFrame()
if 'stock_levels' not in st.session_state:
    st.session_state['stock_levels'] = {}
if 'full_results' not in st.session_state:
    st.session_state['full_results'] = pd.DataFrame()

create_database()

# --- SIDEBAR FOR INPUTS AND FETCH BUTTON ---
with st.sidebar:
    st.subheader("Data Input & Analysis")

    # Option 1: Fetch data via Shopify API (runs full analysis automatically)
    if st.button("Fetch Latest Data from Shopify API"):
        client_data_df = fetch_sales_data_from_shopify()
        if client_data_df is not None and not client_data_df.empty:
            st.session_state['client_data'] = client_data_df
            product_titles = client_data_df['Item Type'].unique()
            current_stock_levels = fetch_inventory_levels_from_shopify(product_titles)
            st.session_state['stock_levels'] = current_stock_levels
            st.session_state['full_results'] = analyze_data_and_generate_alerts(client_data_df, current_stock_levels)
        elif client_data_df is not None and client_data_df.empty:
            st.warning("No sales data found for analysis.")
            st.session_state['client_data'] = pd.DataFrame()

    st.markdown("---")  # Add a separator line

    # Option 2: Upload CSV file (Original Method)
    uploaded_file = st.file_uploader("Or Upload Client Sales Data (CSV)", type="csv")
    if uploaded_file is not None:
        try:
            client_data_df = pd.read_csv(uploaded_file)
            st.session_state['client_data'] = client_data_df
            st.session_state['stock_levels'] = {}
            st.session_state['full_results'] = pd.DataFrame()
            st.success("CSV file uploaded successfully.")
        except Exception as e:
            st.error(f"An error occurred during file processing: {e}")

    st.markdown("---")  # Add another separator line

    # --- NEW: Export Alerts to CSV Button ---
    alert_data_for_export = get_reorder_alerts()
    csv = convert_df_to_csv(alert_data_for_export)

    st.download_button(
        label="Download Re-Order Alerts (CSV)",
        data=csv,
        file_name='stockpilot_reorder_alerts.csv',
        mime='text/csv',
        disabled=alert_data_for_export.empty,  # Disable button if no alerts exist
        help="Click to download a CSV spreadsheet of the current alerts."
    )

# --- MAIN APPLICATION LOGIC ---

if not st.session_state['client_data'].empty:

    st.subheader("Run Manual Analysis (Optional)")
    with st.form("stock_level_form"):
        unique_products = st.session_state['client_data']['Item Type'].unique()
        stock_inputs = {}
        cols = st.columns(3)
        for i, product in enumerate(unique_products):
            current_stock_value = st.session_state['stock_levels'].get(product, 0)
            with cols[i % 3]:
                stock_inputs[product] = st.number_input(f"Stock for '{product}'", min_value=0,
                                                        value=current_stock_value, step=1)

        submitted = st.form_submit_button("Run Analysis and Generate Alerts Manually")

        if submitted:
            st.session_state['full_results'] = analyze_data_and_generate_alerts(st.session_state['client_data'],
                                                                                stock_inputs)

    if not st.session_state['full_results'].empty:
        with st.container():
            st.subheader("Full Inventory Analysis Results")
            st.dataframe(st.session_state['full_results'])

# --- DISPLAY ALERTS IN MAIN AREA ---
st.subheader("Recent Alerts")
alert_data = get_reorder_alerts()

if alert_data.empty:
    st.info("No re-order alerts currently logged.")
else:
    for index, row in alert_data.iterrows():
        st.warning(f"🚨 Reorder needed for **{row['product_name']}** (Alert Date: {row['alert_date']})")