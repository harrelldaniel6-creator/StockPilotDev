import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, callback_context

# --- 1. App Setup ---
app = dash.Dash(__name__, title="StockPilotDev v3.9.14 | 2026 Strategy Suite")
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
        try:
            start, end = row[start_col], row[end_col]
            if pd.isna(start) or pd.isna(end): continue
            total_wage, duration = row[wage_col], (end - start).total_seconds() / 3600
            if duration <= 0: continue
            wage_per_h = total_wage / duration
            curr = start
            while curr < end:
                next_h = curr.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
                seg_end = min(next_h, end)
                hourly_costs.append({'Hour': curr.hour, 'Spent': (seg_end - curr).total_seconds() / 3600 * wage_per_h})
                curr = next_h
        except:
            continue
    res = pd.DataFrame(hourly_costs)
    if res.empty: return pd.DataFrame(columns=['Hour', 'Spent'])
    return res.groupby('Hour')['Spent'].sum().reset_index()


def calculate_inventory_health(inv_df, sales_df, stock_col, threshold):
    date_col = sales_df.select_dtypes(include=['datetime64']).columns[0]
    days_active = (sales_df[date_col].max() - sales_df[date_col].min()).days or 1
    daily_velocity = len(sales_df) / days_active
    inv_df['Daily_Burn'] = daily_velocity / len(inv_df)
    inv_df['Days_of_Cover'] = inv_df[stock_col] / inv_df['Daily_Burn'].replace(0, 0.001)

    def get_status(row):
        if row[stock_col] <= (threshold * 0.5): return 'CRITICAL'
        if row[stock_col] < threshold: return 'REORDER'
        return 'HEALTHY'

    inv_df['Status'] = inv_df.apply(get_status, axis=1)
    return inv_df


def route_by_score(df, labor, sales, inv):
    l_keys = {'wage', 'pay', 'employee', 'staff', 'clock', 'start', 'end', 'shift', 'labor', 'payroll'}
    i_keys = {'stock', 'qty', 'product', 'item', 'inventory', 'sku', 'reorder', 'count'}
    s_keys = {'revenue', 'sales', 'transaction', 'price', 'customer', 'ticket', 'total', 'receipt'}
    cols = [str(col).lower().replace('_', ' ').replace('-', ' ') for col in df.columns]
    js = df.to_json(date_format='iso', orient='split')
    l_score = len([k for k in l_keys if any(k in c for c in cols)])
    i_score = len([k for k in i_keys if any(k in c for c in cols)])
    s_score = len([k for k in s_keys if any(k in c for c in cols)])
    if l_score > i_score and l_score > s_score:
        return js, sales, inv
    elif i_score > l_score and i_score > s_score:
        return labor, sales, js
    else:
        return labor, js, inv


# --- 3. App Layout ---
app.layout = html.Div([
    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),
    html.Div([
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9.14)", style={'color': '#ffffff', 'margin': '0'}),
        html.P("2026 SMB Command Center | Sales, Labor & Inventory", style={'color': '#cbd5e0'})
    ], style={'backgroundColor': '#2d3748', 'padding': '40px 20px', 'textAlign': 'center',
              'borderRadius': '0 0 20px 20px'}),

    html.Div([
        html.Div([
            dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']), multiple=True,
                       style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                              'borderStyle': 'dashed', 'borderRadius': '10px', 'textAlign': 'center',
                              'backgroundColor': '#fff', 'margin': '20px 0'}),
            html.Button("Reset Session", id="reset-btn",
                        style={'backgroundColor': '#e53e3e', 'color': 'white', 'padding': '10px 25px',
                               'borderRadius': '8px', 'border': 'none', 'display': 'block', 'margin': '0 auto',
                               'cursor': 'pointer'})
        ], style={'maxWidth': '800px', 'margin': '0 auto'}),

        # PILLARS: Sales
        html.Div([
            html.H2("📈 Sales & Financials", style={'color': '#38a169'}),
            html.Div([
                html.Div([html.Label("Revenue Col:"), dcc.Dropdown(id='sales-col')], style={'flex': '1'}),
                html.Div([html.Label("Cust ID Col:"), dcc.Dropdown(id='cust-col')], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='topline-stats', style={'display': 'flex', 'gap': '15px', 'marginBottom': '25px'}),
            html.Div([
                dcc.Graph(id='sales-trend-graph', style={'flex': '1'}),
                dcc.Graph(id='customer-share-graph', style={'flex': '1'})
            ], style={'display': 'flex', 'gap': '20px'})
        ], style={'padding': '30px', 'backgroundColor': '#fff', 'borderRadius': '15px', 'margin': '20px auto',
                  'maxWidth': '1200px', 'border': '1px solid #e2e8f0'}),

        # PILLARS: Labor
        html.Div([
            html.H2("👥 Labor & Peak Efficiency", style={'color': '#5a67d8'}),
            html.Div([
                html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("Start Time:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("End Time:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='labor-kpi-container', style={'display': 'flex', 'gap': '15px', 'marginBottom': '25px'}),
            dcc.Graph(id='profitability-heatmap')
        ], style={'padding': '30px', 'backgroundColor': '#fff', 'borderRadius': '15px', 'margin': '20px auto',
                  'maxWidth': '1200px', 'border': '1px solid #e2e8f0'}),

        # PILLARS: Inventory
        html.Div([
            html.H2("📦 Inventory Intelligence", style={'color': '#718096'}),
            html.Div([
                html.Div([html.Label("Stock Qty Col:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
                html.Div([html.Label("Product Name:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
                html.Div([html.Label("Unit Cost Col:"), dcc.Dropdown(id='inv-cost-col')], style={'flex': '1'}),
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='inv-kpi-container', style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            dcc.Graph(id='inventory-graph'),
            html.H3("🚨 Dead Stock & Capital Risk", style={'marginTop': '30px', 'color': '#e53e3e'}),
            dcc.Graph(id='waste-analysis-graph'),
            html.Button("📥 Generate Reorder List", id="btn-reorder-list",
                        style={'marginTop': '20px', 'cursor': 'pointer'}),
            dcc.Download(id="download-reorder-list")
        ], style={'padding': '30px', 'borderRadius': '15px', 'backgroundColor': '#fff', 'margin': '20px auto',
                  'maxWidth': '1200px', 'border': '1px solid #e2e8f0'})
    ])
])


# --- 4. Callbacks ---
@app.callback(
    [Output('stored-labor-data', 'data'), Output('stored-sales-data', 'data'), Output('stored-inventory-data', 'data')],
    [Input('upload-data', 'contents'), Input('reset-btn', 'n_clicks')],
    [State('upload-data', 'filename'), State('stored-labor-data', 'data'), State('stored-sales-data', 'data'),
     State('stored-inventory-data', 'data')],
    prevent_initial_call=True
)
def master_intake(contents, reset, names, labor, sales, inv):
    if callback_context.triggered_id == 'reset-btn': return None, None, None
    if contents:
        for c, n in zip(contents, names):
            js = parse_contents(c, n)
            if js:
                df = safe_load_df(js)
                labor, sales, inv = route_by_score(df, labor, sales, inv)
    return labor, sales, inv


@app.callback(
    [Output('sales-col', 'options'), Output('cust-col', 'options'), Output('wage-col', 'options'),
     Output('start-col', 'options'), Output('end-col', 'options'), Output('inv-stock-col', 'options'),
     Output('inv-name-col', 'options'), Output('inv-cost-col', 'options')],
    [Input('stored-sales-data', 'data'), Input('stored-labor-data', 'data'), Input('stored-inventory-data', 'data')]
)
def sync_drops(s, l, i):
    dfs = [safe_load_df(x) for x in [s, l, i]]
    return [[{'label': c, 'value': c} for c in df.columns] for df in
            [dfs[0], dfs[0], dfs[1], dfs[1], dfs[1], dfs[2], dfs[2], dfs[2]]]


@app.callback(
    [Output('topline-stats', 'children'),
     Output('sales-trend-graph', 'figure'),
     Output('customer-share-graph', 'figure')],
    [Input('stored-sales-data', 'data'),
     Input('stored-labor-data', 'data'),
     Input('stored-inventory-data', 'data'),
     Input('sales-col', 'value'),
     Input('cust-col', 'value'),
     Input('inv-cost-col', 'value'),
     Input('inv-stock-col', 'value')],
    prevent_initial_call=True
)
def update_sales(s_js, l_js, i_js, rev, cust, cost_col, stock_col):
    if not s_js or not rev or not cust: raise exceptions.PreventUpdate
    df = safe_load_df(s_js)
    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
    total_rev = df[rev].sum()
    atv = total_rev / len(df) if not df.empty else 0

    total_labor = 0
    if l_js:
        df_l = safe_load_df(l_js)
        numeric_cols = df_l.select_dtypes(include=['number']).columns
        if not numeric_cols.empty:
            total_labor = df_l[numeric_cols[0]].sum()

    total_cogs = 0
    if i_js and cost_col and stock_col:
        df_i = safe_load_df(i_js)
        df_i[cost_col] = pd.to_numeric(df_i[cost_col].astype(str).str.replace('[$,]', '', regex=True),
                                       errors='coerce').fillna(0)
        total_cogs = (df_i[stock_col] * df_i[cost_col]).sum() * 0.3

    gross_margin = ((total_rev - total_cogs) / total_rev * 100) if total_rev > 0 else 0
    net_profit = ((total_rev - total_labor - total_cogs) / total_rev * 100) if total_rev > 0 else 0

    kpi_cards = [
        html.Div([html.Small("REVENUE"),
                  html.Abbr(html.H2(f"${total_rev:,.0f}"), title="Total gross sales. Goal: 5% monthly growth.")],
                 style={'backgroundColor': '#38a169', 'color': 'white', 'padding': '20px', 'borderRadius': '12px',
                        'flex': '1'}),
        html.Div([html.Small("AVG TRANSACTION"),
                  html.Abbr(html.H2(f"${atv:,.2f}"), title="Total Rev / Total Transactions. Goal: >$500.")],
                 style={'backgroundColor': '#2f855a', 'color': 'white', 'padding': '20px', 'borderRadius': '12px',
                        'flex': '1'}),
        html.Div([html.Small("GROSS MARGIN"),
                  html.Abbr(html.H2(f"{gross_margin:.1f}%"), title="Revenue minus Estimated COGS. Target: >40%.")],
                 style={'backgroundColor': '#276749', 'color': 'white', 'padding': '20px', 'borderRadius': '12px',
                        'flex': '1'}),
        html.Div([html.Small("NET PROFIT"),
                  html.Abbr(html.H2(f"{net_profit:.1f}%"), title="Profit after all Labor and COGS. Target: >15%.")],
                 style={'backgroundColor': '#22543d', 'color': 'white', 'padding': '20px', 'borderRadius': '12px',
                        'flex': '1'}),
    ]

    date_col = df.select_dtypes(include=['datetime64']).columns[0]
    df_monthly = df.set_index(date_col).resample('MS')[rev].sum().reset_index()
    fig1 = px.line(df_monthly, x=date_col, y=rev, title="Monthly Sales Trend (Aggregated)")
    fig1.update_layout(yaxis_tickprefix='$', yaxis_tickformat=',.0f', template="plotly_white")
    fig2 = px.pie(df.groupby(cust)[rev].sum().reset_index().nlargest(10, rev), values=rev, names=cust, hole=0.4,
                  title="Revenue Share by Customer")
    return kpi_cards, fig1, fig2


@app.callback(
    [Output('labor-kpi-container', 'children'), Output('profitability-heatmap', 'figure')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'), Input('wage-col', 'value'),
     Input('start-col', 'value'), Input('end-col', 'value'), Input('sales-col', 'value')],
    prevent_initial_call=True
)
def update_labor_logic(l_js, s_js, wage, start, end, rev_col):
    if not l_js or not all([wage, start, end]): raise exceptions.PreventUpdate
    l_df, s_df = safe_load_df(l_js), safe_load_df(s_js)
    hourly_labor = distribute_wages_hourly(l_df, wage, start, end)
    total_l = hourly_labor['Spent'].sum()

    total_s = 0
    if not s_df.empty and rev_col:
        s_df[rev_col] = pd.to_numeric(s_df[rev_col].astype(str).str.replace('[$,]', '', regex=True),
                                      errors='coerce').fillna(0)
        total_s = s_df[rev_col].sum()
        s_df['Hour'] = pd.to_datetime(s_df.iloc[:, 0]).dt.hour
        hourly_sales = s_df.groupby('Hour')[rev_col].sum().reset_index()
        merged = pd.merge(hourly_labor, hourly_sales, on='Hour', how='outer').fillna(0)
        rplh = total_s / (len(l_df) or 1)
        labor_pct = (total_l / total_s * 100) if total_s > 0 else 0
        fig = px.bar(merged, x='Hour', y=[rev_col, 'Spent'], barmode='group',
                     title="Profitability: Sales vs Labor Spend")

        # New Time formatting for X-Axis
        time_labels = {h: f"{h if h <= 12 and h != 0 else abs(h - 12)} {'AM' if h < 12 else 'PM'}" for h in range(24)}
        time_labels[0] = "12 AM"
        time_labels[12] = "12 PM"

        fig.update_layout(
            xaxis=dict(
                tickmode='array',
                tickvals=list(range(24)),
                ticktext=[time_labels[h] for h in range(24)]
            ),
            yaxis_tickprefix='$', yaxis_tickformat=',.2f', template="plotly_white"
        )
    else:
        rplh = 0;
        labor_pct = 0
        fig = px.bar(hourly_labor, x='Hour', y='Spent', title="Labor Cost Distribution")

    kpis = [
        html.Div(
            [html.Small("TOTAL LABOR SPEND"), html.Abbr(html.H3(f"${total_l:,.2f}"), title="Total gross wages paid.")],
            style={'flex': '1', 'backgroundColor': '#5a67d8', 'color': 'white', 'padding': '20px',
                   'borderRadius': '12px'}),
        html.Div([html.Small("LABOR % OF SALES"),
                  html.Abbr(html.H3(f"{labor_pct:.1f}%"), title="Wages as % of Revenue. Goal: <25%.")],
                 style={'flex': '1', 'backgroundColor': '#4c51bf', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
        html.Div([html.Small("REVENUE PER LABOR HOUR"),
                  html.Abbr(html.H3(f"${rplh:,.2f}"), title="Total Rev / Total Labor Hours. Target: >$100.")],
                 style={'flex': '1', 'backgroundColor': '#3182ce', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
    ]
    return kpis, fig


@app.callback(
    [Output('inv-kpi-container', 'children'),
     Output('inventory-graph', 'figure'), Output('waste-analysis-graph', 'figure')],
    [Input('stored-inventory-data', 'data'), Input('stored-sales-data', 'data'), Input('inv-stock-col', 'value'),
     Input('inv-name-col', 'value'), Input('inv-cost-col', 'value'), Input('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def unified_inventory_callback(inv_js, sales_js, stock, name, cost, thresh):
    if not inv_js or not stock or not name or not cost: raise exceptions.PreventUpdate
    inv_df, sales_df = safe_load_df(inv_js), safe_load_df(sales_js)
    inv_df[stock] = pd.to_numeric(inv_df[stock], errors='coerce').fillna(0)
    inv_df[cost] = pd.to_numeric(inv_df[cost].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(
        0)

    inv_df['Required_Qty'] = ((thresh or 20) * 1.5 - inv_df[stock]).clip(lower=0)
    inv_df['Restock_Cost'] = inv_df['Required_Qty'] * inv_df[cost]
    val = (inv_df[stock] * inv_df[cost]).sum()
    restock_total = inv_df['Restock_Cost'].sum()

    turnover = 0
    if not sales_df.empty:
        turnover = len(sales_df) / (val / 100) if val > 0 else 0
        inv_df = calculate_inventory_health(inv_df, sales_df, stock, thresh or 20)
        fig = px.bar(inv_df, x=name, y=stock, color='Status',
                     color_discrete_map={'CRITICAL': '#e53e3e', 'REORDER': '#ecc94b', 'HEALTHY': '#48bb78'},
                     title="Inventory Health Levels", text='Days_of_Cover')
        fig.update_traces(texttemplate='%{text:.1f} Days', textposition='outside')
        waste_fig = px.scatter(inv_df, x='Days_of_Cover', y=stock, size=inv_df[cost].clip(lower=1), color='Status',
                               hover_name=name, title="Capital Trap Analysis")
    else:
        fig = px.bar(inv_df, x=name, y=stock);
        waste_fig = go.Figure()

    kpis = [
        html.Div([html.Small("TOTAL INV VALUE"),
                  html.Abbr(html.H3(f"${val:,.2f}"), title="Current total capital tied in stock.")],
                 style={'flex': '1', 'backgroundColor': '#718096', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
        html.Div([html.Small("INV TURNOVER RATIO"),
                  html.Abbr(html.H3(f"{turnover:.1f}x"), title="Sales vs. Stock value. Goal: >4.0x.")],
                 style={'flex': '1', 'backgroundColor': '#4a5568', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
        html.Div([html.Small("EST. RESTOCK INVESTMENT"),
                  html.Abbr(html.H3(f"${restock_total:,.2f}"), title="Capital needed for reordering.")],
                 style={'flex': '1', 'backgroundColor': '#f56565', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
    ]
    return kpis, fig, waste_fig


@app.callback(
    Output("download-reorder-list", "data"),
    Input("btn-reorder-list", "n_clicks"),
    [State('stored-inventory-data', 'data'), State('inv-stock-col', 'value'), State('inv-name-col', 'value'),
     State('inv-cost-col', 'value'), State('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def generate_reorder_list(n, inv_js, stock_col, name_col, cost_col, threshold):
    if not inv_js or not stock_col: return None
    df = safe_load_df(inv_js)
    reorder_df = df[df[stock_col] < (threshold or 20)].copy()
    reorder_df['Suggested_Order_Qty'] = ((threshold or 20) * 1.5) - reorder_df[stock_col]
    if cost_col:
        reorder_df[cost_col] = pd.to_numeric(reorder_df[cost_col].astype(str).str.replace('[$,]', '', regex=True),
                                             errors='coerce').fillna(0)
        reorder_df['Total_Line_Cost'] = reorder_df['Suggested_Order_Qty'] * reorder_df[cost_col]
    return dcc.send_data_frame(reorder_df[[name_col, stock_col, 'Suggested_Order_Qty', 'Total_Line_Cost']].to_csv,
                               f"StockPilotDev_v3.9.14_Reorder_List.csv", index=False)


if __name__ == '__main__':
    app.run(debug=True)