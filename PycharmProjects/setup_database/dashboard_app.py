import dash
from dash import html, dcc, Input, Output
import plotly.express as px
import pandas as pd
import sqlite3

# Initialize the Dash app
app = dash.Dash(__name__)


def fetch_data_from_db():
    """Fetches all stock data from the SQLite database into a pandas DataFrame."""
    conn = sqlite3.connect('stockpilot.db')
    df = pd.read_sql_query("SELECT * FROM stock_data", conn)
    conn.close()

    # Ensure date column is treated as a date object for plotting
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    return df


# Fetch the initial data
df = fetch_data_from_db()
# Get a list of unique symbols for the dropdown options
available_symbols = df['symbol'].unique()

# --- DEBUGGING LINE ---
print(f"DEBUG: Dashboard found these symbols at startup: {available_symbols}")
# ----------------------

# Define the app layout
app.layout = html.Div(children=[
    html.H1(children='StockPilot Dev Dashboard'),
    html.Div(children='Visualizing stock data from your SQLite database.'),

    html.Div([
        html.Label("Select Stock Symbol:"),
        dcc.Dropdown(
            id='symbol-dropdown',
            options=[{'label': i, 'value': i} for i in available_symbols],
            value=available_symbols if len(available_symbols) > 0 else None,
            clearable=False
        ),
    ], style={'width': '50%', 'display': 'inline-block'}),

    dcc.Graph(id='stock-price-graph'),
])


# Define the callback function to update the graph
@app.callback(
    Output('stock-price-graph', 'figure'),
    Input('symbol-dropdown', 'value')
)
def update_graph(selected_symbol):
    """Updates the graph based on the selected symbol from the dropdown."""
    filtered_df = df[df['symbol'] == selected_symbol]
    fig = px.line(filtered_df, x='trade_date', y='adjusted_close',
                  title=f'{selected_symbol} Adjusted Close Price Over Time')
    return fig


if __name__ == '__main__':
    # Run the development server
    app.run(debug=True)