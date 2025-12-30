import base64
import io
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State

# Initialize the Dash app
# Expose 'server' for Gunicorn on Render
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
        # Return an error message to the user interface
        return html.Div(['There was an error processing this file.'], style={'color': 'red'})

    if df is not None:
        # Convert dataframe to a JSON string for storage in dcc.Store
        # Note: If this function returns a Dash html component (like Div above), it cannot be stored in dcc.Store
        # So ensure you handle the error appropriately in the calling callback.
        return df.to_json(date_format='iso', orient='split')
    return None


# --- App Layout ---
app.layout = html.Div([
    html.H1("Small Business Data Analysis Dashboard"),
    html.P("Upload your business data to generate analysis and reports."),

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
        # Ensure that if an error message html.Div is returned, we handle it and don't store it
        if isinstance(data_json, str):
            return data_json
    return None


# Callback 2: Update the status message based on stored data
@app.callback(Output('output-status', 'children'),
              Input('stored-data', 'data'))
def update_status(data):
    if data is not None:
        # Use a temporary read to get row/column counts for the status message
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

    # This is where your custom business analysis goes.
    # We will assume a simple line graph using the first two columns of the uploaded data for testing.
    if len(df.columns) >= 2:
        x_col = df.columns[0]
        y_col = df.columns[1]
        fig = go.Figure(data=[go.Scatter(x=df[x_col], y=df[y_col], mode='lines+markers')])
        fig.update_layout(title=f'Analysis of {y_col} over {x_col}',
                          xaxis_title=x_col,
                          yaxis_title=y_col)
        return fig
    else:
        return go.Figure(layout=go.Layout(title="Data loaded, but requires at least two columns for visualization."))


# --- Run the application locally ---
if __name__ == '__main__':
    # Running locally for testing
    app.run_server(debug=True)