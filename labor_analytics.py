import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# --- CONFIGURATION (Ensure TARGET_PRIME_COST is defined in the dashboard script) ---
# TARGET_PRIME_COST = 55.0 # If this is needed here, uncomment and define it

# Define or import necessary functions (placeholders below)
def fetch_shopify_sales_data(start_date_iso):
    # Your existing function implementation goes here
    # Example: print(f"Fetching sales data starting from: {start_date_iso}")
    # return pd.DataFrame(columns=['Date', 'Created_At', 'Total_Sales'])
    return pd.DataFrame()  # Currently returns an empty DF, this needs implementation


def get_reorder_alerts():
    # Your existing function implementation goes here
    # return pd.DataFrame()
    return pd.DataFrame()


# --- AGGREGATION & PROCESSING LAYER ---
def get_aggregated_labor_data(LABOR_FILE_PATH, sales_data_df):
    """
    Processes raw labor and sales data into an hourly aggregated DataFrame.
    """
    labor_df = pd.read_csv(LABOR_FILE_PATH, format='mixed')
    labor_df.columns = labor_df.columns.str.strip().str.replace(' ', '_')  # Clean up columns

    # Ensure Date is parsed correctly
    labor_df['Date'] = pd.to_datetime(labor_df['Date'], errors='coerce', format='mixed')
    labor_df = labor_df.dropna(subset=['Date'])

    # Ensure TimeIn/TimeOut are datetime objects (assuming 'H:M:S AM/PM' format)
    labor_df['Time_In'] = pd.to_datetime(labor_df['Date'].dt.date.astype(str) + ' ' + labor_df['Time_In'],
                                         format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    labor_df['Time_Out'] = pd.to_datetime(labor_df['Date'].dt.date.astype(str) + ' ' + labor_df['Time_Out'],
                                          format='%Y-%m-%d %I:%M:%S %p', errors='coerce')

    labor_df = labor_df.dropna(subset=['Time_In', 'Time_Out'])

    # Calculate Total_Hours and Labor_Cost
    labor_df['Total_Hours'] = (labor_df['Time_Out'] - labor_df['Time_In']).dt.total_seconds() / 3600
    labor_df['Labor_Cost'] = labor_df['Total_Hours'] * labor_df['Hourly_Rate']

    # Aggregate by hour
    labor_df['Hour'] = labor_df['Time_In'].dt.hour
    hourly_labor_costs = labor_df.groupby(['Date', 'Hour'])['Labor_Cost'].sum().reset_index()

    # Prepare sales data (from Shopify)
    # NOTE: sales_data_df must be populated by fetch_shopify_sales_data()
    sales_data_df['Date'] = pd.to_datetime(sales_data_df['Date']).dt.date
    sales_data_df['Hour'] = pd.to_datetime(sales_data_df['Created_At']).dt.hour
    hourly_sales = sales_data_df.groupby(['Date', 'Hour'])['Total_Sales'].sum().reset_index()
    hourly_sales.rename(columns={'Total_Sales': 'Sales'}, inplace=True)

    # Merge labor and sales data
    processed_data = pd.merge(hourly_labor_costs, hourly_sales, on=['Date', 'Hour'], how='outer')
    processed_data.fillna(0, inplace=True)

    # Calculate Prime Cost % safely
    processed_data['Prime_Cost_Pct'] = (processed_data['Labor_Cost'] / processed_data['Sales']) * 100
    processed_data['Prime_Cost_Pct'] = processed_data['Prime_Cost_Pct'].replace([np.inf, -np.inf, np.nan], 0)

    # --- DEBUGGING LINES ---
    print("--- DEBUG: Processed Data Head ---")
    print(processed_data.head())
    print(f"--- DEBUG: Total rows in processed data: {len(processed_data)} ---")
    # -----------------------

    return processed_data

# Note: The main execution logic is handled in StockPilotDev_Dashboard_Final.py which calls this function.
