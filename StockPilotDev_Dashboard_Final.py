import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions
from plotly.subplots import make_subplots

# --- 1. App Setup ---
app = dash.Dash(__name__, title="StockPilotDev v3.9.1 | 2026 Strategy Suite")
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
                    if not temp_dates.isna().all():
                        df[col] = temp_dates
                except:
                    pass
        return df.to_json(date_format='iso', orient='split')
    except Exception as e:
        print(f"Error parsing {filename}: {e}")
        return None


def safe_load_df(json_data):
    if not json_data: return pd.DataFrame()
    try:
        df = pd.read_json(io.StringIO(json_data), orient='split')
        dt_cols = df.select_dtypes(include=['datetime64', 'object']).columns
        for col in dt_cols:
            try:
                df[col] = pd.to_datetime(df[col])
            except:
                pass
        if not df.select_dtypes(include=['datetime64']).empty:
            first_date_col = df.select_dtypes(include=['datetime64']).columns[0]
            df = df.sort_values(by=first_date_col)
        return df
    except:
        return pd.DataFrame()


def distribute_wages_hourly(df, wage_col, start_col, end_col):
    hourly_costs = []
    for _, row in df.iterrows():
        start, end = row[start_col], row[end_col]
        total_wage = row[wage_col]
        duration = (end - start).total_seconds() / 3600
        if duration <= 0: continue
        wage_per_h = total_wage / duration
        curr = start
        while curr < end:
            next_h = curr.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
            seg_end = min(next_h, end)
            hourly_costs.append({
                'Hour': curr.hour,
                'Spent': (seg_end - curr).total_seconds() / 3600 * wage_per_h,
                'Hours_Count': (seg_end - curr).total_seconds() / 3600
            })
            curr = next_h
    res = pd.DataFrame(hourly_costs)
    if res.empty: return pd.DataFrame(columns=['Hour', 'Spent', 'Hours_Count'])
    return res.groupby('Hour').agg({'Spent': 'sum', 'Hours_Count': 'sum'}).reset_index()


# --- 3. App Layout ---
app.layout = html.Div([
    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),

    html.Div([
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9.1)",
                style={'color': '#ffffff', 'margin': '0', 'fontWeight': '300'}),
        html.P("2026 SMB Command Center | Sales, Labor & Inventory", style={'color': '#cbd5e0'})
    ], style={'backgroundColor': '#2d3748', 'padding': '40px 20px', 'textAlign': 'center',
              'borderRadius': '0 0 20px 20px'}),

    html.Div([
        html.Div([
            dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']),
                       style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                              'borderStyle': 'dashed', 'borderRadius': '10px', 'textAlign': 'center',
                              'backgroundColor': '#fff'},
                       multiple=True),
            html.Button("Reset Session", id="reset-btn",
                        style={'backgroundColor': '#e53e3e', 'color': 'white', 'padding': '10px 25px',
                               'borderRadius': '8px', 'border': 'none', 'marginTop': '15px', 'cursor': 'pointer'})
        ], style={'margin': '30px auto', 'maxWidth': '800px', 'textAlign': 'center'}),

        # PILLAR 1: SALES & FINANCIALS
        html.Div([
            html.H2("📈 Sales & Financials", style={'color': '#38a169'}),
            html.Div([
                html.Div([html.Label("Revenue Col:"), dcc.Dropdown(id='sales-col')], style={'flex': '1'}),
                html.Div([html.Label("Cust ID Col:"), dcc.Dropdown(id='cust-col')], style={'flex': '1'}),
                html.Div([html.Label("Est. COGS %:"), dcc.Input(id='cogs-pct', type='number', value=30)],
                         style={'flex': '0.5'}),
                html.Div([html.Label("Monthly Target:"), dcc.Input(id='fixed-costs', type='number', value=5000)],
                         style={'flex': '0.7'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='topline-stats', style={'display': 'flex', 'gap': '15px'}),
            html.Div(id='sales-kpi-cards', style={'marginTop': '20px'}),
            dcc.Graph(id='revenue-trend-graph'),
            dcc.Graph(id='customer-pareto-graph'),
        ], style={'padding': '30px', 'backgroundColor': '#fff', 'borderRadius': '15px', 'marginBottom': '30px',
                  'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}),

        # PILLAR 2: LABOR & LEAK DETECTION
        html.Div([
            html.H2("👥 Labor Productivity", style={'color': '#5a67d8'}),
            html.Div([
                html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("Start Time:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("End Time:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
                html.Div([html.Label("Labor Cap %:"), dcc.Input(id='labor-threshold', type='number', value=30)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='labor-kpis', style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px'}),
            html.Div(id='chef-summary-output',
                     style={'padding': '20px', 'backgroundColor': '#f7fafc', 'borderRadius': '12px',
                            'borderLeft': '10px solid #5a67d8', 'marginTop': '20px'}),
            dcc.Graph(id='labor-hourly-graph'),
        ], style={'padding': '30px', 'backgroundColor': '#fff', 'borderRadius': '15px', 'marginBottom': '30px',
                  'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}),

        # PILLAR 3: INVENTORY INTELLIGENCE
        html.Div([
            html.H2("📦 Inventory Intelligence", style={'color': '#718096'}),
            html.Div([
                html.Div([html.Label("Stock Qty Col:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
                html.Div([html.Label("Product Name:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='inventory-kpi-container', style={'marginBottom': '20px'}),
            html.Div(id='inventory-alerts-output'),
            dcc.Graph(id='inventory-graph')
        ], style={'padding': '30px', 'backgroundColor': '#fff', 'borderRadius': '15px',
                  'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}),

    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'paddingBottom': '100px'})
], style={'fontFamily': 'Inter, sans-serif', 'backgroundColor': '#f7fafc'})


# --- 4. Callbacks ---

@app.callback(
    [Output('stored-labor-data', 'data'), Output('stored-sales-data', 'data'), Output('stored-inventory-data', 'data')],
    [Input('upload-data', 'contents'), Input('reset-btn', 'n_clicks')],
    [State('upload-data', 'filename'), State('stored-labor-data', 'data'),
     State('stored-sales-data', 'data'), State('stored-inventory-data', 'data')]
)
def handle_uploads(contents, reset_clicks, filenames, l_js, s_js, i_js):
    ctx = dash.callback_context
    if not ctx.triggered: return l_js, s_js, i_js

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == 'reset-btn': return None, None, None
    if not contents: return l_js, s_js, i_js

    for c, f in zip(contents, filenames):
        if 'labor' in f.lower():
            l_js = parse_contents(c, f)
        elif 'sales' in f.lower():
            s_js = parse_contents(c, f)
        elif 'inventory' in f.lower():
            i_js = parse_contents(c, f)
    return l_js, s_js, i_js


@app.callback(
    [Output('sales-col', 'options'), Output('cust-col', 'options'), Output('wage-col', 'options'),
     Output('start-col', 'options'), Output('end-col', 'options'), Output('inv-stock-col', 'options'),
     Output('inv-name-col', 'options')],
    [Input('stored-sales-data', 'data'), Input('stored-labor-data', 'data'), Input('stored-inventory-data', 'data')]
)
def sync_dropdowns(s_js, l_js, i_js):
    s_df, l_df, i_df = safe_load_df(s_js), safe_load_df(l_js), safe_load_df(i_js)
    return [[{'label': c, 'value': c} for c in df.columns] for df in [s_df, s_df, l_df, l_df, l_df, i_df, i_df]]


@app.callback(
    [Output('topline-stats', 'children'), Output('sales-kpi-cards', 'children'),
     Output('revenue-trend-graph', 'figure'), Output('customer-pareto-graph', 'figure')],
    [Input('stored-sales-data', 'data'), Input('sales-col', 'value'), Input('cust-col', 'value'),
     Input('cogs-pct', 'value'), Input('fixed-costs', 'value')]
)
def update_sales_pillar(js, rev, cust, cogs, target):
    if not js or not rev or not cust: raise exceptions.PreventUpdate
    df = safe_load_df(js)
    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
    total_rev = df[rev].sum()
    gp = total_rev * (1 - (cogs / 100))

    topline = [
        html.Div([html.Small("TOTAL REVENUE"), html.H2(f"${total_rev:,.0f}")],
                 style={'flex': '1', 'backgroundColor': '#48bb78', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
        html.Div([html.Small("GROSS PROFIT"), html.H2(f"${gp:,.0f}")],
                 style={'flex': '1', 'backgroundColor': '#38a169', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'})
    ]

    counts = df[cust].value_counts()
    clv = total_rev / len(counts) if len(counts) > 0 else 0
    retention = (len(counts[counts > 1]) / len(counts)) * 100 if len(counts) > 0 else 0
    be_pct = (total_rev / target) * 100 if target > 0 else 100

    kpi_cards = html.Div([
        html.Div([
            html.Div([html.Small("AVG CUSTOMER VALUE (CLV)"), html.H3(f"${clv:,.2f}", style={'color': '#38a169'})],
                     style={'flex': '1'}),
            html.Div([html.Small("RETENTION"), html.H3(f"{retention:.1f}%", style={'color': '#5a67d8'})],
                     style={'flex': '1'}),
            html.Div([html.Small("BREAK-EVEN"), html.H3(f"{be_pct:.1f}%")], style={'flex': '1.5'})
        ], style={'display': 'flex', 'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#fff',
                  'borderRadius': '12px', 'border': '1px solid #edf2f7'})
    ])

    date_col = df.select_dtypes(include=['datetime64']).columns[0]
    trend_df = df.set_index(date_col).resample('D')[rev].sum().reset_index()
    fig1 = px.line(trend_df, x=date_col, y=rev, title="Monthly Revenue vs Trend")
    fig1.update_layout(yaxis=dict(tickformat="$,"), template="plotly_white")

    p_df = df.groupby(cust)[rev].sum().sort_values(ascending=False).reset_index()
    p_df['cum_pct'] = 100 * (p_df[rev].cumsum() / p_df[rev].sum())
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    fig2.add_trace(go.Bar(x=p_df[cust], y=p_df[rev], name="Spend", marker_color='#5a67d8'), secondary_y=False)
    fig2.add_trace(go.Scatter(x=p_df[cust], y=p_df['cum_pct'], name="Cum %", line=dict(color='#f1c40f')),
                   secondary_y=True)
    fig2.update_layout(yaxis=dict(tickformat="$,"), template="plotly_white")

    return topline, kpi_cards, fig1, fig2


@app.callback(
    [Output('labor-kpis', 'children'), Output('chef-summary-output', 'children'),
     Output('labor-hourly-graph', 'figure')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'), Input('wage-col', 'value'),
     Input('start-col', 'value'), Input('end-col', 'value'), Input('sales-col', 'value'),
     Input('labor-threshold', 'value')]
)
def update_labor_pillar(l_js, s_js, wage, start, end, rev_col, threshold):
    l_df, s_df = safe_load_df(l_js), safe_load_df(s_js)
    if l_df.empty or not all([wage, start, end]):
        return "", "Upload Labor Data to see analysis.", go.Figure()

    hourly_labor = distribute_wages_hourly(l_df, wage, start, end)
    total_labor_cost = hourly_labor['Spent'].sum()
    total_labor_hours = hourly_labor['Hours_Count'].sum()

    total_revenue = 0
    total_transactions = 0
    if not s_df.empty and rev_col:
        s_df[rev_col] = pd.to_numeric(s_df[rev_col].astype(str).str.replace('[$,]', '', regex=True),
                                      errors='coerce').fillna(0)
        total_revenue = s_df[rev_col].sum()
        total_transactions = len(s_df)

    labor_pct = (total_labor_cost / total_revenue * 100) if total_revenue > 0 else 0
    splh = total_revenue / total_labor_hours if total_labor_hours > 0 else 0
    tplh = total_transactions / total_labor_hours if total_labor_hours > 0 else 0
    priority_savings = max(0, total_labor_cost - (total_revenue * (threshold / 100)))

    kpis = [
        html.Div([html.Small("LABOR SPEND"), html.H3(f"${total_labor_cost:,.2f}")],
                 style={'flex': '1', 'minWidth': '150px', 'backgroundColor': '#5a67d8', 'color': 'white',
                        'padding': '20px', 'borderRadius': '12px'}),
        html.Div([html.Small("LABOR %"), html.H3(f"{labor_pct:.1f}%")],
                 style={'flex': '1', 'minWidth': '150px', 'backgroundColor': '#4c51bf', 'color': 'white',
                        'padding': '20px', 'borderRadius': '12px'}),
        html.Div([html.Small("SALES PER HR (SPLH)"), html.H3(f"${splh:,.2f}")],
                 style={'flex': '1', 'minWidth': '150px', 'backgroundColor': '#48bb78', 'color': 'white',
                        'padding': '20px', 'borderRadius': '12px'}),
        html.Div([html.Small("TXNS PER HR (TPLH)"), html.H3(f"{tplh:.1f}")],
                 style={'flex': '1', 'minWidth': '150px', 'backgroundColor': '#38a169', 'color': 'white',
                        'padding': '20px', 'borderRadius': '12px'}),
        html.Div([html.Small("PRIORITY SAVINGS"), html.H3(f"${priority_savings:,.2f}")],
                 style={'flex': '1', 'minWidth': '150px', 'backgroundColor': '#f56565', 'color': 'white',
                        'padding': '20px', 'borderRadius': '12px'})
    ]

    top_3_peaks = hourly_labor['Spent'].nlargest(3).values
    colors = ['#f56565' if val in top_3_peaks else '#5a67d8' for val in hourly_labor['Spent']]

    fig = go.Figure(data=[go.Bar(x=hourly_labor['Hour'], y=hourly_labor['Spent'], marker_color=colors)])
    fig.update_layout(title="Hourly Labor Spend (Peaks in Red)", xaxis_title="Hour of Day", yaxis=dict(tickformat="$,"),
                      template="plotly_white")

    summary = f"Productivity: ${splh:,.2f}/hr. Savings potential: ${priority_savings:,.2f}."
    return kpis, summary, fig


@app.callback(
    [Output('inventory-alerts-output', 'children'), Output('inventory-graph', 'figure'),
     Output('inventory-kpi-container', 'children')],
    [Input('stored-inventory-data', 'data'), Input('inv-stock-col', 'value'), Input('inv-name-col', 'value'),
     Input('reorder-threshold', 'value')]
)
def update_inventory_pillar(i_js, stock_col, name_col, reorder_pt):
    if not i_js or not all([stock_col, name_col]): return html.Div("Upload inventory data."), go.Figure(), ""
    i_df = safe_load_df(i_js)
    i_df[stock_col] = pd.to_numeric(i_df[stock_col], errors='coerce').fillna(0)
    total_val = i_df[stock_col].sum()

    kpi_card = html.Div([
        html.Small("TOTAL INVENTORY VALUE", style={'color': '#718096', 'fontWeight': 'bold'}),
        html.H3(f"${total_val:,.2f}", style={'margin': '5px 0 0 0', 'color': '#2d3748'})
    ], style={'padding': '20px', 'backgroundColor': '#edf2f7', 'borderRadius': '12px', 'width': 'fit-content',
              'borderLeft': '5px solid #718096'})

    reorder_val = float(reorder_pt) if reorder_pt else 0
    low_stock_df = i_df[i_df[stock_col] < reorder_val]
    alert_content = [
        html.H3(f"⚠️ {len(low_stock_df)} LOW STOCK ALERTS", style={'color': '#e53e3e'}),
        html.Ul([html.Li(f"{row[name_col]}: {row[stock_col]} remaining") for _, row in low_stock_df.iterrows()])
    ]

    fig = go.Figure(data=[go.Bar(x=i_df[name_col], y=i_df[stock_col], marker_color='#718096')])
    fig.add_hline(y=reorder_val, line_dash="dash", line_color="#e53e3e", annotation_text="REORDER POINT")
    fig.update_layout(title="Current Stock Levels", yaxis=dict(tickformat="$,"), template="plotly_white")

    return alert_content, fig, kpi_card


if __name__ == '__main__':
    app.run(debug=True)