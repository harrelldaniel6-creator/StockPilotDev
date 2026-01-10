import pandas as pd
import plotly.graph_objects as go
import os

def create_inventory_dashboard(alerts_df):
    """
    Generates an HTML dashboard displaying inventory reorder alerts in a table format.
    """
    if alerts_df.empty:
        print("No alerts to display. Inventory levels are healthy!")
        return

    # Create the Plotly figure
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=["Product Name", "Variant Title", "Inventory Quantity", "Alert Date"],
            fill_color='#34495e', # Dark blue header from our first dashboard
            font=dict(color='white', size=14),
            align='left'
        ),
        cells=dict(
            values=[alerts_df[c] for c in alerts_df.columns],
            fill_color='#f5f5f5', # Light gray cells
            align='left'
        )
    )])

    fig.update_layout(
        title='<b>StockPilotDev: Inventory Reorder Alerts</b>',
        template="plotly_white",
        height=600
    )

    output_html = 'StockPilotDev_Inventory_Dashboard.html'
    fig.write_html(output_html)
    print(f"Success! Inventory dashboard generated: {output_html}")
    return output_html

if __name__ == "__main__":
    # Mock data to run this file standalone for testing (using column names from inventory_checker.py)
    mock_alerts = {
        'product_name': ['T-Shirt', 'Coffee Mug'],
        'variant_title': ['Medium, Blue', 'Small, Red'],
        'inventory_quantity': [2.0, 5.0],
        'alert_date': [pd.Timestamp.now().isoformat(), pd.Timestamp.now().isoformat()]
    }
    alerts_df = pd.DataFrame(mock_alerts)
    create_inventory_dashboard(alerts_df)