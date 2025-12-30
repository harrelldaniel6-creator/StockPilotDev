import base64
import io
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State

# Initialize the Dash app
# Note: In a real Render deployment, you might expose 'server = app.server' for Gunicorn
app = dash.Dash(__name__)
server = app.server

# Helper function to parse uploaded content
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = None
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename:
            # Assume that the user uploaded an excel file
            df = pd.read_excel(io.BytesIO(decoded))
    except Exception as e:
        print(f"Error processing file: {e}")
        return None

    if df is not None:
        # Convert dataframe to a JSON string for storage in dcc.Store
        return df.to_json(date_format='iso', orient='split')
    return None


# --- App Layout ---
app.layout = html.Div([
    html.H1("StockPilot Dev Dashboard"),
    html.P("Visualizing business data from your uploads."),

    # Add the CSV Upload component
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select a CSV/Excel File')
        ]),
        style={
            'width': '50%', 'height': '60px', 'lineHeight': '60px',
            'borderWidth': '1px', 'borderStyle': 'dashed',
            'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px'
        },
        multiple=False  # Allow only one file at a time
    ),

    # Store the processed data in a hidden component
    dcc.Store(id='stored-data', storage_type='session'),

    html.Div(id='output-status'),

    html.H3("Data Analysis Graph"),
    dcc.Graph(id='analysis-graph')
])


# --- Callbacks ---

# Callback 1: Process the uploaded file and store it
@app.callback(Output('stored-data', 'data'),
              Input('upload-data', 'contents'),
              State('upload-data', 'filename'))
def update_store(contents, filename):
    if contents is not None:
        data_json = parse_contents(contents, filename)
        return data_json
    return None


# Callback 2: Update the status message based on stored data
@app.callback(Output('output-status', 'children'),
              Input('stored-data', 'data'))
def update_status(data):
    if data is not None:
        df = pd.read_json(data, orient='split')
        return html.Div([f"Successfully loaded data with {len(df.columns)} columns and {len(df)} rows."])
    return html.Div(["Awaiting file upload..."])


# Callback 3: Generate the graph using the stored data
@app.callback(Output('analysis-graph', 'figure'),
              Input('stored-data', 'data'))
def update_graph(data):
    if data is None:
        # Return an empty figure if no data is loaded yet
        return go.Figure(layout=go.Layout(title="Upload data to see graph"))

    df = pd.read_json(data, orient='split')

    # ASSUMPTION: This code assumes your uploaded data has 'trade_date' and 'adjusted_close' columns.
    # You will need to modify these column names once you use real business data.
    if 'trade_date' in df.columns and 'adjusted_close' in df.columns:
        fig = go.Figure(data=[go.Scatter(x=df['trade_date'], y=df['adjusted_close'], mode='lines+markers')])
        fig.update_layout(title='Adjusted Close Price Over Time',
                          xaxis_title='Trade Date',
                          yaxis_title='Adjusted Close')
        return fig
    else:
        return go.Figure(
            layout=go.Layout(title="Data loaded, but missing required columns (e.g., 'trade_date', 'adjusted_close')."))


# --- Run the application locally ---
if __name__ == '__main__':
    # Running locally for testing
    app.run_server(debug=True)