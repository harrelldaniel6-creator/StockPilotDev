import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
import numpy as np
import random

# --- CONFIGURATION ---
LABOR_FILE_PATH = 'C:/StockPilotSafe/Excel Files/Labor_Raw_Data.csv'
TARGET_PRIME_COST = 55.0


# --- PLACEHOLDER FUNCTIONS (MOCK DATA) ---
def fetch_shopify_sales_data(start_date_iso):
    print(f"Fetching sales data starting from: {start_date_iso}")
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    mock_data = {
        'Date': [today_date_str, today_date_str, today_date_str],
        'Created_At': [f'{today_date_str} 10:00:00 AM', f'{today_date_str} 11:00:00 AM',
                       f'{today_date_str} 12:00:00 PM'],
        'Total_Sales': [150.00, 220.50, 180.00]
    }
    return pd.DataFrame(mock_data)


def get_reorder_alerts():
    mock_alerts = {
        'product_name': ['T-Shirt', 'Coffee Mug'],
        'variant_title': ['Medium, Blue', 'Small, Red'],
        'inventory_quantity': [2.0, 5.0],
        'alert_date': [pd.Timestamp.now().isoformat(), pd.Timestamp.now().isoformat()]
    }
    return pd.DataFrame(mock_alerts)


# --- AGGREGATION & PROCESSING LAYER (Functional) ---
def get_aggregated_labor_data(LABOR_FILE_PATH, sales_data_df):
    labor_df = pd.read_csv(LABOR_FILE_PATH)
    labor_df.columns = labor_df.columns.str.strip().str.replace(' ', '_')
    labor_df['Date'] = pd.to_datetime(labor_df['Date'], errors='coerce')
    labor_df = labor_df.dropna(subset=['Date'])
    labor_df['Time_In'] = pd.to_datetime(labor_df['Date'].dt.date.astype(str) + ' ' + labor_df['Start_Time'],
                                         format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    labor_df['Time_Out'] = pd.to_datetime(labor_df['Date'].dt.date.astype(str) + ' ' + labor_df['End_Time'],
                                          format='%Y-%m-%d %I:%M:%S %p', errors='coerce')
    labor_df = labor_df.dropna(subset=['Time_In', 'Time_Out'])
    labor_df['Total_Hours'] = (labor_df['Time_Out'] - labor_df['Time_In']).dt.total_seconds() / 3600
    labor_df['Labor_Cost'] = labor_df['Total_Hours'] * labor_df['Hourly_Rate']
    labor_df['Hour'] = labor_df['Time_In'].dt.hour
    hourly_labor_costs = labor_df.groupby(['Date', 'Hour'])['Labor_Cost'].sum().reset_index()
    sales_data_df['Date'] = pd.to_datetime(sales_data_df['Date'], errors='coerce').dt.date.astype(str)
    sales_data_df['Created_At'] = pd.to_datetime(sales_data_df['Created_At'], errors='coerce')
    sales_data_df['Hour'] = sales_data_df['Created_At'].dt.hour
    hourly_sales = sales_data_df.groupby(['Date', 'Hour'])['Total_Sales'].sum().reset_index()
    hourly_sales.rename(columns={'Total_Sales': 'Sales'}, inplace=True)
    hourly_labor_costs['Date'] = hourly_labor_costs['Date'].dt.date.astype(str)
    processed_data = pd.merge(hourly_labor_costs, hourly_sales, on=['Date', 'Hour'], how='outer')
    processed_data.fillna(0, inplace=True)
    processed_data['Prime_Cost_Pct'] = (processed_data['Labor_Cost'] / processed_data['Sales']) * 100
    processed_data['Prime_Cost_Pct'] = processed_data['Prime_Cost_Pct'].replace([np.inf, -np.inf, np.nan], 0)
    print("--- DEBUG: Processed Data Head ---")
    print(processed_data.head())
    print(f"--- DEBUG: Total rows in processed data: {len(processed_data)} ---")
    return processed_data


# --- MASTER DASHBOARD VISUALIZATION LAYER ---
def create_stockpilot_dashboard(labor_df, alerts_df):
    labor_df['Date'] = pd.to_datetime(labor_df['Date'])
    fig = make_subplots(
        rows=2, cols=1,
        # FIX: Removed row_titles to prevent overlap on the far right edge
        # row_titles=['Labor Efficiency Analysis', 'Inventory Reorder Alerts'],
        specs=[[{"secondary_y": True}], [{"type": "table"}]]
    )
    target_exceeded = (labor_df['Prime_Cost_Pct'] > TARGET_PRIME_COST).any()
    target_line_color = 'red' if target_exceeded else 'green'

    # ROW 1: Labor Efficiency Chart (2025 Modern Colors)
    fig.add_trace(
        go.Bar(x=labor_df['Hour'], y=labor_df['Sales'], name="Sales ($)", marker_color='#008080', opacity=0.6), row=1,
        col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=labor_df['Hour'], y=labor_df['Labor_Cost'], name="Labor Cost ($)",
                             line=dict(color='#FFD700', width=3), mode='lines+markers'), row=1, col=1,
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=labor_df['Hour'], y=labor_df['Prime_Cost_Pct'], name="Prime Cost %",
                             line=dict(color='#9966CC', dash='dot', width=2)), row=1, col=1, secondary_y=True)
    fig.add_trace(
        go.Scatter(x=[labor_df['Hour'].min(), labor_df['Hour'].max()], y=[TARGET_PRIME_COST, TARGET_PRIME_COST],
                   mode='lines', line=dict(color=target_line_color, dash='dash', width=3),
                   name=f"Target ({TARGET_PRIME_COST}%)", hoverinfo='name'), row=1, col=1, secondary_y=True)

    # ROW 2: Inventory Alerts Table (Visual Refinements Applied)
    if not alerts_df.empty:
        fig.add_trace(go.Table(
            header=dict(values=["Product Name", "Variant Title", "Inventory Quantity", "Alert Date"],
                        fill_color='#008080', font=dict(color='white', size=12),
                        align=['left', 'left', 'right', 'left']),
            cells=dict(values=[alerts_df[c] for c in alerts_df.columns], fill_color='#f5f5f5',
                       align=['left', 'left', 'right', 'left'])
        ), row=2, col=1)

    # Update layout for master dashboard with increased right margin
    cache_id = random.randint(1000, 9999)
    fig.update_layout(
        title=f'<b>StockPilotDev: Master Operations Dashboard ({cache_id})</b>',
        template="plotly_white",
        height=900,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(r=200)
    )

    # FIX: Use yaxis (the first right y-axis) and add a standoff to prevent overlap with the plot area
    fig.update_yaxes(title_text="Amount ($)", secondary_y=False, row=1, col=1)
    fig.update_yaxes(title_text="Prime Cost (%)", secondary_y=True, row=1, col=1)
    fig.update_yaxes(title_standoff=60, row=1, col=1, secondary_y=False)

    output_html = 'StockPilotDev_Master_Dashboard.html'
    fig.write_html(output_html)
    print(f"Success! Master dashboard generated: {output_html}")
    return fig


# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    try:
        df_dates = pd.read_csv(LABOR_FILE_PATH, usecols=['Date'])
        df_dates.columns = df_dates.columns.str.strip().str.replace(' ', '_')
        df_dates['Date'] = pd.to_datetime(df_dates['Date'], errors='coerce')
        earliest_date = df_dates['Date'].min()
        start_date_iso = earliest_date.isoformat()
        sales_data_df = fetch_shopify_sales_data(start_date_iso)
    except Exception as e:
        print(f"Could not determine start data from CSV: {e}")
        print("Fetching only last 7 days of sales data instead.")
        start_date_iso = (datetime.now() - timedelta(days=7)).isoformat()
        sales_data_df = fetch_shopify_sales_data(start_date_iso)

    processed_data = get_aggregated_labor_data(LABOR_FILE_PATH, sales_data_df)

    if processed_data is not None and not processed_data.empty:
        alerts_df = get_reorder_alerts()
        create_stockpilot_dashboard(processed_data, alerts_df)
        print("Automation complete. Master dashboard updated.")
    else:
        print("ERROR: Processed data was empty or invalid. Check CSV contents or processing logic.")