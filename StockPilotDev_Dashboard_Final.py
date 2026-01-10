import base64
import io
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, dash_table, callback_context

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

    # Brand Header
    html.Div([
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9)",
                style={'color': '#ffffff', 'margin': '0', 'fontWeight': '300'}),
        html.P("2026 SMB Command Center | Sales, Labor & Inventory", style={'color': '#cbd5e0'})
    ], style={'backgroundColor': '#2d3748', 'padding': '40px 20px', 'textAlign': 'center',
              'borderRadius': '0 0 20px 20px'}),

    html.Div([
        # Data Intake
        html.Div([
            dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']), multiple=True,
                       style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px',
                              'borderStyle': 'dashed', 'borderRadius': '10px', 'textAlign': 'center',
                              'backgroundColor': '#fff', 'color': '#718096'}),
            html.Button("Reset Session", id="reset-btn",
                        style={'backgroundColor': '#e53e3e', 'color': 'white', 'padding': '10px 25px',
                               'borderRadius': '8px', 'border': 'none', 'marginTop': '15px', 'cursor': 'pointer'})
        ], style={'margin': '30px auto', 'maxWidth': '800px', 'textAlign': 'center'}),

        # PILLAR 1: SALES & FINANCIALS
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
            # Side-by-Side Graphs
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
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='inventory-topline',
                     style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px', 'flexWrap': 'wrap'}),
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
     Output('inv-name-col', 'options')],
    [Input('stored-sales-data', 'data'), Input('stored-labor-data', 'data'), Input('stored-inventory-data', 'data')]
)
def sync_dropdowns(s_js, l_js, i_js):
    s_df, l_df, i_df = safe_load_df(s_js), safe_load_df(l_js), safe_load_df(i_js)
    return [[{'label': c, 'value': c} for c in df.columns] for df in [s_df, s_df, l_df, l_df, l_df, i_df, i_df]]


@app.callback(
    [Output('topline-stats', 'children'),
     Output('sales-kpi-cards', 'children'),
     Output('sales-trend-graph', 'figure'),
     Output('customer-share-graph', 'figure')],
    [Input('stored-sales-data', 'data'),
     Input('sales-col', 'value'),
     Input('cust-col', 'value'),
     Input('fixed-costs', 'value'),
     Input('cogs-pct', 'value')],
    prevent_initial_call=True
)
def update_sales(js, rev, cust, f_costs, cogs_pct):
    if not js or rev is None or cust is None:
        raise exceptions.PreventUpdate

    df = safe_load_df(js)
    # Convert revenue to numeric format
    df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)

    # KPI Calculations
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
        html.Div([html.Small("PROJECTED NET PROFIT"), html.H2(f"${net_profit:,.0f}")],
                 style={'flex': '1', 'backgroundColor': '#2f855a', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'})
    ]

    # Graph 1: Monthly Sales Trend
    df['Date'] = pd.to_datetime(df['Date'])
    monthly_df = df.set_index('Date').resample('ME')[rev].sum().reset_index()

    fig1 = px.line(
        monthly_df,
        x='Date',
        y=rev,
        title="Monthly Sales Trend",
        markers=True,
        color_discrete_sequence=['#38a169']
    )
    fig1.update_layout(template="plotly_white", yaxis_tickprefix='$', height=450)

    # Graph 2: Revenue Concentration (Pie)
    cust_rev = df.groupby(cust)[rev].sum().reset_index()
    fig2 = px.pie(
        cust_rev.nlargest(10, rev),
        values=rev,
        names=cust,
        hole=0.4,
        title="Revenue Concentration: Top 10 Customers"
    )
    fig2.update_layout(height=450)

    # Retention KPI Card
    counts = df[cust].value_counts()
    retention = (len(counts[counts > 1]) / len(counts) * 100) if not counts.empty else 0
    kpi_cards = html.Div([
        html.Small("RETENTION RATE: "),
        html.Strong(f"{retention:.1f}%")
    ], style={'padding': '10px', 'textAlign': 'center', 'backgroundColor': '#f7fafc', 'borderRadius': '8px'})

    return topline, kpi_cards, fig1, fig2


@app.callback(
    [Output('labor-hourly-graph', 'figure'),
     Output('labor-leak-alerts', 'children'),
     Output('total-labor-text', 'children'),
     Output('labor-pct-text', 'children'),
     Output('potential-savings-text', 'children'),
     Output('monday-summary-box', 'children')],
    [Input('stored-labor-data', 'data'),
     Input('stored-sales-data', 'data'),
     Input('wage-col', 'value'),
     Input('start-col', 'value'),
     Input('end-col', 'value'),
     Input('sales-col', 'value'),
     Input('labor-threshold', 'value')],
    prevent_initial_call=True
)
def update_labor_with_leaks(l_js, s_js, wage, start, end, rev_col, threshold):
    # Safety gate to prevent processing empty inputs
    if not l_js or not all([wage, start, end]):
        raise exceptions.PreventUpdate

    l_df = safe_load_df(l_js)
    s_df = safe_load_df(s_js)

    if l_df.empty:
        return go.Figure().update_layout(height=450), "", "$0.00", "0.0%", "$0.00", "Upload Labor & Sales data."

    # Unpack both the DataFrame and the alerts list from your helper function
    hourly_labor, ot_leaks = distribute_wages_hourly(l_df, wage, start, end)

    def format_time(h):
        if h == 0: return "12 AM"
        if h < 12: return f"{int(h)} AM"
        if h == 12: return "12 PM"
        return f"{int(h - 12)} PM"

    hourly_labor['Time_Label'] = hourly_labor['Hour'].apply(format_time)

    # Default color is the StockPilot blue
    bar_colors = ['#5a67d8'] * len(hourly_labor)
    total_labor = hourly_labor['Spent'].sum()
    total_rev = 0
    leak_alerts = ""

    # Logic to compare Labor vs Sales per hour for red indicator bars
    if not s_df.empty and rev_col in s_df.columns:
        s_df[rev_col] = pd.to_numeric(s_df[rev_col].astype(str).str.replace('[$,]', '', regex=True),
                                      errors='coerce').fillna(0)
        total_rev = s_df[rev_col].sum()

        # Ensure 'Date' is datetime for hour extraction
        s_df['Hour'] = s_df['Date'].dt.hour
        hourly_sales = s_df.groupby('Hour')[rev_col].sum().reset_index()

        comparison = pd.merge(hourly_labor, hourly_sales, on='Hour', how='inner')

        if not comparison.empty:
            comparison['Labor_Ratio'] = (comparison['Spent'] / comparison[rev_col]) * 100

            # Identify the top 3 hours where labor is most expensive relative to sales
            top_3_hours = comparison.nlargest(3, 'Labor_Ratio')['Hour'].tolist()
            bar_colors = ['#f56565' if h in top_3_hours else '#5a67d8' for h in hourly_labor['Hour']]

            # Generate text alerts for leaks exceeding user threshold
            leaks = comparison[comparison['Labor_Ratio'] > (threshold or 30)]
            if not leaks.empty:
                leak_alerts = html.Div([
                    html.Strong("⚠️ LABOR LEAK DETECTED: "),
                    f"Labor exceeded {threshold}% of sales at: {', '.join([format_time(h) for h in leaks['Hour']])}."
                ], style={'color': '#c53030', 'backgroundColor': '#fff5f5', 'padding': '15px', 'borderRadius': '10px',
                          'border': '1px solid #feb2b2'})

    labor_pct = (total_labor / total_rev * 100) if total_rev > 0 else 0
    savings = total_labor * 0.10  # Est. 10% optimization target

    summary = [
        html.H4("👨‍🍳 Chef's Weekly Strategy", style={'color': '#5a67d8'}),
        html.P(f"This week, your labor-to-sales ratio is sitting at {labor_pct:.1f}%. "
               f"Focus on optimizing priority windows to save approximately ${savings:,.2f}. "
               f"Detected {len(ot_leaks)} overtime shifts.")
    ]

    # Re-apply marker_color to the figure data
    fig = go.Figure(data=[
        go.Bar(
            x=hourly_labor['Time_Label'],
            y=hourly_labor['Spent'],
            marker_color=bar_colors,
            opacity=0.85,
            text=hourly_labor['Spent'].apply(lambda x: f"${x:,.2f}"),
            textposition='outside'
        )
    ])

    fig.update_layout(
        title="Labor Cost by Hour (Rose = Critical Priority)",
        template="plotly_white",
        yaxis_tickprefix='$',
        font_family="Inter",
        height=450
    )

    return fig, leak_alerts, f"${total_labor:,.2f}", f"{labor_pct:.1f}%", f"${savings:,.2f}", summary


@app.callback(
    [Output('inventory-topline', 'children'), Output('inventory-graph', 'figure')],
    [Input('stored-inventory-data', 'data'), Input('stored-sales-data', 'data'), Input('inv-stock-col', 'value'),
     Input('inv-name-col', 'value'), Input('sales-col', 'value'), Input('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def update_inventory(i_js, s_js, stock, name, rev_col, thresh):
    if not i_js or stock is None: raise exceptions.PreventUpdate
    inv_df, sales_df = safe_load_df(i_js), safe_load_df(s_js)
    inv_df[stock] = pd.to_numeric(inv_df[stock], errors='coerce').fillna(0)

    velocity_cards = [html.Div(f"Low Stock: {len(inv_df[inv_df[stock] < float(thresh or 20)])} items")]
    fig = px.bar(inv_df.nlargest(15, stock), x=name, y=stock, title="Inventory Levels")
    return velocity_cards, fig


@app.callback(
    Output("download-reorder-list", "data"),
    Input("btn-reorder-list", "n_clicks"),
    [State('stored-inventory-data', 'data'), State('inv-stock-col', 'value'), State('inv-name-col', 'value'),
     State('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def download_list(n, js, stock, name, thresh):
    if not js: raise exceptions.PreventUpdate
    df = safe_load_df(js)
    reorder = df[df[stock] < float(thresh or 20)]
    return dcc.send_data_frame(reorder.to_csv, "Reorder_List.csv", index=False)


if __name__ == '__main__':
    app.run(debug=True)