import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, callback_context

# --- 1. App Setup ---
app = dash.Dash(__name__, title="StockPilotDev v3.9.11 | 2026 Strategy Suite")
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


def append_data(existing_json, new_json):
    if not existing_json: return new_json
    return pd.concat([safe_load_df(existing_json), safe_load_df(new_json)], axis=0, ignore_index=True).to_json(
        date_format='iso', orient='split')


def distribute_wages_hourly(df, wage_col, start_col, end_col):
    hourly_costs, overtime_alerts = [], []
    for _, row in df.iterrows():
        try:
            start, end = row[start_col], row[end_col]
            total_wage, duration = row[wage_col], (end - start).total_seconds() / 3600
            if duration <= 0: continue
            wage_per_h = total_wage / duration
            if duration > 8:
                overtime_alerts.append(
                    {'time': start.strftime('%m/%d %I%p'), 'cost': (wage_per_h * 1.5) * (duration - 8)})
            curr = start
            while curr < end:
                next_h = curr.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
                seg_end = min(next_h, end)
                hourly_costs.append({'Hour': curr.hour, 'Spent': (seg_end - curr).total_seconds() / 3600 * wage_per_h})
                curr = next_h
        except:
            continue
    res = pd.DataFrame(hourly_costs)
    return res.groupby('Hour')['Spent'].sum().reset_index(), overtime_alerts


# --- 3. App Layout ---
app.layout = html.Div([
    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),

    html.Div([
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9)",
                style={'color': '#ffffff', 'margin': '0', 'fontWeight': '300'}),
        html.P("2026 SMB Command Center | Sales, Labor & Inventory", style={'color': '#cbd5e0'})
    ], style={'backgroundColor': '#2d3748', 'padding': '40px 20px', 'textAlign': 'center',
              'borderRadius': '0 0 20px 20px'}),

    html.Div([
        html.Div([
            dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']), multiple=True,
                       style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                              'borderStyle': 'dashed', 'borderRadius': '10px', 'textAlign': 'center',
                              'backgroundColor': '#fff', 'color': '#718096'}),
            html.Button("Reset Session", id="reset-btn",
                        style={'backgroundColor': '#e53e3e', 'color': 'white', 'padding': '10px 25px',
                               'borderRadius': '8px', 'border': 'none', 'marginTop': '15px', 'cursor': 'pointer'})
        ], style={'margin': '30px auto', 'maxWidth': '800px', 'textAlign': 'center'}),

        # PILLAR 1: SALES
        html.Div([
            html.H2("📈 Sales & Financials", style={'color': '#38a169', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Revenue Col:"), dcc.Dropdown(id='sales-col')], style={'flex': '1'}),
                html.Div([html.Label("Cust ID Col:"), dcc.Dropdown(id='cust-col')], style={'flex': '1'}),
                html.Div([html.Label("Est. COGS %:"), dcc.Input(id='cogs-pct', type='number', value=30)],
                         style={'flex': '0.5'}),
                html.Div([html.Label("Monthly Target:"), dcc.Input(id='fixed-costs', type='number', value=5000)],
                         style={'flex': '0.7'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='topline-stats', style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            html.Div(id='sales-kpi-cards'),
            html.Div([
                html.Div([dcc.Loading(dcc.Graph(id='sales-trend-graph', style={'height': '450px'}))],
                         style={'flex': '1'}),
                html.Div([dcc.Loading(dcc.Graph(id='customer-share-graph', style={'height': '450px'}))],
                         style={'flex': '1'})
            ], style={'display': 'flex', 'gap': '20px'})
        ], style={'padding': '30px', 'marginBottom': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px',
                  'backgroundColor': '#fff'}),

        # PILLAR 2: LABOR
        html.Div([
            html.H2("👥 Labor Productivity", style={'color': '#5a67d8', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("Start Time:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("End Time:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
                html.Div([html.Label("Labor Cap %:"), dcc.Input(id='labor-threshold', type='number', value=30)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div([
                html.Div([html.Small("TOTAL LABOR SPEND"), html.H3(id='total-labor-text')],
                         style={'flex': '1', 'backgroundColor': '#5a67d8', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("LABOR % OF SALES"), html.H3(id='labor-pct-text')],
                         style={'flex': '1', 'backgroundColor': '#4c51bf', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("REVENUE PER LABOR HOUR"), html.H3(id='rplh-text')],
                         style={'flex': '1', 'backgroundColor': '#3182ce', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("PRIORITY SAVINGS"), html.H3(id='potential-savings-text')],
                         style={'flex': '1', 'backgroundColor': '#f56565', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
            ], style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            html.Div(id='monday-summary-box',
                     style={'padding': '20px', 'backgroundColor': '#f7fafc', 'borderRadius': '12px',
                            'borderLeft': '5px solid #5a67d8'}),
            html.Div(id='labor-leak-alerts'),
            dcc.Loading(dcc.Graph(id='labor-hourly-graph', style={'height': '450px'}))
        ], style={'padding': '30px', 'marginBottom': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px',
                  'backgroundColor': '#fff'}),

        # PILLAR 3: INVENTORY
        html.Div([
            html.H2("📦 Inventory Intelligence",
                    style={'color': '#718096', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Stock Qty Col:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
                html.Div([html.Label("Product Name:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
                html.Div([html.Label("Unit Cost Col (Optional):"), dcc.Dropdown(id='inv-cost-col')],
                         style={'flex': '1'}),
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div([
                html.Div([html.Small("TOTAL INV VALUE"), html.H3(id='inv-value-text')],
                         style={'flex': '1', 'backgroundColor': '#718096', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("STOCK-TO-SALES RATIO"), html.H3(id='stock-sales-ratio-text')],
                         style={'flex': '1', 'backgroundColor': '#4a5568', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("EST. TURNOVER RATE"), html.H3(id='turnover-rate-text')],
                         style={'flex': '1', 'backgroundColor': '#2d3748', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("LOW STOCK ITEMS"), html.H3(id='low-stock-count-text')],
                         style={'flex': '1', 'backgroundColor': '#f56565', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
            ], style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            dcc.Loading(dcc.Graph(id='inventory-graph', style={'height': '450px'})),
            html.Div([
                html.Button("📥 Generate Reorder List", id="btn-reorder-list",
                            style={'backgroundColor': '#2d3748', 'color': 'white', 'padding': '10px 20px',
                                   'borderRadius': '8px', 'border': 'none', 'marginTop': '10px', 'cursor': 'pointer'}),
                dcc.Download(id="download-reorder-list")
            ], style={'textAlign': 'right'})
        ], style={'padding': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px', 'backgroundColor': '#fff'})
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'paddingBottom': '100px'})
], style={'fontFamily': 'Inter, sans-serif', 'backgroundColor': '#f7fafc', 'minHeight': '100vh'})


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
            temp_df = safe_load_df(js)
            cols, fn = [col.lower() for col in temp_df.columns], n.lower()
            if any(k in fn for k in ['labor', 'wage', 'payroll']) or any(k in cols for k in ['wage', 'clock']):
                labor = append_data(labor, js)
            elif any(k in fn for k in ['inv', 'stock']) or any(k in cols for k in ['stock', 'qty']):
                inv = append_data(inv, js)
            else:
                sales = append_data(sales, js)
    return labor, sales, inv


@app.callback(
    [Output('sales-col', 'options'), Output('cust-col', 'options'), Output('wage-col', 'options'),
     Output('start-col', 'options'), Output('end-col', 'options'), Output('inv-stock-col', 'options'),
     Output('inv-name-col', 'options'), Output('inv-cost-col', 'options')],
    [Input('stored-sales-data', 'data'), Input('stored-labor-data', 'data'), Input('stored-inventory-data', 'data')]
)
def sync_dropdowns(s_js, l_js, i_js):
    s_df, l_df, i_df = safe_load_df(s_js), safe_load_df(l_js), safe_load_df(i_js)
    return [[{'label': c, 'value': c} for c in df.columns] for df in [s_df, s_df, l_df, l_df, l_df, i_df, i_df, i_df]]


@app.callback(
    [Output('topline-stats', 'children'), Output('sales-kpi-cards', 'children'), Output('sales-trend-graph', 'figure'),
     Output('customer-share-graph', 'figure')],
    [Input('stored-sales-data', 'data'), Input('sales-col', 'value'), Input('cust-col', 'value'),
     Input('fixed-costs', 'value'), Input('cogs-pct', 'value')],
    prevent_initial_call=True
)
def update_sales(js, rev, cust, f_costs, cogs_pct):
    if not js or rev is None or cust is None: raise exceptions.PreventUpdate
    df = safe_load_df(js)
    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
    total_rev = df[rev].sum()
    avg_ticket = total_rev / len(df) if len(df) > 0 else 0
    gross_profit = total_rev * (1 - (cogs_pct / 100))
    net_profit = gross_profit - (f_costs or 0)
    topline = [
        html.Div([html.Small("TOTAL REVENUE"), html.H2(f"${total_rev:,.0f}")],
                 style={'flex': '1', 'backgroundColor': '#48bb78', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
        html.Div([html.Small("AVG TOTAL TICKET"), html.H2(f"${avg_ticket:,.2f}")],
                 style={'flex': '1', 'backgroundColor': '#38a169', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
        html.Div([html.Small("NET PROFIT"), html.H2(f"${net_profit:,.0f}")],
                 style={'flex': '1', 'backgroundColor': '#2f855a', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'})
    ]
    df['Date'] = pd.to_datetime(df['Date'])
    monthly_df = df.set_index('Date').resample('ME')[rev].sum().reset_index()
    fig1 = px.line(monthly_df, x='Date', y=rev, title="Monthly Sales Trend", markers=True,
                   color_discrete_sequence=['#38a169'])
    cust_rev = df.groupby(cust)[rev].sum().reset_index()
    fig2 = px.pie(cust_rev.nlargest(10, rev), values=rev, names=cust, hole=0.4, title="Top 10 Customers Share")
    counts = df[cust].value_counts()
    ret = (len(counts[counts > 1]) / len(counts) * 100) if not counts.empty else 0
    kpi_cards = html.Div([html.Small("RETENTION RATE: "), html.Strong(f"{ret:.1f}%")],
                         style={'padding': '10px', 'textAlign': 'center'})
    return topline, kpi_cards, fig1, fig2


@app.callback(
    [Output('labor-hourly-graph', 'figure'), Output('labor-leak-alerts', 'children'),
     Output('total-labor-text', 'children'), Output('labor-pct-text', 'children'), Output('rplh-text', 'children'),
     Output('potential-savings-text', 'children'), Output('monday-summary-box', 'children')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'), Input('wage-col', 'value'),
     Input('start-col', 'value'), Input('end-col', 'value'), Input('sales-col', 'value'),
     Input('labor-threshold', 'value')],
    prevent_initial_call=True
)
def update_labor_enhanced(l_js, s_js, wage, start, end, rev_col, threshold):
    if not l_js or not all([wage, start, end]): raise exceptions.PreventUpdate
    l_df, s_df = safe_load_df(l_js), safe_load_df(s_js)
    hourly_labor, ot_leaks = distribute_wages_hourly(l_df, wage, start, end)

    # Financial Stats
    total_spent = hourly_labor['Spent'].sum()
    total_labor_hours = (pd.to_datetime(l_df[end]) - pd.to_datetime(l_df[start])).dt.total_seconds().sum() / 3600
    total_rev = pd.to_numeric(s_df[rev_col].astype(str).str.replace('[$,]', '', regex=True),
                              errors='coerce').sum() if not s_df.empty else 0
    rplh = total_rev / total_labor_hours if total_labor_hours > 0 else 0
    labor_pct = (total_spent / total_rev * 100) if total_rev > 0 else 0

    # Priority Color Logic
    bar_colors = ['#5a67d8'] * len(hourly_labor)
    leak_alerts = ""
    if not s_df.empty:
        s_df['Hour'] = s_df['Date'].dt.hour
        h_sales = s_df.groupby('Hour')[rev_col].sum().reset_index()
        comp = pd.merge(hourly_labor, h_sales, on='Hour', how='inner')
        if not comp.empty:
            comp['Ratio'] = (comp['Spent'] / comp[rev_col]) * 100
            top_3 = comp.nlargest(3, 'Ratio')['Hour'].tolist()
            bar_colors = ['#f56565' if h in top_3 else '#5a67d8' for h in hourly_labor['Hour']]
            leaks = comp[comp['Ratio'] > (threshold or 30)]
            if not leaks.empty:
                leak_alerts = html.Div(
                    [html.Strong("⚠️ LABOR LEAK: "), f"Ratio > {threshold}% at {leaks['Hour'].tolist()}"],
                    style={'color': '#c53030', 'padding': '10px'})

    # Graph
    fig = go.Figure()
    fig.add_trace(go.Bar(x=hourly_labor['Hour'], y=hourly_labor['Spent'], name='Labor Cost', marker_color=bar_colors))
    if not s_df.empty:
        fig.add_trace(
            go.Scatter(x=h_sales['Hour'], y=h_sales[rev_col], name='Revenue', line=dict(color='#38a169', width=3),
                       yaxis='y2'))
    fig.update_layout(yaxis2=dict(overlaying='y', side='right'), template="plotly_white", height=450)

    summary = html.Div(
        [html.H4("Chef's Strategy"), html.P(f"Labor is {labor_pct:.1f}% of sales. Revenue per hour is ${rplh:.2f}.")])
    return fig, leak_alerts, f"${total_spent:,.2f}", f"{labor_pct:.1f}%", f"${rplh:.2f}", f"${total_spent * 0.1:,.2f}", summary


@app.callback(
    [Output('inv-value-text', 'children'), Output('stock-sales-ratio-text', 'children'),
     Output('turnover-rate-text', 'children'), Output('low-stock-count-text', 'children'),
     Output('inventory-graph', 'figure')],
    [Input('stored-inventory-data', 'data'), Input('stored-sales-data', 'data'), Input('inv-stock-col', 'value'),
     Input('inv-name-col', 'value'), Input('inv-cost-col', 'value'), Input('sales-col', 'value'),
     Input('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def update_inventory_pro(i_js, s_js, stock, name, cost, s_col, thresh):
    if not i_js or stock is None: raise exceptions.PreventUpdate
    inv_df, s_df = safe_load_df(i_js), safe_load_df(s_js)
    inv_df[stock] = pd.to_numeric(inv_df[stock], errors='coerce').fillna(0)

    # Financial Value
    if cost:
        inv_df[cost] = pd.to_numeric(inv_df[cost].astype(str).str.replace('[$,]', '', regex=True),
                                     errors='coerce').fillna(0)
        val = (inv_df[stock] * inv_df[cost]).sum()
    else:
        val = inv_df[stock].sum() * 10  # Fallback cost

    total_rev = pd.to_numeric(s_df[s_col].astype(str).str.replace('[$,]', '', regex=True),
                              errors='coerce').sum() if not s_df.empty else 0
    ssr = val / total_rev if total_rev > 0 else 0
    turn = total_rev / val if val > 0 else 0
    low = len(inv_df[inv_df[stock] < float(thresh or 20)])

    fig = px.bar(inv_df.nlargest(15, stock), x=name, y=stock, title="Inventory Levels")
    fig.add_hline(y=float(thresh or 20), line_dash="dash", line_color="red")
    return f"${val:,.2f}", f"{ssr:.2f}x", f"{turn:.1f}x", f"{low}", fig


if __name__ == '__main__':
    app.run(debug=True)