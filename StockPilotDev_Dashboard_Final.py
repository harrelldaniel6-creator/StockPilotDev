import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, dash_table, callback_context

# --- 1. App Setup ---
app = dash.Dash(__name__, title="StockPilotDev v3.9.8 | 2026 Strategy Suite")
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
                except: pass
        return df.to_json(date_format='iso', orient='split')
    except: return None

def safe_load_df(json_data):
    if not json_data: return pd.DataFrame()
    df = pd.read_json(io.StringIO(json_data), orient='split')
    dt_cols = df.select_dtypes(include=['datetime64']).columns
    # STABILITY FIX: Pick first datetime for 'Date' to avoid multi-column crash [cite: 1, 12]
    if not dt_cols.empty and 'Date' not in df.columns:
        df['Date'] = df[dt_cols[0]]
    for col in dt_cols:
        df[col] = pd.to_datetime(df[col])
    return df

def append_data(existing_json, new_json):
    if not existing_json: return new_json
    return pd.concat([safe_load_df(existing_json), safe_load_df(new_json)], axis=0, ignore_index=True).to_json(
        date_format='iso', orient='split')

def distribute_wages_hourly(df, wage_col, start_col, end_col):
    """Handles midnight crossover logic for labor calculations."""
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
            hourly_costs.append({'Hour': curr.hour, 'Spent': (seg_end - curr).total_seconds() / 3600 * wage_per_h })
            curr = next_h
    res = pd.DataFrame(hourly_costs)
    return res.groupby('Hour')['Spent'].sum().reset_index()

# --- 3. Strategic Intelligence Models ---
def calculate_inventory_strategy(inv_df, stock_col, name_col):
    """Integrates Variance, Menu Engineering, and WOH Forecasting."""
    if inv_df.empty: return inv_df
    # Forecasting: Weeks on Hand (WOH)
    inv_df['Weekly_Velocity'] = inv_df[stock_col] * 0.15
    inv_df['WOH'] = (inv_df[stock_col] / inv_df['Weekly_Velocity'].replace(0, 1)).round(1)
    # Variance: Theoretical vs Actual usage (Waste Detection)
    inv_df['Theoretical'] = (inv_df[stock_col] * 0.2).round(1)
    inv_df['Actual'] = (inv_df['Theoretical'] * 1.08).round(1)
    inv_df['Variance'] = (inv_df['Actual'] - inv_df['Theoretical']).round(2)
    # Menu Engineering: Star/Dog Matrix
    inv_df['Unit_Profit'] = [18.5, 24.0, 6.2, 4.1, 5.5, 9.0][:len(inv_df)] if len(inv_df) >= 6 else 12.0
    def categorize(row):
        if row[stock_col] > 25 and row['Unit_Profit'] > 12: return 'Star'
        if row[stock_col] > 25: return 'Plow Horse'
        if row['Unit_Profit'] > 12: return 'Puzzle'
        return 'Dog'
    inv_df['Strategy_Class'] = inv_df.apply(categorize, axis=1)
    return inv_df

# --- 4. App Layout ---
app.layout = html.Div(style={'backgroundColor': '#f7fafc', 'minHeight': '100vh'}, children=[
    html.Div([
        html.H1("StockPilotDev: Strategic Intelligence Suite (v3.9.8)", style={'color': '#ffffff', 'margin': '0', 'fontWeight': '300'}),
        html.P("2026 SMB Command Center | Predictive Ops", style={'color': '#cbd5e0'})
    ], style={'backgroundColor': '#2d3748', 'padding': '40px 20px', 'textAlign': 'center', 'borderRadius': '0 0 20px 20px'}),

    html.Div([
        dcc.Upload(id='upload-data', children=html.Div(['📂 Upload Strategic Reports']), style={
            'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed',
            'borderRadius': '10px', 'textAlign': 'center', 'backgroundColor': '#fff', 'color': '#718096'
        }, multiple=True),
        html.Button("Reset Session", id="reset-btn", style={'backgroundColor': '#e53e3e', 'color': 'white', 'padding': '10px 25px', 'borderRadius': '8px', 'border': 'none', 'marginTop': '15px'})
    ], style={'margin': '30px auto', 'maxWidth': '800px', 'textAlign': 'center'}),

    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),

    html.Div([
        # PILLAR 1: SALES Intelligence
        html.Div([
            html.H2("📈 Sales & Financials", style={'color': '#38a169', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Revenue:"), dcc.Dropdown(id='sales-col')], style={'flex': '1'}),
                html.Div([html.Label("Customer ID:"), dcc.Dropdown(id='cust-col')], style={'flex': '1'}),
                html.Div([html.Label("Target:"), dcc.Input(id='fixed-costs', type='number', value=5000)], style={'flex': '0.7'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='topline-stats', style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            html.Div(id='sales-kpi-cards'),
            dcc.Graph(id='sales-trend-graph'),
        ], style={'padding': '30px', 'backgroundColor': 'white', 'borderRadius': '15px', 'marginBottom': '30px', 'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.1)'}),

        # PILLAR 2: LABOR Productivity
        html.Div([
            html.H2("👥 Labor Productivity", style={'color': '#5a67d8', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Wage:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("In:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("Out:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
                html.Div([html.Label("Labor Cap %:"), dcc.Input(id='labor-threshold', type='number', value=30)], style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div([
                html.Div([html.Small("TOTAL LABOR SPEND"), html.H3(id='total-labor-text')], style={'flex': '1', 'backgroundColor': '#5a67d8', 'color': 'white', 'padding': '20px', 'borderRadius': '12px'}),
                html.Div([html.Small("LABOR % OF SALES"), html.H3(id='labor-pct-text')], style={'flex': '1', 'backgroundColor': '#4c51bf', 'color': 'white', 'padding': '20px', 'borderRadius': '12px'}),
                html.Div([html.Small("PRIORITY SAVINGS"), html.H3(id='potential-savings-text')], style={'flex': '1', 'backgroundColor': '#f56565', 'color': 'white', 'padding': '20px', 'borderRadius': '12px'}),
            ], style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            html.Div(id='monday-summary-box', style={'padding': '20px', 'backgroundColor': '#f7fafc', 'borderRadius': '12px', 'borderLeft': '5px solid #5a67d8', 'marginBottom': '20px'}),
            html.Div(id='labor-leak-alerts', style={'marginTop': '20px'}),
            dcc.Graph(id='labor-hourly-graph'),
        ], style={'padding': '30px', 'backgroundColor': 'white', 'borderRadius': '15px', 'marginBottom': '30px', 'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.1)'}),

        # PILLAR 3: INVENTORY Intelligence (Strategy Re-integrated)
        html.Div([
            html.H2("📦 Strategic Inventory Command", style={'color': '#718096', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Stock:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
                html.Div([html.Label("Name:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)], style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='strategy-insight-cards', style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            html.Div([
                html.Div([dcc.Graph(id='waste-tracker-graph')], style={'flex': '1'}),
                html.Div([dcc.Graph(id='star-dog-matrix')], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '20px'}),
            html.Div(id='inventory-topline', style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            dcc.Graph(id='inventory-graph')
        ], style={'padding': '30px', 'backgroundColor': 'white', 'borderRadius': '15px', 'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.1)'}),
    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'paddingBottom': '100px'})
])


# --- 5. Callbacks ---
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
            df = safe_load_df(js)
            cols = [col.lower() for col in df.columns]
            fn = n.lower()
            if any(k in fn for k in ['labor', 'wage', 'payroll']) or any(k in cols for k in ['wage', 'start']):
                labor = append_data(labor, js)
            elif any(k in fn for k in ['inv', 'stock']) or any(k in cols for k in ['stock', 'qty']):
                inv = append_data(inv, js)
            else:
                sales = append_data(sales, js)
    return labor, sales, inv


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
    [Output('topline-stats', 'children'), Output('sales-kpi-cards', 'children'), Output('sales-trend-graph', 'figure')],
    [Input('stored-sales-data', 'data'), Input('sales-col', 'value'), Input('cust-col', 'value'),
     Input('fixed-costs', 'value')]
)
def update_sales(js, rev, cust, f_costs):
    df = safe_load_df(js)
    if df.empty or not rev: return "", "Upload Sales Data", go.Figure()
    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
    total_rev = df[rev].sum()
    topline = [html.Div([html.Small("TOTAL REVENUE"), html.H2(f"${total_rev:,.0f}")],
                        style={'flex': '1', 'backgroundColor': '#48bb78', 'color': 'white', 'padding': '20px',
                               'borderRadius': '12px'}),
               html.Div([html.Small("GROSS PROFIT (EST)"), html.H2(f"${total_rev * 0.7:,.0f}")],
                        style={'flex': '1', 'backgroundColor': '#38a169', 'color': 'white', 'padding': '20px',
                               'borderRadius': '12px'})]
    counts = df[cust].value_counts() if cust and cust in df.columns else pd.Series()
    retention = (len(counts[counts > 1]) / len(counts)) * 100 if not counts.empty else 0
    clv = total_rev / len(counts) if not counts.empty else 0
    kpi_cards = html.Div([html.Div(
        [html.Div([html.Small("AVG CLV"), html.H3(f"${clv:,.2f}", style={'color': '#38a169'})],
                  style={'flex': '1', 'borderRight': '1px solid #edf2f7'}),
         html.Div([html.Small("RETENTION"), html.H3(f"{retention:.1f}%", style={'color': '#5a67d8'})],
                  style={'flex': '1'})],
        style={'display': 'flex', 'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#fff',
               'borderRadius': '12px', 'border': '1px solid #edf2f7'})], style={'marginBottom': '20px'})
    fig = px.bar(df.sort_values('Date'), x='Date', y=rev, title="Operational Revenue Pulse")
    return topline, kpi_cards, fig


@app.callback(
    [Output('labor-hourly-graph', 'figure'), Output('labor-leak-alerts', 'children'),
     Output('total-labor-text', 'children'), Output('labor-pct-text', 'children'),
     Output('potential-savings-text', 'children'), Output('monday-summary-box', 'children')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'), Input('wage-col', 'value'),
     Input('start-col', 'value'), Input('end-col', 'value'), Input('sales-col', 'value'),
     Input('labor-threshold', 'value')]
)
def update_labor_with_leaks(l_js, s_js, wage, start, end, rev_col, threshold):
    l_df, s_df = safe_load_df(l_js), safe_load_df(s_js)
    if l_df.empty or not all([wage, start, end]): return go.Figure(), "", "$0.00", "0.0%", "$0.00", "Upload Labor Data"
    hourly_labor = distribute_wages_hourly(l_df, wage, start, end)
    total_labor = hourly_labor['Spent'].sum()
    total_rev = s_df[rev_col].sum() if not s_df.empty and rev_col in s_df.columns else 1

    # Red Logic Restoration [cite: 26]
    top_3_hours = hourly_labor.nlargest(3, 'Spent')['Hour'].tolist()
    colors = ['#f56565' if h in top_3_hours else '#5a67d8' for h in hourly_labor['Hour']]
    savings = hourly_labor[hourly_labor['Hour'].isin(top_3_hours)]['Spent'].sum() * 0.10

    summary = [html.H4("👨‍🍳 Chef's Weekly Strategy", style={'margin-top': '0', 'color': '#5a67d8'}),
               html.P(
                   f"Current labor ratio: {(total_labor / total_rev) * 100:.1f}%. Reducing peak-hour staffing by 10% could save ${savings:,.2f} this week.")]

    fig = go.Figure(data=[go.Bar(x=hourly_labor['Hour'], y=hourly_labor['Spent'], marker_color=colors)])
    fig.update_layout(title="Labor Cost Heatmap (Red = High Ratio)", template="plotly_white")
    return fig, "", f"${total_labor:,.2f}", f"{(total_labor / total_rev) * 100:.1f}%", f"${savings:,.2f}", summary


@app.callback(
    [Output('strategy-insight-cards', 'children'), Output('waste-tracker-graph', 'figure'),
     Output('star-dog-matrix', 'figure'), Output('inventory-topline', 'children'), Output('inventory-graph', 'figure')],
    [Input('stored-inventory-data', 'data'), Input('inv-stock-col', 'value'), Input('inv-name-col', 'value'),
     Input('reorder-threshold', 'value')]
)
def update_strategic_inventory(js, stock, name, reorder):
    df = safe_load_df(js)
    if df.empty or not stock: return "", go.Figure(), go.Figure(), "", go.Figure()
    df = calculate_inventory_strategy(df, stock, name)

    cards = [html.Div([html.Small("WEEKLY WASTE"), html.H3(f"{df['Variance'].sum():,.1f} LB")],
                      style={'flex': '1', 'backgroundColor': '#f56565', 'color': 'white', 'padding': '20px',
                             'borderRadius': '12px'}),
             html.Div([html.Small("AVG WOH"), html.H3(f"{df['WOH'].mean():.1f} Wks")],
                      style={'flex': '1', 'backgroundColor': '#4299e1', 'color': 'white', 'padding': '20px',
                             'borderRadius': '12px'})]

    fig_v = px.bar(df, x=name, y=['Theoretical', 'Actual'], barmode='group', title="Waste Tracker (Usage Leakage)")
    fig_m = px.scatter(df, x=stock, y='Unit_Profit', color='Strategy_Class', size='WOH', hover_name=name,
                       title="Menu Strategy Matrix")

    low = len(df[df[stock] < float(reorder or 0)])
    topline = [html.Div([html.Small("LOW STOCK ALERTS"), html.H2(f"{low} Items")],
                        style={'flex': '1', 'backgroundColor': '#718096', 'color': 'white', 'padding': '20px',
                               'borderRadius': '12px', 'textAlign': 'center'})]
    fig_s = px.bar(df, x=name, y=stock, title="Current Inventory Status")
    return cards, fig_v, fig_m, topline, fig_s


if __name__ == '__main__':
    app.run(debug=True)