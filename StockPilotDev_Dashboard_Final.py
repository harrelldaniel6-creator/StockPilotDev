import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, dash_table, callback_context

# --- 1. App Setup ---
app = dash.Dash(__name__, title="StockPilotDev v3.9 | 2026 Strategy Suite")
server = app.server


# --- 2. Helper Functions ---
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename:
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None

        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    temp_dates = pd.to_datetime(df[col], errors='coerce')
                    if not temp_dates.isna().all(): df[col] = temp_dates
                except:
                    pass
        return df.to_json(date_format='iso', orient='split')
    except Exception:
        return None


def safe_load_df(json_data):
    if not json_data: return pd.DataFrame()
    df = pd.read_json(io.StringIO(json_data), orient='split')
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ['date', 'time', 'start', 'end']):
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def append_data(existing_json, new_json):
    if not existing_json: return new_json
    existing_df, new_df = safe_load_df(existing_json), safe_load_df(new_json)
    return pd.concat([existing_df, new_df], axis=0, ignore_index=True).to_json(date_format='iso', orient='split')


def distribute_wages_hourly(df, wage_col, start_col, end_col):
    if df.empty or wage_col not in df.columns or start_col not in df.columns or end_col not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
    df[end_col] = pd.to_datetime(df[end_col], errors='coerce')
    df[wage_col] = pd.to_numeric(df[wage_col].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(
        0)
    df.dropna(subset=[start_col, end_col, wage_col], inplace=True)
    df = df[df[start_col] < df[end_col]]

    # DEBUGGING: Check data after initial cleaning but before distribution
    print(f"\nDistribute Wages Input rows remaining: {len(df)}")
    if df.empty: return pd.DataFrame()

    hourly_costs = []
    for _, row in df.iterrows():
        start, end, total_wage = row[start_col], row[end_col], row[wage_col]
        duration_minutes = (end - start).total_seconds() / 60
        if duration_minutes <= 0: continue
        wage_per_minute = total_wage / duration_minutes
        current_time = start
        while current_time < end:
            next_hour = current_time.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
            time_until_end_of_hour = min(next_hour, end) - current_time
            minutes_in_segment = time_until_end_of_hour.total_seconds() / 60
            cost_for_segment = minutes_in_segment * wage_per_minute
            hourly_costs.append({'Hour': current_time.hour, 'Spent': cost_for_segment})
            current_time = next_hour
    result_df = pd.DataFrame(hourly_costs)
    return result_df.groupby('Hour')['Spent'].sum().reset_index() if not result_df.empty else result_df


# --- 3. App Layout ---
app.layout = html.Div([
    html.Div([
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9)", style={'color': '#ffffff', 'margin': '0'}),
        html.P("2026 Multi-File Intelligence | Precision Metrics", style={'color': '#e0e0e0'})
    ], style={'backgroundColor': '#2c3e50', 'padding': '20px', 'textAlign': 'center'}),

    html.Div([
        dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']), style={
            'width': '70%', 'height': '60px', 'lineHeight': '30px', 'borderWidth': '2px', 'borderStyle': 'dashed',
            'borderRadius': '10px', 'textAlign': 'center', 'backgroundColor': '#fff'
        }, multiple=True),
        html.Button("Reset Session", id="reset-btn", style={
            'backgroundColor': '#dc3545', 'color': 'white', 'border': 'none', 'padding': '10px 20px',
            'borderRadius': '5px', 'marginLeft': '20px'})
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'margin': '20px'}),

    html.Div(id='upload-status', style={'textAlign': 'center', 'marginBottom': '20px'}),
    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),

    html.Div([
        html.Div(id='summary-stats', style={'display': 'flex', 'justifyContent': 'space-around', 'padding': '15px',
                                            'backgroundColor': '#ffffff', 'borderRadius': '8px',
                                            'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}),
        html.Div([html.Label("Global Date Range:", style={'fontWeight': 'bold'}),
                  dcc.DatePickerRange(id='date-picker-range')], style={'marginTop': '20px'})
    ], style={'maxWidth': '1200px', 'margin': '0 auto'}),

    # SECTION: Sales
    html.Div([
        html.H2("📈 2026 Sales Strategy Map", style={'color': '#28a745'}),
        html.Div([
            html.Div([html.Label("Revenue Col:"), dcc.Dropdown(id='sales-col')], style={'flex': '1'}),
            html.Div([html.Label("Grouping:"), dcc.Dropdown(id='cust-col')], style={'flex': '1'}),
            html.Div([html.Label("Target %:"), dcc.Input(id='growth-target', type='number', value=12)],
                     style={'flex': '0.5'}),
        ], style={'display': 'flex', 'gap': '20px'}),
        html.Div(id='sales-metrics-cards',
                 style={'display': 'flex', 'justifyContent': 'space-between', 'padding': '15px'}),
        dcc.Graph(id='sales-forecast-graph')
    ], style={'padding': '20px', 'margin': '20px auto', 'maxWidth': '1200px', 'border': '1px solid #28a745',
              'borderRadius': '10px'}),

    # SECTION: Labor
    html.Div([
        html.H2("👥 Labor Intelligence", style={'color': '#007bff'}),
        html.Div([
            html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
            html.Div([html.Label("Hours Col:"), dcc.Dropdown(id='hours-col')], style={'flex': '1'}),
            html.Div([html.Label("Group By:"), dcc.Dropdown(id='groupby-col')], style={'flex': '1'}),
        ], style={'display': 'flex', 'gap': '20px'}),
        html.Div([html.Button("Download Report", id="btn-download-labor"), dcc.Download(id="download-labor-csv")],
                 style={'textAlign': 'right', 'marginTop': '10px'}),
        html.Div(id='labor-metrics-cards', style={'marginTop': '10px'}),
        dcc.Graph(id='hourly-labor-graph'),
        html.Div(id='labor-detail-table', style={'marginTop': '10px'})
    ], style={'padding': '20px', 'margin': '20px auto', 'maxWidth': '1200px', 'border': '1px solid #007bff',
              'borderRadius': '10px'}),

    # SECTION: Inventory
    html.Div([
        html.H2("📦 Inventory Intelligence", style={'color': '#dc3545'}),
        html.Div([
            html.Div([html.Label("Stock Col:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
            html.Div([html.Label("Name Col:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
            html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                     style={'flex': '0.5'}),
        ], style={'display': 'flex', 'gap': '20px'}),
        html.Div(id='inventory-metrics-cards', style={'display': 'flex', 'gap': '20px', 'marginTop': '10px'}),
        dcc.Graph(id='inventory-status-graph')
    ], style={'padding': '20px', 'margin': '20px auto', 'maxWidth': '1200px', 'border': '1px solid #dc3545',
              'borderRadius': '10px'}),
], style={'fontFamily': 'Segoe UI, sans-serif', 'backgroundColor': '#f4f4f9'})


# --- 4. Callbacks ---
@app.callback(
    [Output('stored-labor-data', 'data'), Output('stored-sales-data', 'data'), Output('stored-inventory-data', 'data'),
     Output('upload-status', 'children')],
    [Input('upload-data', 'contents'), Input('reset-btn', 'n_clicks')],
    [State('upload-data', 'filename'), State('stored-labor-data', 'data'), State('stored-sales-data', 'data'),
     State('stored-inventory-data', 'data')],
    prevent_initial_call=True
)
def handle_uploads(contents, reset, names, labor, sales, inv):
    if callback_context.triggered_id == 'reset-btn': return None, None, None, html.Div("Session Reset",
                                                                                       style={'color': 'red'})
    if not contents: raise exceptions.PreventUpdate
    files = []
    for c, n in zip(contents, names):
        js = parse_contents(c, n)
        if js:
            fn = n.lower()
            if any(k in fn for k in ['labor', 'wage', 'hour']):
                labor = append_data(labor, js);
                files.append(f"👥 Labor: {n}")
            elif any(k in fn for k in ['sale', 'rev']):
                sales = append_data(sales, js);
                files.append(f"📈 Sales: {n}")
            elif any(k in fn for k in ['inv', 'stock']):
                inv = append_data(inv, js);
                files.append(f"📦 Inventory: {n}")
            else:
                sales = append_data(sales, js);
                files.append(f"📈 Misc: {n}")
    return labor, sales, inv, html.Div(" | ".join(files), style={'color': '#28a745', 'fontWeight': 'bold'})


@app.callback(
    [Output('sales-col', 'options'), Output('sales-col', 'value'), Output('cust-col', 'options'),
     Output('cust-col', 'value'),
     Output('hours-col', 'options'), Output('hours-col', 'value'), Output('wage-col', 'options'),
     Output('wage-col', 'value'),
     Output('groupby-col', 'options'), Output('groupby-col', 'value'), Output('inv-stock-col', 'options'),
     Output('inv-stock-col', 'value'),
     Output('inv-name-col', 'options'), Output('inv-name-col', 'value'), Output('date-picker-range', 'start_date'),
     Output('date-picker-range', 'end_date')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'), Input('stored-inventory-data', 'data')],
    [State('sales-col', 'value'), State('cust-col', 'value'), State('hours-col', 'value'), State('wage-col', 'value')]
)
def sync_ui(labor, sales, inv, s_val, c_val, h_val, w_val):
    dfs = [safe_load_df(d) for d in [labor, sales, inv] if d]
    if not dfs: return [[] if i % 2 == 0 else None for i in range(14)] + [None, None]
    combined = pd.concat(dfs, axis=0, ignore_index=True)
    opts = [{'label': c, 'value': c} for c in combined.columns]

    def check(v): return v if v in combined.columns else (combined.columns if not combined.empty else None)

    dt_cols = combined.select_dtypes(include=['datetime64']).columns
    start, end = (combined[dt_cols].min().min(), combined[dt_cols].max().max()) if not dt_cols.empty else (None, None)
    return [opts, check(s_val), opts, check(c_val), opts, check(h_val), opts, check(w_val), opts, None, opts, None,
            opts, None, start, end]


@app.callback(
    [Output('sales-metrics-cards', 'children'), Output('sales-forecast-graph', 'figure')],
    [Input('stored-sales-data', 'data'), Input('sales-col', 'value'), Input('cust-col', 'value'),
     Input('growth-target', 'value'),
     Input('stored-labor-data', 'data'), Input('hours-col', 'value'), Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date')]
)
def update_sales_view(s_js, rev, grp, growth, l_js, h_col, start_date, end_date):
    df_sales, df_labor = safe_load_df(s_js), safe_load_df(l_js)

    # FIX 1: Filter sales data by global date range
    if start_date and end_date and not df_sales.empty and 'Date' in df_sales.columns:
        df_sales['Date'] = pd.to_datetime(df_sales['Date'])
        df_sales = df_sales[(df_sales['Date'] >= start_date) & (df_sales['Date'] <= end_date)]

    # FIX 2: Check if selected columns exist in current dataframe to prevent KeyError
    if df_sales.empty or not rev or rev not in df_sales.columns or not grp or grp not in df_sales.columns:
        return "Configure Columns Above/Adjust Date Range", go.Figure()

    df_sales[rev] = pd.to_numeric(df_sales[rev].astype(str).str.replace('[$,]', '', regex=True),
                                  errors='coerce').fillna(0)
    total_sales = df_sales[rev].sum()
    forecast = total_sales * (1 + (float(growth or 0) / 100))

    sales_per_hour = 0
    if not df_labor.empty and h_col in df_labor.columns:
        # Filter labor data by the same global date range for calculation consistency
        if start_date and end_date and 'Date' in df_labor.columns:
            df_labor['Date'] = pd.to_datetime(df_labor['Date'])
            df_labor = df_labor[(df_labor['Date'] >= start_date) & (df_labor['Date'] <= end_date)]

        hr_sum = pd.to_numeric(df_labor[h_col], errors='coerce').sum()
        if hr_sum > 0: sales_per_hour = total_sales / hr_sum

    metrics = [html.B(f"Total Rev: ${total_sales:,.0f}"), html.B(f"2026 Forecast: ${forecast:,.0f}"),
               html.B(f"Sales/Hr: ${sales_per_hour:,.2f}")]
    grouped = df_sales.groupby(grp)[rev].agg(Revenue='sum').reset_index().nlargest(15, 'Revenue')
    fig = px.bar(grouped, x=grp, y='Revenue', text_auto='.2s', template="plotly_white")
    fig.update_traces(marker_color='#28a745', textposition='outside')
    return metrics, fig


@app.callback(
    [Output('labor-metrics-cards', 'children'), Output('hourly-labor-graph', 'figure'),
     Output('labor-detail-table', 'children'), Output('download-labor-csv', 'data')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'), Input('wage-col', 'value'),
     Input('sales-col', 'value'), Input('btn-download-labor', 'n_clicks'),
     Input('date-picker-range', 'start_date'), Input('date-picker-range', 'end_date')]  # Added date range inputs
)
def update_labor_metrics_and_graph(l_js, s_js, w_col, r_col, n, start_date, end_date):
    l_df = safe_load_df(l_js)

    # FIX 3: Filter labor data by global date range before any processing
    if start_date and end_date and not l_df.empty and 'Date' in l_df.columns:
        l_df['Date'] = pd.to_datetime(l_df['Date'])
        l_df = l_df[(l_df['Date'] >= start_date) & (l_df['Date'] <= end_date)]

    if l_df.empty or not w_col or w_col not in l_df.columns:
        return html.Div("Upload Labor Data/Adjust Date Range"), go.Figure(), html.Div(), None

    # We assume 'Shift Start' and 'Shift End' are the column names for the detailed analysis
    hourly_spend_df = distribute_wages_hourly(l_df, w_col, 'Start Time', 'End Time')

    # DEBUGGING: Print result of hourly distribution
    print(f"Hourly spend DF length after filtering/distribution: {len(hourly_spend_df)}")

    fig = go.Figure()
    metrics_ui = html.Div(
        f"Total Labor: ${pd.to_numeric(l_df[w_col].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').sum():,.2f}")

    if not hourly_spend_df.empty:
        target_hours_int = list(range(9, 24)) + list(range(0, 4))
        hourly_spend_df = hourly_spend_df[hourly_spend_df['Hour'].isin(target_hours_int)]
        top_3_hours = hourly_spend_df.nlargest(3, 'Spent')['Hour'].tolist()
        colors = ['#f8d7da' if hour in top_3_hours else '#007bff' for hour in hourly_spend_df['Hour']]
        hour_labels = {h: f"{h % 12 if h % 12 != 0 else 12}{'am' if h < 12 or h == 24 else 'pm'}" for h in
                       target_hours_int}
        hourly_spend_df['Display Hour'] = pd.Categorical(hourly_spend_df['Hour'].map(hour_labels),
                                                         categories=hour_labels.values(), ordered=True)
        fig = px.bar(hourly_spend_df, x='Display Hour', y='Spent',
                     title="Total Labor Spend by Hour (Top 3 Highlighted)", template="plotly_white", text_auto='$.2s')
        fig.update_traces(marker_color=colors)
        fig.update_layout(yaxis=dict(tickprefix="$"))

    table = dash_table.DataTable(data=l_df.to_dict('records'), columns=[{"name": i, "id": i} for i in l_df.columns],
                                 page_size=10, style_header={'backgroundColor': '#007bff', 'color': 'white'})
    csv = dcc.send_data_frame(l_df.to_csv,
                              "Labor_Report_2026.csv") if callback_context.triggered_id == 'btn-download-labor' else None
    return metrics_ui, fig, table, csv


@app.callback(
    [Output('inventory-metrics-cards', 'children'), Output('inventory-status-graph', 'figure')],
    [Input('stored-inventory-data', 'data'), Input('inv-stock-col', 'value'), Input('inv-name-col', 'value'),
     Input('reorder-threshold', 'value')]
)
def update_inv(js, stock, name, threshold):
    df = safe_load_df(js)
    if df.empty or not stock or stock not in df.columns: return "Upload Inventory", go.Figure()
    df[stock] = pd.to_numeric(df[stock], errors='coerce').fillna(0)
    low = len(df[df[stock] < float(threshold or 0)])
    fig = px.bar(df.nlargest(15, stock), x=name if (name and name in df.columns) else df.index, y=stock,
                 color_continuous_scale='Reds_r')
    return html.Div(f"Low Stock Items: {low}", style={'backgroundColor': '#dc3545', 'color': 'white', 'padding': '10px',
                                                      'borderRadius': '5px'}), fig


if __name__ == '__main__':
    app.run(debug=True)