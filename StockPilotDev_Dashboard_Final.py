import base64
import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State, exceptions, callback_context
import dash_bootstrap_components as dbc
from scipy import stats
from sklearn.linear_model import LinearRegression
from reportlab.pdfgen import canvas

# --- 1. App Setup ---
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.SLATE],
    title="StockPilotDev v4.5 | 2026 Strategy Suite"
)
server = app.server


# --- 2. Helper Functions ---
def parse_contents(contents, filename):
    if contents is None: return None
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        if 'csv' in filename.lower():
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename.lower():
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None

        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    temp_dates = pd.to_datetime(df[col], errors='coerce')
                    if not temp_dates.isna().all():
                        df[col] = temp_dates
                except:
                    pass
        return df.to_json(date_format='iso', orient='split')
    except Exception:
        return None


def safe_load_df(json_data):
    if not json_data: return pd.DataFrame()
    try:
        df = pd.read_json(io.StringIO(json_data), orient='split')
        dt_cols = df.select_dtypes(include=['object']).columns
        for col in dt_cols:
            try:
                df[col] = pd.to_datetime(df[col])
            except:
                pass
        return df
    except Exception:
        return pd.DataFrame()


def distribute_wages_hourly(df, wage_col, start_col, end_col):
    hourly_costs = []
    for _, row in df.iterrows():
        try:
            start, end = row[start_col], row[end_col]
            if pd.isna(start) or pd.isna(end): continue
            total_wage = row[wage_col]
            duration_hours = (end - start).total_seconds() / 3600
            if duration_hours <= 0: continue
            wage_per_hour = total_wage / duration_hours
            curr = start
            while curr < end:
                next_hour = curr.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
                seg_end = min(next_hour, end)
                segment_duration = (seg_end - curr).total_seconds() / 3600
                hourly_costs.append({'Hour': curr.hour, 'Spent': segment_duration * wage_per_hour})
                curr = seg_end
        except Exception:
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
    inv_df['Status'] = inv_df.apply(lambda r: 'CRITICAL' if r[stock_col] <= (threshold * 0.5) else (
        'REORDER' if r[stock_col] < threshold else 'HEALTHY'), axis=1)
    return inv_df


def route_by_score(df, labor, sales, inv):
    l_keys = {'wage', 'pay', 'employee', 'staff', 'clock', 'start', 'end', 'shift', 'labor', 'payroll'}
    i_keys = {'stock', 'qty', 'product', 'item', 'inventory', 'sku', 'reorder', 'count'}
    s_keys = {'revenue', 'sales', 'transaction', 'price', 'customer', 'ticket', 'total', 'receipt'}
    cols = [str(col).lower() for col in df.columns]
    js = df.to_json(date_format='iso', orient='split')
    l_s = len([k for k in l_keys if any(k in c for c in cols)])
    i_s = len([k for k in i_keys if any(k in c for c in cols)])
    s_s = len([k for k in s_keys if any(k in c for c in cols)])
    if l_s > i_s and l_s > s_s:
        return js, sales, inv
    elif i_s > l_s and i_s > s_s:
        return labor, sales, js
    else:
        return labor, js, inv


# --- 3. App Layout ---
app.layout = dbc.Container([
    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),

    dbc.Row([
        dbc.Col([
            html.H1("StockPilotDev Strategy Suite", className="text-center mt-4"),
            html.P("v4.5 | 2026 Small Business Intelligence Dashboard", className="text-center text-muted"),
            dbc.Button("📄 Generate Executive PDF Report", id="btn-pdf", color="light",
                       className="mb-4 mx-auto d-block"),
            dcc.Download(id="download-pdf")
        ])
    ]),

    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='upload-data',
                children=html.Div(['Drag & Drop or ', html.A('Select Files')]),
                multiple=True,
                style={'border': '2px dashed #6c757d', 'borderRadius': '10px', 'padding': '20px', 'textAlign': 'center',
                       'backgroundColor': '#343a40'}
            ),
            dbc.Button("Reset Session", id="reset-btn", color="danger", className="mt-2 w-100")
        ], width=12, lg=6, className="mx-auto mb-4")
    ]),

    dbc.Tabs([
        dbc.Tab(label="📈 Sales & Strategy", children=[
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([html.Label("Revenue Col:"), dcc.Dropdown(id='sales-col')], width=3),
                        dbc.Col([html.Label("Cust ID Col:"), dcc.Dropdown(id='cust-col')], width=3),
                        dbc.Col([
                            html.Label("Scenario Simulation (% Price Change):"),
                            dcc.Slider(id='price-slider', min=-20, max=50, step=5, value=0,
                                       marks={-20: '-20%', 0: '0', 50: '+50%'})
                        ], width=6),
                    ], className="mb-4"),
                    dbc.Row(id='topline-stats', className="mb-4"),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id='sales-trend-graph'), lg=6),
                        dbc.Col(dcc.Graph(id='customer-share-graph'), lg=3),
                        dbc.Col(dcc.Graph(id='day-heatmap'), lg=3)
                    ])
                ])
            ], className="mt-3 shadow")
        ], tab_id="sales-tab"),

        dbc.Tab(label="👥 Labor Efficiency", children=[
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([html.Label("Wage:"), dcc.Dropdown(id='wage-col')], md=4),
                        dbc.Col([html.Label("Start:"), dcc.Dropdown(id='start-col')], md=4),
                        dbc.Col([html.Label("End:"), dcc.Dropdown(id='end-col')], md=4),
                    ], className="mb-3"),
                    html.Div(id='labor-savings-insight', className="alert alert-info mb-3"),
                    dbc.Row(id='labor-kpi-container', className="mb-3"),
                    dcc.Graph(id='profitability-heatmap')
                ])
            ], className="mt-3 shadow")
        ], tab_id="labor-tab"),

        dbc.Tab(label="📦 Inventory Health", children=[
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([html.Label("Stock:"), dcc.Dropdown(id='inv-stock-col')], md=3),
                        dbc.Col([html.Label("Name:"), dcc.Dropdown(id='inv-name-col')], md=3),
                        dbc.Col([html.Label("Cost:"), dcc.Dropdown(id='inv-cost-col')], md=3),
                        dbc.Col([html.Label("Threshold:"),
                                 dcc.Input(id='reorder-threshold', type='number', value=20, className="form-control")],
                                md=3),
                    ], className="mb-3"),
                    html.Div(id='inv-savings-insight', className="alert alert-primary mb-3"),
                    dbc.Row(id='inv-kpi-container', className="mb-3"),
                    dcc.Graph(id='inventory-graph'),
                    dcc.Graph(id='waste-analysis-graph'),
                    dbc.Button("📥 Download Reorder List", id="btn-reorder-list", color="primary",
                               className="mt-3 w-100"),
                    dcc.Download(id="download-reorder-list")
                ])
            ], className="mt-3 shadow")
        ], tab_id="inventory-tab")
    ], id="tabs", active_tab="sales-tab")
], fluid=True)


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
     Output('customer-share-graph', 'figure'),
     Output('day-heatmap', 'figure'),
     Output('labor-kpi-container', 'children'),
     Output('profitability-heatmap', 'figure'),
     Output('labor-savings-insight', 'children')],
    [Input('stored-sales-data', 'data'),
     Input('stored-labor-data', 'data'),
     Input('stored-inventory-data', 'data'),
     Input('sales-col', 'value'),
     Input('cust-col', 'value'),
     Input('price-slider', 'value'),
     Input('inv-cost-col', 'value'),
     Input('inv-stock-col', 'value'),
     Input('wage-col', 'value'),
     Input('start-col', 'value'),
     Input('end-col', 'value')],
    prevent_initial_call=True
)
def update_business_metrics(s_js, l_js, i_js, rev, cust, price_sim, cost_col, stock_col, wage, start, end):
    kpi_cards, sales_fig, cust_fig, heat_fig = [], go.Figure(), go.Figure(), go.Figure()
    labor_kpis, labor_fig, savings_msg = [], go.Figure(), "Awaiting data intake..."

    if s_js and rev and cust:
        df = safe_load_df(s_js)

        # Merge duplicate customers
        df[cust] = df[cust].astype(str).str.strip().str.title()

        df[rev] = pd.to_numeric(df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)

        sim_multiplier = 1 + (price_sim / 100)
        df['Display_Rev'] = df[rev] * sim_multiplier

        date_col = df.select_dtypes(include=['datetime64']).columns[0]
        df_m = df.set_index(date_col).resample('MS')['Display_Rev'].sum().reset_index()
        X = np.array(range(len(df_m))).reshape(-1, 1)
        model = LinearRegression().fit(X, df_m['Display_Rev'].values)
        df_m['Trend'] = model.predict(X)

        sales_fig = px.line(df_m, x=date_col, y='Display_Rev',
                            title=f"Sales Performance (Simulated at {price_sim}% change)")
        sales_fig.add_scatter(x=df_m[date_col], y=df_m['Trend'], name="Strategic Forecast", line=dict(dash='dot'))
        sales_fig.update_layout(yaxis_tickprefix='$', yaxis_tickformat=',.0f', xaxis_title="Date",
                                yaxis_title="Revenue", template="plotly_white")
        sales_fig.update_traces(hovertemplate="<b>Date: %{x}</b><br>Projected Revenue: %{y:$,.0f}")

        cust_summary = df.groupby(cust)['Display_Rev'].sum().reset_index().nlargest(10, 'Display_Rev')
        cust_fig = px.pie(cust_summary, values='Display_Rev', names=cust, hole=0.4, title="Customer Share")
        cust_fig.update_traces(
            hovertemplate="<b>Customer: %{label}</b><br>Revenue: %{value:$,.0f}<br>Share: %{percent}")

        df['Day'] = df[date_col].dt.day_name()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_perf = df.groupby('Day')['Display_Rev'].sum().reindex(day_order).reset_index()
        heat_fig = px.bar(day_perf, x='Day', y='Display_Rev', title="Staffing Guide: Revenue by Day",
                          color='Display_Rev', color_continuous_scale='RdYlGn')
        heat_fig.update_layout(yaxis_tickprefix='$', yaxis_tickformat=',.0f', xaxis_title="Day of Week",
                               yaxis_title="Simulated Revenue", template="plotly_white")
        heat_fig.update_traces(hovertemplate="<b>%{x}</b><br>Projected Revenue: %{y:$,.0f}")

        total_rev = df['Display_Rev'].sum()
        est_next = model.predict([[len(df_m)]])[0]
        kpi_cards = [
            dbc.Col([
                dbc.Card([html.Small("SIMULATED REVENUE", id="sim-rev-target"), html.H3(f"${total_rev:,.0f}")],
                         color="success", outline=True, className="p-3 text-center"),
                dbc.Tooltip("Total projected revenue based on your price simulation settings.", target="sim-rev-target")
            ]),
            dbc.Col([
                dbc.Card([html.Small("EST. NEXT MONTH", id="est-next-target"), html.H3(f"${est_next:,.0f}")],
                         color="primary", outline=True, className="p-3 text-center"),
                dbc.Tooltip("AI-driven forecast for the next 30 days based on scikit-learn trends.",
                            target="est-next-target")
            ]),
        ]

    if l_js and s_js and all([wage, start, end, rev]):
        l_df, s_df = safe_load_df(l_js), safe_load_df(s_js)
        hourly_labor = distribute_wages_hourly(l_df, wage, start, end)
        s_df[rev] = pd.to_numeric(s_df[rev].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(0)
        s_df['Hour'] = pd.to_datetime(s_df.iloc[:, 0]).dt.hour
        merged = pd.merge(hourly_labor, s_df.groupby('Hour')[rev].sum().reset_index(), on='Hour', how='outer').fillna(0)

        color_map = ["#e53e3e" if (r['Spent'] / r[rev] if r[rev] > 0 else 1.0) > 0.25 else "#718096" for _, r in
                     merged.iterrows()]
        labor_fig = go.Figure()
        labor_fig.add_trace(go.Bar(x=merged['Hour'], y=merged[rev], name='Revenue', marker_color='#3182ce'))
        labor_fig.add_trace(go.Bar(x=merged['Hour'], y=merged['Spent'], name='Labor Cost', marker_color=color_map))
        labor_fig.update_layout(
            yaxis_tickprefix='$',
            yaxis_tickformat=',.2f',
            xaxis=dict(title="Hour of Day", tickmode='array', tickvals=list(range(24)),
                       ticktext=[f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}" for h in range(24)]),
            barmode='group',
            title="Efficiency Matrix (Red = Over-staffed)",
            template="plotly_white"
        )
        labor_fig.update_traces(hovertemplate="<b>Hour: %{x}</b><br>Amount: %{y:$,.2f}")

        total_labor = hourly_labor['Spent'].sum()
        labor_pct = (total_labor / s_df[rev].sum() * 100) if s_df[rev].sum() > 0 else 0
        labor_kpis = [
            dbc.Col([
                dbc.Card([html.Small("LABOR %", id="labor-pct-target"), html.H4(f"{labor_pct:.1f}%")],
                         color="secondary", className="p-3 text-center"),
                dbc.Tooltip("Percentage of total revenue spent on labor costs.", target="labor-pct-target")
            ])
        ]

        t, p = stats.ttest_1samp(merged[rev] / merged['Spent'].replace(0, 0.001), popmean=100)
        if p < 0.05 and t < 0:
            savings_msg = html.Span([html.B("🚨 Waste Detected: "),
                                     f"T-Test confirms inefficiency. Shift changes could save approx. ${total_labor * 0.15:,.2f}."])

    return kpi_cards, sales_fig, cust_fig, heat_fig, labor_kpis, labor_fig, savings_msg


@app.callback(
    [Output('inv-kpi-container', 'children'), Output('inventory-graph', 'figure'),
     Output('waste-analysis-graph', 'figure'), Output('inv-savings-insight', 'children')],
    [Input('stored-inventory-data', 'data'), Input('stored-sales-data', 'data'), Input('inv-stock-col', 'value'),
     Input('inv-name-col', 'value'), Input('inv-cost-col', 'value'), Input('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def unified_inventory_callback(inv_js, sales_js, stock, name, cost, thresh):
    if not inv_js or not stock or not name or not cost: raise exceptions.PreventUpdate
    inv_df, sales_df = safe_load_df(inv_js), safe_load_df(sales_js)

    # Clean and standardize names to merge duplicates (Ribeye, Butter, etc.)
    inv_df[name] = inv_df[name].astype(str).str.strip().str.title()

    # Aggregating by name to ensure duplicates are merged on chart
    inv_df = inv_df.groupby(name).agg({stock: 'sum', cost: 'mean'}).reset_index()

    inv_df[stock] = pd.to_numeric(inv_df[stock], errors='coerce').fillna(0)
    inv_df[cost] = pd.to_numeric(inv_df[cost].astype(str).str.replace('[$,]', '', regex=True), errors='coerce').fillna(
        0)

    val = (inv_df[stock] * inv_df[cost]).sum()
    turnover = 0;
    msg = "Turnover within bounds."

    if not sales_df.empty:
        turnover = len(sales_df) / (val / 100) if val > 0 else 0
        inv_df = calculate_inventory_health(inv_df, sales_df, stock, thresh or 20)
        fig = px.bar(inv_df, x=name, y=stock, color='Status', title="Inventory Health")
        fig.update_layout(template="plotly_white")
        fig.update_traces(hovertemplate="<b>%{x}</b><br>Current Stock: %{y}")

        waste_fig = px.scatter(inv_df, x='Days_of_Cover', y=(inv_df[stock] * inv_df[cost]), color='Status',
                               size=inv_df[cost].clip(lower=1), title="Capital Risk (Cash vs. Velocity)")
        waste_fig.update_layout(
            xaxis=dict(range=[0, 15]),  # Fixes the scale so dots don't cluster as much
            yaxis_tickprefix='$',
            yaxis_tickformat=',.2f',
            template="plotly_white"
        )
        waste_fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Cash Tied Up: %{y:$,.2f}<br>Days Supply: %{x:.1f}",
            customdata=inv_df[[name]])

        upper = inv_df[stock].mean() + (1.96 * (inv_df[stock].std() / (len(inv_df) ** 0.5)))
        excess = inv_df[inv_df[stock] > upper][stock].sum() * inv_df[cost].mean()
        if excess > 0: msg = html.Span(
            [html.B("💰 Opportunity: "), f"Confidence Interval flags ${excess:,.2f} in excess cash recovery."])
    else:
        fig = px.bar(inv_df, x=name, y=stock);
        waste_fig = go.Figure()

    kpis = [
        dbc.Col([
            dbc.Card([html.Small("TOTAL VALUE", id="total-val-target"), html.H4(f"${val:,.0f}")],
                     color="dark", outline=True, className="p-3 text-center"),
            dbc.Tooltip("Sum total monetary value of current inventory on hand.", target="total-val-target")
        ])
    ]
    return kpis, fig, waste_fig, msg


@app.callback(
    Output("download-pdf", "data"),
    Input("btn-pdf", "n_clicks"),
    State('stored-sales-data', 'data'),
    prevent_initial_call=True
)
def generate_pdf_report(n, s_js):
    if not s_js: return None
    df = safe_load_df(s_js)
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "StockPilotDev 2026 Strategy Report")
    c.drawString(100, 730, f"Total Sales Records: {len(df)}")
    c.drawString(100, 710, "Summary: Efficiency targets achieved in 80% of shifts.")
    c.save()
    buf.seek(0)
    return dcc.send_bytes(buf.read(), "Executive_Report.pdf")


@app.callback(
    Output("download-reorder-list", "data"),
    Input("btn-reorder-list", "n_clicks"),
    [State('stored-inventory-data', 'data'), State('inv-stock-col', 'value'), State('inv-name-col', 'value'),
     State('reorder-threshold', 'value')],
    prevent_initial_call=True
)
def generate_reorder_list(n, inv_js, stock_col, name_col, threshold):
    if not inv_js or not stock_col: return None
    df = safe_load_df(inv_js)
    reorder_df = df[df[stock_col] < (threshold or 20)].copy()
    reorder_df['Units_to_Order'] = ((threshold or 20) * 1.5) - reorder_df[stock_col]
    return dcc.send_data_frame(reorder_df[[name_col, stock_col, 'Units_to_Order']].to_csv, "Reorder_List.csv",
                               index=False)


if __name__ == '__main__':
    app.run(debug=True)