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
        html.P("2026 SMB Command Center | Financial & Labor Precision", style={'color': '#e0e0e0'})
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

    html.Div([
        # PILLAR 1: SALES INTELLIGENCE
        html.Div([
            html.H2("📈 2026 Sales & Health Dashboard", style={'color': '#28a745'}),
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
            html.Div([html.Label("Trend Smoothing:"), dcc.Slider(id='forecast-span', min=1, max=6, value=3)],
                     style={'marginTop': '10px'})
        ], style={'padding': '20px', 'marginBottom': '20px', 'border': '1px solid #28a745', 'borderRadius': '10px',
                  'backgroundColor': '#fff'}),

        # PILLAR 2: LABOR INTELLIGENCE
        html.Div([
            html.H2("👥 Labor Productivity & Cost Distribution", style={'color': '#007bff'}),
            html.Div([
                html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("Start Time:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("End Time:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px'}),
            dcc.Graph(id='labor-hourly-precision-graph'),
        ], style={'padding': '20px', 'border': '1px solid #007bff', 'borderRadius': '10px', 'backgroundColor': '#fff'}),
    ], style={'maxWidth': '1200px', 'margin': '0 auto'})
], style={'fontFamily': 'Segoe UI, sans-serif', 'backgroundColor': '#f4f4f9', 'paddingBottom': '50px'})


# --- 4. Callbacks (Part 2: Visual Intelligence & 7-Day Sales Avg) ---

@app.callback(
    [Output('stored-labor-data', 'data'), Output('stored-sales-data', 'data')],
    [Input('upload-data', 'contents'), Input('reset-btn', 'n_clicks')],
    [State('upload-data', 'filename'), State('stored-labor-data', 'data'), State('stored-sales-data', 'data')],
    prevent_initial_call=True
)
def handle_uploads(contents, reset, names, labor, sales):
    if callback_context.triggered_id == 'reset-btn': return None, None
    if not contents: raise exceptions.PreventUpdate
    for c, n in zip(contents, names):
        js = parse_contents(c, n)
        if js:
            if any(k in n.lower() for k in ['labor', 'wage']):
                labor = append_data(labor, js)
            else:
                sales = append_data(sales, js)
    return labor, sales


@app.callback(
    [Output('sales-col', 'options'), Output('cust-col', 'options'),
     Output('wage-col', 'options'), Output('start-col', 'options'), Output('end-col', 'options')],
    [Input('stored-sales-data', 'data'), Input('stored-labor-data', 'data')]
)
def sync_dropdowns(s_js, l_js):
    s_df, l_df = safe_load_df(s_js), safe_load_df(l_js)
    s_opts = [{'label': c, 'value': c} for c in s_df.columns]
    l_opts = [{'label': c, 'value': c} for c in l_df.columns]
    return s_opts, s_opts, l_opts, l_opts, l_opts


@app.callback(
    [Output('topline-stats', 'children'), Output('sales-kpi-cards', 'children'), Output('sales-trend-graph', 'figure')],
    [Input('stored-sales-data', 'data'), Input('sales-col', 'value'),
     Input('cust-col', 'value'), Input('forecast-span', 'value'),
     Input('fixed-costs', 'value'), Input('cogs-pct', 'value')]
)
def update_sales_intelligence(js, rev, cust, span, f_costs, cogs_pct):
    df = safe_load_df(js)
    if df.empty or not rev: return "", "Upload Sales Data to See 2026 Insights", go.Figure()

    # Financial Cleaning
    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
    df = df.sort_values('Date')
    total_rev = df[rev].sum()
    order_count = len(df)
    aov = total_rev / order_count if order_count > 0 else 0
    gross_profit = total_rev * (1 - (cogs_pct / 100))

    # 1. Topline Stats
    topline = [
        html.Div([html.Small("TOTAL REVENUE"), html.H2(f"${total_rev:,.0f}")],
                 title="Total income before any expenses or deductions.",
                 style={'flex': '1', 'backgroundColor': '#28a745', 'color': 'white', 'padding': '10px',
                        'borderRadius': '8px', 'textAlign': 'center', 'cursor': 'help'}),
        html.Div([html.Small("GROSS PROFIT"), html.H2(f"${gross_profit:,.0f}")],
                 title=f"Estimated take-home after a {cogs_pct}% product cost.",
                 style={'flex': '1', 'backgroundColor': '#1e7e34', 'color': 'white', 'padding': '10px',
                        'borderRadius': '8px', 'textAlign': 'center', 'cursor': 'help'}),
        html.Div([html.Small("AVG ORDER (AOV)"), html.H2(f"${aov:,.2f}")],
                 title="The average amount spent per transaction.",
                 style={'flex': '1', 'backgroundColor': '#fff', 'border': '1px solid #28a745', 'padding': '10px',
                        'borderRadius': '8px', 'textAlign': 'center', 'cursor': 'help'}),
        html.Div([html.Small("ORDERS"), html.H2(f"{order_count:,}")],
                 title="Total count of all processed sales records.",
                 style={'flex': '1', 'backgroundColor': '#fff', 'border': '1px solid #28a745', 'padding': '10px',
                        'borderRadius': '8px', 'textAlign': 'center', 'cursor': 'help'}),
    ]

    # 2. Advanced KPI Logic
    daily_rev = df.set_index('Date').resample('D')[rev].sum().reset_index()
    # Calculate 7-Day Average Revenue (Rolling)
    seven_day_avg = daily_rev[rev].tail(7).mean() if len(daily_rev) >= 7 else daily_rev[rev].mean()

    monthly = df.set_index('Date').resample('ME')[rev].sum().reset_index()

    retention, churn = 0, 0
    if cust and cust in df.columns:
        counts = df[cust].value_counts()
        retention = (len(counts[counts > 1]) / len(counts)) * 100
        recent = df[df['Date'] > (df['Date'].max() - pd.Timedelta(days=60))][cust].nunique()
        churn = max(0, (1 - (recent / df[cust].nunique())) * 100)

    be_progress = min(100, (monthly[rev].iloc[-1] / f_costs * 100)) if f_costs and not monthly.empty else 0

    # 3. KPI Cards with Tooltips (REPLACED VELOCITY WITH 7-DAY AVG)
    kpi_cards = html.Div([
        html.Div([
            html.Div([
                html.Small("7-DAY DAILY AVG", style={'borderBottom': '1px dotted #ccc'}),
                html.H3(f"${seven_day_avg:,.2f}", style={'color': '#28a745'})
            ], title="7-Day Rolling Average: Your actual daily revenue performance over the last week of data.",
                style={'flex': '1', 'borderRight': '1px solid #eee', 'cursor': 'help'}),

            html.Div([
                html.Small("RETENTION", style={'borderBottom': '1px dotted #ccc'}),
                html.H3(f"{retention:.1f}%", style={'color': '#007bff'})
            ], title="The percentage of your customers who have purchased more than once.",
                style={'flex': '1', 'borderRight': '1px solid #eee', 'cursor': 'help'}),

            html.Div([
                html.Small("CHURN RISK", style={'borderBottom': '1px dotted #ccc'}),
                html.H3(f"{churn:.1f}%", style={'color': '#dc3545'})
            ], title="Percentage of customers who haven't returned in the last 60 days.",
                style={'flex': '1', 'borderRight': '1px solid #eee', 'cursor': 'help'}),

            html.Div([
                html.Small("BREAK-EVEN", style={'borderBottom': '1px dotted #ccc'}),
                html.H3(f"{be_progress:.1f}%"),
                html.Div(style={'backgroundColor': '#eee', 'height': '8px', 'borderRadius': '4px'},
                         children=[html.Div(
                             style={'backgroundColor': '#28a745', 'height': '100%', 'width': f'{be_progress}%',
                                    'borderRadius': '4px'})])
            ], title=f"Monthly progress toward covering your ${f_costs:,.0f} fixed costs.",
                style={'flex': '1.5', 'padding': '0 15px', 'cursor': 'help'}),
        ], style={'display': 'flex', 'textAlign': 'center', 'padding': '15px', 'backgroundColor': '#fff',
                  'borderRadius': '8px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.05)', 'border': '1px solid #eee'})
    ], style={'marginBottom': '20px'})

    # 4. Final Graphing
    monthly['Trend'] = monthly[rev].rolling(window=span or 3).mean()
    fig = px.bar(monthly, x='Date', y=rev, title="Monthly Revenue Performance vs Trend",
                 color_discrete_sequence=['#28a745'], opacity=0.7, text_auto='$.2s')
    fig.add_scatter(x=monthly['Date'], y=monthly['Trend'], name="Trendline", line=dict(color='orange', width=4))

    if not monthly.empty:
        peak = monthly.loc[monthly[rev].idxmax()]
        trough = monthly.loc[monthly[rev].idxmin()]
        fig.add_annotation(x=peak['Date'], y=peak[rev], text="PEAK REVENUE", showarrow=True, arrowhead=2,
                           bgcolor="#28a745", font=dict(color="white"))
        fig.add_annotation(x=trough['Date'], y=trough[rev], text="LOW POINT", showarrow=True, arrowhead=2,
                           bgcolor="#dc3545", font=dict(color="white"))

    fig.update_layout(template="plotly_white", margin=dict(t=60, b=0, l=0, r=0), yaxis_tickprefix='$')
    fig.update_traces(textposition='outside', selector=dict(type='bar'))

    return topline, kpi_cards, fig


@app.callback(
    Output('labor-hourly-precision-graph', 'figure'),
    [Input('stored-labor-data', 'data'), Input('wage-col', 'value'), Input('start-col', 'value'),
     Input('end-col', 'value')]
)
def update_labor_view(js, wage, start, end):
    df = safe_load_df(js)
    if df.empty or not all([wage, start, end]): return go.Figure()

    hourly_df = distribute_wages_hourly(df, wage, start, end)
    target_hours = list(range(9, 24)) + list(range(0, 4))
    hourly_df = hourly_df[hourly_df['Hour'].isin(target_hours)]
    top_3 = hourly_df.nlargest(3, 'Spent')['Hour'].tolist()
    colors = ['#f8d7da' if h in top_3 else '#007bff' for h in hourly_df['Hour']]

    labels = {h: f"{h % 12 if h % 12 != 0 else 12}{'am' if h < 12 or h == 24 else 'pm'}" for h in target_hours}
    hourly_df['Display Hour'] = pd.Categorical(hourly_df['Hour'].map(labels), categories=labels.values(), ordered=True)

    fig = px.bar(hourly_df, x='Display Hour', y='Spent', title="Labor Cost by Hour", text_auto='$.2s')
    fig.update_traces(marker_color=colors, textposition='outside', selector=dict(type='bar'))
    fig.update_layout(template="plotly_white", yaxis_tickprefix='$')
    return fig


if __name__ == '__main__':
    app.run(debug=True)