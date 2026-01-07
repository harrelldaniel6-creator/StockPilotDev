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
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8'))) if 'csv' in filename else pd.read_excel(
            io.BytesIO(decoded))
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    temp_dates = pd.to_datetime(df[col], errors='coerce')
                    if not temp_dates.isna().all(): df[col] = temp_dates
                except:
                    pass
        return df.to_json(date_format='iso', orient='split')
    except:
        return None


def safe_load_df(json_data):
    if not json_data: return pd.DataFrame()
    df = pd.read_json(io.StringIO(json_data), orient='split')
    dt_cols = df.select_dtypes(include=['datetime64']).columns
    if not dt_cols.empty and 'Date' not in df.columns: df['Date'] = df[dt_cols]
    if 'Date' in df.columns: df['Date'] = pd.to_datetime(df['Date'])
    return df


def append_data(existing_json, new_json):
    if not existing_json: return new_json
    return pd.concat([safe_load_df(existing_json), safe_load_df(new_json)], axis=0, ignore_index=True).to_json(
        date_format='iso', orient='split')


def distribute_wages_hourly(df, wage_col, start_col, end_col):
    if df.empty or not all(c in df.columns for c in [wage_col, start_col, end_col]): return pd.DataFrame()
    df = df.copy()
    df[start_col] = pd.to_datetime(df[start_col], errors='coerce')
    df[end_col] = pd.to_datetime(df[end_col], errors='coerce')
    df = df.dropna(subset=[start_col, end_col])
    df[wage_col] = pd.to_numeric(df[wage_col].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(
        0)

    hourly_costs = []
    for _, row in df.iterrows():
        start, end, total_wage = row[start_col], row[end_col], row[wage_col]
        duration = (end - start).total_seconds() / 3600
        if duration <= 0: continue
        wage_per_h = total_wage / duration
        curr = start
        while curr < end:
            next_h = curr.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
            seg_end = min(next_h, end)
            hourly_costs.append({'Hour': curr.hour, 'Spent': (seg_end - curr).total_seconds() / 3600 * wage_per_h})
            curr = next_h
    res = pd.DataFrame(hourly_costs)
    return res.groupby('Hour')['Spent'].sum().reset_index() if not res.empty else res


# --- 3. App Layout ---
app.layout = html.Div([
    html.Div([
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9)", style={'color': '#ffffff', 'margin': '0'}),
        html.P("2026 SMB Command Center | Sales, Labor & Inventory", style={'color': '#e0e0e0'})
    ], style={'backgroundColor': '#2c3e50', 'padding': '20px', 'textAlign': 'center'}),

    html.Div([
        dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']), style={
            'width': '65%', 'height': '60px', 'lineHeight': '30px', 'borderWidth': '2px', 'borderStyle': 'dashed',
            'borderRadius': '10px', 'textAlign': 'center', 'backgroundColor': '#fff'
        }, multiple=True),
        html.Button("Reset Session", id="reset-btn",
                    style={'backgroundColor': '#dc3545', 'color': 'white', 'padding': '10px 20px',
                           'borderRadius': '5px', 'marginLeft': '20px'})
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'margin': '20px'}),

    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),

    html.Div([
        # PILLAR 1: SALES
        html.Div([
            html.H2("📈 Sales & Financials", style={'color': '#28a745'}),
            html.Div([
                html.Div([html.Label("Revenue Col:"), dcc.Dropdown(id='sales-col')], style={'flex': '1'}),
                html.Div([html.Label("Cust ID Col:"), dcc.Dropdown(id='cust-col')], style={'flex': '1'}),
                html.Div([html.Label("Est. COGS %:"), dcc.Input(id='cogs-pct', type='number', value=30)],
                         style={'flex': '0.5'}),
                html.Div([html.Label("Monthly Target:"), dcc.Input(id='fixed-costs', type='number', value=5000)],
                         style={'flex': '0.7'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '10px'}),
            html.Div(id='topline-stats', style={'display': 'flex', 'gap': '10px', 'marginBottom': '15px'}),
            html.Div(id='sales-kpi-cards'),
            dcc.Graph(id='sales-trend-graph'),
        ], style={'padding': '20px', 'marginBottom': '20px', 'border': '1px solid #28a745', 'borderRadius': '10px',
                  'backgroundColor': '#fff'}),

        # PILLAR 2: LABOR
        html.Div([
            html.H2("👥 Labor Productivity", style={'color': '#007bff'}),
            html.Div([
                html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("Start Time:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("End Time:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px'}),
            dcc.Graph(id='labor-hourly-graph'),
        ], style={'padding': '20px', 'marginBottom': '20px', 'border': '1px solid #007bff', 'borderRadius': '10px',
                  'backgroundColor': '#fff'}),

        # PILLAR 3: INVENTORY
        html.Div([
            html.H2("📦 Inventory Intelligence", style={'color': '#dc3545'}),
            html.Div([
                html.Div([html.Label("Stock Qty Col:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
                html.Div([html.Label("Product Name:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}),
            html.Div(id='inventory-topline', style={'display': 'flex', 'gap': '10px', 'marginBottom': '15px'}),
            dcc.Graph(id='inventory-graph')
        ], style={'padding': '20px', 'border': '1px solid #dc3545', 'borderRadius': '10px', 'backgroundColor': '#fff'}),

    ], style={'maxWidth': '1200px', 'margin': '0 auto'})
], style={'fontFamily': 'Segoe UI, sans-serif', 'backgroundColor': '#f4f4f9', 'paddingBottom': '50px'})


# --- 4. Callbacks ---
@app.callback(
    [Output('stored-labor-data', 'data'), Output('stored-sales-data', 'data'), Output('stored-inventory-data', 'data')],
    [Input('upload-data', 'contents'), Input('reset-btn', 'n_clicks')],
    [State('upload-data', 'filename'), State('stored-labor-data', 'data'), State('stored-sales-data', 'data'),
     State('stored-inventory-data', 'data')],
    prevent_initial_call=True
)
def handle_uploads(contents, reset, names, labor, sales, inv):
    if callback_context.triggered_id == 'reset-btn': return None, None, None
    if not contents: raise exceptions.PreventUpdate
    for c, n in zip(contents, names):
        js = parse_contents(c, n)
        if js:
            fn = n.lower()
            if any(k in fn for k in ['labor', 'wage']):
                labor = append_data(labor, js)
            elif any(k in fn for k in ['inv', 'stock']):
                inv = append_data(inv, js)
            else:
                sales = append_data(sales, js)
    return labor, sales, inv


@app.callback(
    [Output('sales-col', 'options'), Output('cust-col', 'options'),
     Output('wage-col', 'options'), Output('start-col', 'options'), Output('end-col', 'options'),
     Output('inv-stock-col', 'options'), Output('inv-name-col', 'options')],
    [Input('stored-sales-data', 'data'), Input('stored-labor-data', 'data'), Input('stored-inventory-data', 'data')]
)
def sync_dropdowns(s_js, l_js, i_js):
    s_df, l_df, i_df = safe_load_df(s_js), safe_load_df(l_js), safe_load_df(i_js)
    return [[{'label': c, 'value': c} for c in df.columns] for df in [s_df, s_df, l_df, l_df, l_df, i_df, i_df]]


@app.callback(
    [Output('topline-stats', 'children'), Output('sales-kpi-cards', 'children'), Output('sales-trend-graph', 'figure')],
    [Input('stored-sales-data', 'data'), Input('sales-col', 'value'),
     Input('cust-col', 'value'), Input('fixed-costs', 'value'), Input('cogs-pct', 'value')]
)
def update_sales(js, rev, cust, f_costs, cogs_pct):
    df = safe_load_df(js)
    if df.empty or not rev: return "", "Upload Sales Data", go.Figure()

    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
    df = df.sort_values('Date')
    total_rev = df[rev].sum()
    gross_profit = total_rev * (1 - (cogs_pct / 100))
    daily_rev = df.set_index('Date').resample('D')[rev].sum().reset_index()
    seven_day_avg = daily_rev[rev].tail(7).mean() if not daily_rev.empty else 0

    topline = [
        html.Div([html.Small("TOTAL REVENUE"), html.H2(f"${total_rev:,.0f}")],
                 style={'flex': '1', 'backgroundColor': '#28a745', 'color': 'white', 'padding': '10px',
                        'borderRadius': '8px', 'textAlign': 'center'}),
        html.Div([html.Small("GROSS PROFIT"), html.H2(f"${gross_profit:,.0f}")],
                 title=f"Est. profit at {cogs_pct}% COGS",
                 style={'flex': '1', 'backgroundColor': '#1e7e34', 'color': 'white', 'padding': '10px',
                        'borderRadius': '8px', 'textAlign': 'center', 'cursor': 'help'})
    ]

    retention = 0
    if cust and cust in df.columns:
        counts = df[cust].value_counts()
        retention = (len(counts[counts > 1]) / len(counts)) * 100 if len(counts) > 0 else 0

    monthly = df.set_index('Date').resample('ME')[rev].sum().reset_index()
    be_progress = min(100, (monthly[rev].iloc[-1] / f_costs * 100)) if f_costs and not monthly.empty else 0

    kpi_cards = html.Div([
        html.Div([
            html.Div([html.Small("7-DAY DAILY AVG"), html.H3(f"${seven_day_avg:,.2f}", style={'color': '#28a745'})],
                     title="Avg revenue over the last week.",
                     style={'flex': '1', 'borderRight': '1px solid #eee', 'cursor': 'help'}),
            html.Div([html.Small("RETENTION"), html.H3(f"{retention:.1f}%", style={'color': '#007bff'})],
                     style={'flex': '1', 'borderRight': '1px solid #eee', 'cursor': 'help'}),
            html.Div([html.Small("BREAK-EVEN"), html.H3(f"{be_progress:.1f}%"),
                      html.Div(style={'backgroundColor': '#eee', 'height': '8px', 'borderRadius': '4px'}, children=[
                          html.Div(style={'backgroundColor': '#28a745', 'height': '100%', 'width': f'{be_progress}%',
                                          'borderRadius': '4px'})])],
                     style={'flex': '1.5', 'padding': '0 15px', 'cursor': 'help'})
        ], style={'display': 'flex', 'textAlign': 'center', 'padding': '15px', 'backgroundColor': '#fff',
                  'borderRadius': '8px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.05)', 'border': '1px solid #eee'})
    ])

    fig = px.bar(monthly, x='Date', y=rev, title="Monthly Revenue vs Trend", text_auto='$.2s')
    fig.update_layout(template="plotly_white", yaxis_tickprefix='$')
    fig.update_traces(textposition='outside', selector=dict(type='bar'), marker_color='#28a745')
    return topline, kpi_cards, fig


@app.callback(
    Output('labor-hourly-graph', 'figure'),
    [Input('stored-labor-data', 'data'), Input('wage-col', 'value'), Input('start-col', 'value'),
     Input('end-col', 'value')]
)
def update_labor(js, wage, start, end):
    df = safe_load_df(js)
    if df.empty or not all([wage, start, end]): return go.Figure()
    hourly_df = distribute_wages_hourly(df, wage, start, end)
    fig = px.bar(hourly_df, x='Hour', y='Spent', title="Labor Cost by Hour", text_auto='$.2s')
    fig.update_layout(template="plotly_white", yaxis_tickprefix='$', xaxis=dict(tickmode='linear'))
    fig.update_traces(textposition='outside', selector=dict(type='bar'), marker_color='#007bff')
    return fig


@app.callback(
    [Output('inventory-topline', 'children'), Output('inventory-graph', 'figure')],
    [Input('stored-inventory-data', 'data'), Input('inv-stock-col', 'value'), Input('inv-name-col', 'value'),
     Input('reorder-threshold', 'value')]
)
def update_inv(js, stock, name, thresh):
    df = safe_load_df(js)
    if df.empty or not stock: return "", go.Figure()
    df[stock] = pd.to_numeric(df[stock], errors='coerce').fillna(0)
    low = len(df[df[stock] < float(thresh or 0)])
    topline = [html.Div([html.Small("LOW STOCK ALERTS"), html.H2(f"{low} Items")],
                        style={'flex': '1', 'backgroundColor': '#dc3545', 'color': 'white', 'padding': '10px',
                               'borderRadius': '8px', 'textAlign': 'center'})]

    display_df = df.nlargest(15, stock)
    colors = ['#dc3545' if v < float(thresh or 0) else '#6c757d' for v in display_df[stock]]
    fig = px.bar(display_df, x=name if name else display_df.index, y=stock, title="Inventory Levels (Red = Alert)",
                 text_auto='.0f')
    fig.update_traces(marker_color=colors, textposition='outside')
    fig.update_layout(template="plotly_white")
    return topline, fig


if __name__ == '__main__':
    app.run(debug=True)