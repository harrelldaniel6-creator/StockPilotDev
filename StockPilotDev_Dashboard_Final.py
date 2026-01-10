import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, ctx
from plotly.subplots import make_subplots
import numpy as np
from sklearn.linear_model import LinearRegression

# --- 1. App Setup ---
# Version 4.2: Integrated Predictive Suite
app = dash.Dash(__name__, title="StockPilotDev v4.2 | Chef's Statement Edition")
server = app.server  # Essential for Render/Gunicorn deployment


# --- 2. Helper Functions ---
def parse_contents(contents, filename):
    """Processes uploaded CSV or Excel files into a JSON format for session storage."""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        else:
            df = pd.read_excel(io.BytesIO(decoded))

        # Automatic date detection for all columns
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    temp_dates = pd.to_datetime(df[col], errors='coerce')
                    if not temp_dates.isna().all():
                        df[col] = temp_dates
                except:
                    pass
        return df.to_json(date_format='iso', orient='split')
    except Exception as e:
        print(f"Error parsing {filename}: {e}")
        return None

    def safe_load_df(json_data):
        """Safely converts stored JSON back into a usable Pandas DataFrame."""
        if not json_data:
            return pd.DataFrame()
        try:
            df = pd.read_json(io.StringIO(json_data), orient='split')
            # Re-convert date columns that were stringified in JSON
            dt_cols = df.select_dtypes(include=['datetime64', 'object']).columns
            for col in dt_cols:
                try:
                    df[col] = pd.to_datetime(df[col])
                except:
                    pass
            # Ensure chronological order based on the first detected date column
            date_candidates = df.select_dtypes(include=['datetime64']).columns
            if not date_candidates.empty:
                df = df.sort_values(by=date_candidates[0])
            return df
        except:
            return pd.DataFrame()

