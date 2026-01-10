import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, callback_context

# --- 1. App Setup ---
app = dash.Dash(__name__, title="StockPilotDev v3.9.13 | 2026 Strategy Suite")
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
    if res.empty: return pd.DataFrame(columns=['Hour', 'Spent']), []
    return res.groupby('Hour')['Spent'].sum().reset_index(), []


def process_gsheet_url(url):
    try:
        if "/d/" in url:
            sheet_id = url.split("/d/")[1].split("/")[0]
            return f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0'
    except:
        return None
    return None


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
        return append_data(labor, js), sales, inv
    elif i_score > l_score and i_score > s_score:
        return labor, sales, append_data(inv, js)
    else:
        return labor, append_data(sales, js), inv


# --- 3. App Layout ---
app.layout = html.Div([
    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),
    html.Div([
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9.12)", style={'color': '#ffffff', 'margin': '0'}),
        html.P("2026 SMB Command Center | Sales, Labor & Inventory", style={'color': '#cbd5e0'})
    ], style={'backgroundColor': '#2d3748', 'padding': '40px 20px', 'textAlign': 'center',
              'borderRadius': '0 0 20px 20px'}),
    html.Div([
        html.Div([
            dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']), multiple=True,
                       style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                              'borderStyle': 'dashed', 'borderRadius': '10px', 'textAlign': 'center',
                              'backgroundColor': '#fff'}),
            dcc.Input(id='gsheet-url', type='text', placeholder='Paste Google Sheets URL here...',
                      style={'width': '100%', 'height': '40px', 'marginTop': '10px', 'borderRadius': '8px',
                             'border': '1px solid #cbd5e0', 'padding': '0 10px'}),
            html.Div(id='gsheet-status', style={'marginTop': '10px', 'fontSize': '14px', 'fontWeight': 'bold'}),
            html.Button("Reset Session", id="reset-btn",
                        style={'backgroundColor': '#e53e3e', 'color': 'white', 'padding': '10px 25px',
                               'borderRadius': '8px', 'border': 'none', 'marginTop': '15px', 'cursor': 'pointer'})
        ], style={'margin': '30px auto', 'maxWidth': '800px', 'textAlign': 'center'}),

        # PILLARS
        html.Div([
            html.H2("📈 Sales & Financials", style={'color': '#38a169'}),
            html.Div([
                html.Div([html.Label("Revenue Col:"), dcc.Dropdown(id='sales-col')], style={'flex': '1'}),
                html.Div([html.Label("Cust ID Col:"), dcc.Dropdown(id='cust-col')], style={'flex': '1'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='topline-stats', style={'display': 'flex', 'gap': '15px'}),
            html.Div(
                [dcc.Loading(dcc.Graph(id='sales-trend-graph')), dcc.Loading(dcc.Graph(id='customer-share-graph'))],
                style={'display': 'flex', 'gap': '20px'})
        ], style={'padding': '30px', 'marginBottom': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px',
                  'backgroundColor': '#fff'}),

        html.Div([
            html.H2("👥 Labor Productivity", style={'color': '#5a67d8'}),
            html.Div([
                html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("Start Time:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("End Time:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
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
            ], style={'display': 'flex', 'gap': '15px'}),
            dcc.Loading(dcc.Graph(id='labor-hourly-graph'))
        ], style={'padding': '30px', 'marginBottom': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px',
                  'backgroundColor': '#fff'}),

        html.Div([
            html.H2("📦 Inventory Intelligence", style={'color': '#718096'}),
            html.Div([
                html.Div([html.Label("Stock Qty Col:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
                html.Div([html.Label("Product Name:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
                html.Div([html.Label("Unit Cost Col:"), dcc.Dropdown(id='inv-cost-col')], style={'flex': '1'}),
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div([
                html.Div([html.Small("TOTAL INV VALUE"), html.H3(id='inv-value-text')],
                         style={'flex': '1', 'backgroundColor': '#718096', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("LOW STOCK ITEMS"), html.H3(id='low-stock-count-text')],
                         style={'flex': '1', 'backgroundColor': '#f56565', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
            ], style={'display': 'flex', 'gap': '15px'}),
            dcc.Loading(dcc.Graph(id='inventory-graph')),
            html.Button("📥 Generate Reorder List", id="btn-reorder-list", style={'marginTop': '10px'}),
            dcc.Download(id="download-reorder-list")
        ], style={'padding': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px', 'backgroundColor': '#fff'})
    ], style={'maxWidth': '1200px', 'margin': '0 auto'})
])


# --- 4. Callbacks ---
@app.callback(
    [Output('stored-labor-data', 'data'), Output('stored-sales-data', 'data'), Output('stored-inventory-data', 'data'),
     Output('gsheet-status', 'children'), Output('gsheet-status', 'style')],
    [Input('upload-data', 'contents'), Input('gsheet-url', 'value'), Input('reset-btn', 'n_clicks')],
    [State('upload-data', 'filename'), State('stored-labor-data', 'data'), State('stored-sales-data', 'data'),
     State('stored-inventory-data', 'data')],
    prevent_initial_call=True
)
def master_intake(contents, url, reset, names, labor, sales, inv):
    tid = callback_context.triggered_id
    if tid == 'reset-btn': return None, None, None, "Reset", {'color': 'gray'}
    msg, color = "", "green"
    if tid == 'gsheet-url' and url:
        csv = process_gsheet_url(url)
        if csv:
            try:
                df = pd.read_csv(csv)
                labor, sales, inv = route_by_score(df, labor, sales, inv)
                msg = "✅ Cloud Connected"
            except:
                msg, color = "❌ Connection Error", "red"
    if tid == 'upload-data' and contents:
        for c, n in zip(contents, names):
            js = parse_contents(c, n)
            if js:
                df = safe_load_df(js)
                labor, sales, inv = route_by_score(df, labor, sales, inv)
        msg = f"✅ {len(contents)} File(s) Uploaded"
    return labor, sales, inv, msg, {'color': color, 'marginTop': '10px'}


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
    [Output('topline-stats', 'children'), Output('sales-trend-graph', 'figure'),
     Output('customer-share-graph', 'figure')],
    [Input('stored-sales-data', 'data'), Input('sales-col', 'value'), Input('cust-col', 'value')],
    prevent_initial_call=True
)
def update_sales(js, rev, cust):
    if not js or not rev or not cust: raise exceptions.PreventUpdate
    df = safe_load_df(js)
    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
    total = df[rev].sum()
    top = html.Div(
        [html.Abbr("REVENUE", title="Total gross sales generated.", style={'textDecoration': 'none', 'cursor': 'help'}),
         html.H2(f"${total:,.0f}")],
        style={'backgroundColor': '#48bb78', 'color': 'white', 'padding': '20px', 'borderRadius': '12px', 'flex': '1'})

    # Updated: Added Mode 'text' and yaxis prefix
    fig1 = px.line(df, x=df.columns[0], y=rev, title="Monthly Sales Trend")
    fig1.update_traces(mode="lines+markers+text", texttemplate="$%{y:,.0f}", textposition="top center")
    fig1.update_layout(yaxis_tickprefix='$', yaxis_tickformat=',.0f')

    fig2 = px.pie(df.groupby(cust)[rev].sum().reset_index().nlargest(10, rev), values=rev, names=cust, hole=0.4)
    fig2.update_traces(textinfo='percent+label')
    return top, fig1, fig2


@app.callback(
    [Output('labor-hourly-graph', 'figure'), Output('total-labor-text', 'children'),
     Output('labor-pct-text', 'children'), Output('rplh-text', 'children')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'), Input('wage-col', 'value'),
     Input('start-col', 'value'), Input('end-col', 'value'), Input('sales-col', 'value')],
    prevent_initial_call=True
)
def update_labor(l_js, s_js, wage, start, end, rev_col):
    if not l_js or not all([wage, start, end]): raise exceptions.PreventUpdate
    l_df, s_df = safe_load_df(l_js), safe_load_df(s_js)
    hourly, _ = distribute_wages_hourly(l_df, wage, start, end)
    total_l = hourly['Spent'].sum()
    total_s = pd.to_numeric(s_df[rev_col].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').sum() if (
                not s_df.empty and rev_col) else 0
    hrs = (pd.to_datetime(l_df[end]) - pd.to_datetime(l_df[start])).dt.total_seconds().sum() / 3600
    rplh = total_s / hrs if hrs > 0 else 0

    # Updated: Added Axis Prefix and texttemplate
    fig = px.bar(hourly, x='Hour', y='Spent', title="Labor Cost by Hour", text_auto='.2s')
    fig.update_traces(texttemplate='$%{y:,.2f}', textposition='outside')
    fig.update_layout(yaxis_tickprefix='$', yaxis_tickformat=',.2f', template="plotly_white")

    return fig, html.Abbr(f"${total_l:,.2f}", title="Total wage spend."), html.Abbr(
        f"{(total_l / total_s * 100):.1f}%" if total_s > 0 else "0%", title="Labor as % of Sales."), html.Abbr(
        f"${rplh:.2f}", title="Revenue per Labor Hour.")


@app.callback(
    [Output('inv-value-text', 'children'), Output('low-stock-count-text', 'children'),
     Output('inventory-graph', 'figure')],
    [Input('stored-inventory-data', 'data'), Input('inv-stock-col', 'value'), Input('inv-name-col', 'value'),
     Input('inv-cost-col', 'value'), Input('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def unified_inventory_callback(js, stock, name, cost, thresh):
    if not js or not stock or not name: raise exceptions.PreventUpdate
    df = safe_load_df(js)
    df[stock] = pd.to_numeric(df[stock], errors='coerce').fillna(0)
    c_vals = pd.to_numeric(df[cost].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(
        10) if cost else 10
    val = (df[stock] * c_vals).sum()

    # Updated: Added Data Labels to Inventory
    fig = px.bar(df.nlargest(15, stock), x=name, y=stock, title="Current Stock Levels", text_auto=True)
    fig.update_traces(textposition='outside')

    return html.Abbr(f"${val:,.2f}", title="Total capital in stock."), html.Abbr(
        f"{len(df[df[stock] < (thresh or 20)])}", title="Items below reorder point."), fig


if __name__ == '__main__':
    app.run(debug=True)