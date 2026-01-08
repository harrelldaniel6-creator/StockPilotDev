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
        html.H1("StockPilotDev: Integrated Strategy Suite (v3.9)",
                style={'color': '#ffffff', 'margin': '0', 'fontWeight': '300'}),
        html.P("2026 SMB Command Center | Sales, Labor & Inventory", style={'color': '#cbd5e0'})
    ], style={'backgroundColor': '#2d3748', 'padding': '40px 20px', 'textAlign': 'center',
              'borderRadius': '0 0 20px 20px'}),

    html.Div([
        dcc.Upload(id='upload-data', children=html.Div(['Drag & Drop Files']), style={
            'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '1px', 'borderStyle': 'dashed',
            'borderRadius': '10px', 'textAlign': 'center', 'backgroundColor': '#fff', 'color': '#718096'
        }, multiple=True),
        html.Button("Reset Session", id="reset-btn",
                    style={'backgroundColor': '#e53e3e', 'color': 'white', 'padding': '10px 25px',
                           'borderRadius': '8px', 'border': 'none', 'marginTop': '15px', 'cursor': 'pointer'})
    ], style={'margin': '30px auto', 'maxWidth': '800px', 'textAlign': 'center'}),

    dcc.Store(id='stored-labor-data', storage_type='session'),
    dcc.Store(id='stored-sales-data', storage_type='session'),
    dcc.Store(id='stored-inventory-data', storage_type='session'),

    html.Div([
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
            dcc.Graph(id='sales-trend-graph'),
        ], style={'padding': '30px', 'marginBottom': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px',
                  'backgroundColor': '#fff', 'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.1)'}),

        # PILLAR 2: LABOR & LEAK DETECTION
        html.Div([
            html.H2("👥 Labor Productivity", style={'color': '#5a67d8', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Wage Col:"), dcc.Dropdown(id='wage-col')], style={'flex': '1'}),
                html.Div([html.Label("Start Time:"), dcc.Dropdown(id='start-col')], style={'flex': '1'}),
                html.Div([html.Label("End Time:"), dcc.Dropdown(id='end-col')], style={'flex': '1'}),
                html.Div([html.Label("Labor Cap %:"), dcc.Input(id='labor-threshold', type='number', value=30)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),

            # LABOR KPI SECTION
            html.Div([
                html.Div([html.Small("TOTAL LABOR SPEND", style={'opacity': '0.8'}),
                          html.H3(id='total-labor-text', style={'margin': '5px 0'})],
                         style={'flex': '1', 'backgroundColor': '#5a67d8', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("LABOR % OF SALES", style={'opacity': '0.8'}),
                          html.H3(id='labor-pct-text', style={'margin': '5px 0'})],
                         style={'flex': '1', 'backgroundColor': '#4c51bf', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
                html.Div([html.Small("PRIORITY SAVINGS", style={'opacity': '0.8'}),
                          html.H3(id='potential-savings-text', style={'margin': '5px 0'})],
                         title="Est. savings if Priority Hours were reduced by 10%",
                         style={'flex': '1', 'backgroundColor': '#f56565', 'color': 'white', 'padding': '20px',
                                'borderRadius': '12px'}),
            ], style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),

            # CHEF'S MONDAY SUMMARY BOX
            html.Div(id='monday-summary-box', style={
                'padding': '20px', 'backgroundColor': '#f7fafc', 'borderRadius': '12px',
                'borderLeft': '5px solid #5a67d8', 'marginTop': '20px', 'marginBottom': '20px',
                'lineHeight': '1.6', 'color': '#2d3748'
            }),

            html.Div(id='labor-leak-alerts', style={'marginTop': '20px'}),
            dcc.Graph(id='labor-hourly-graph'),
        ], style={'padding': '30px', 'marginBottom': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px',
                  'backgroundColor': '#fff', 'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.1)'}),

        # PILLAR 3: INVENTORY INTELLIGENCE
        html.Div([
            html.H2("📦 Inventory Intelligence",
                    style={'color': '#718096', 'fontSize': '1.5rem', 'marginBottom': '20px'}),
            html.Div([
                html.Div([html.Label("Stock Qty Col:"), dcc.Dropdown(id='inv-stock-col')], style={'flex': '1'}),
                html.Div([html.Label("Product Name:"), dcc.Dropdown(id='inv-name-col')], style={'flex': '1'}),
                html.Div([html.Label("Reorder Pt:"), dcc.Input(id='reorder-threshold', type='number', value=20)],
                         style={'flex': '0.5'}),
            ], style={'display': 'flex', 'gap': '20px', 'marginBottom': '25px'}),
            html.Div(id='inventory-topline', style={'display': 'flex', 'gap': '15px', 'marginBottom': '20px'}),
            dcc.Graph(id='inventory-graph')
        ], style={'padding': '30px', 'border': '1px solid #e2e8f0', 'borderRadius': '15px', 'backgroundColor': '#fff',
                  'boxShadow': '0 4px 6px -1px rgba(0,0,0,0.1)'}),

    ], style={'maxWidth': '1200px', 'margin': '0 auto', 'paddingBottom': '100px'})
], style={'fontFamily': 'Inter, system-ui, sans-serif', 'backgroundColor': '#f7fafc', 'minHeight': '100vh'})


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

    topline = [
        html.Div([html.Small("TOTAL REVENUE", style={'opacity': '0.8'}),
                  html.H2(f"${total_rev:,.0f}", style={'margin': '5px 0'})],
                 style={'flex': '1', 'backgroundColor': '#48bb78', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'}),
        html.Div([html.Small("GROSS PROFIT", style={'opacity': '0.8'}),
                  html.H2(f"${gross_profit:,.0f}", style={'margin': '5px 0'})],
                 style={'flex': '1', 'backgroundColor': '#38a169', 'color': 'white', 'padding': '20px',
                        'borderRadius': '12px'})
    ]

    retention = 0
    clv = 0
    if cust and cust in df.columns:
        counts = df[cust].value_counts()
        retention = (len(counts[counts > 1]) / len(counts)) * 100 if len(counts) > 0 else 0
        clv = total_rev / len(counts) if len(counts) > 0 else 0

    monthly = df.set_index('Date').resample('ME')[rev].sum().reset_index()
    be_progress = min(100, (monthly[rev].iloc[-1] / f_costs * 100)) if f_costs and not monthly.empty else 0

    kpi_cards = html.Div([
        html.Div([
            html.Div([html.Small("AVG CUSTOMER VALUE (CLV)"), html.H3(f"${clv:,.2f}", style={'color': '#38a169'})],
                     style={'flex': '1', 'borderRight': '1px solid #edf2f7'}),
            html.Div([html.Small("RETENTION"), html.H3(f"{retention:.1f}%", style={'color': '#5a67d8'})],
                     style={'flex': '1', 'borderRight': '1px solid #edf2f7'}),
            html.Div([html.Small("BREAK-EVEN"), html.H3(f"{be_progress:.1f}%"),
                      html.Div(style={'backgroundColor': '#edf2f7', 'height': '8px', 'borderRadius': '4px',
                                      'marginTop': '5px'}, children=[
                          html.Div(style={'backgroundColor': '#48bb78', 'height': '100%', 'width': f'{be_progress}%',
                                          'borderRadius': '4px'})])], style={'flex': '1.5', 'padding': '0 20px'})
        ], style={'display': 'flex', 'textAlign': 'center', 'padding': '20px', 'backgroundColor': '#fff',
                  'borderRadius': '12px', 'border': '1px solid #edf2f7'})
    ], style={'marginBottom': '20px'})

    fig = px.bar(monthly, x='Date', y=rev, title="Monthly Revenue vs Trend", text_auto='$.2s')
    fig.update_layout(template="plotly_white", yaxis_tickprefix='$', font_family="Inter")
    fig.update_traces(marker_color='#48bb78', marker_line_color='#2f855a', marker_line_width=1, opacity=0.85)
    return topline, kpi_cards, fig


@app.callback(
    [Output('labor-hourly-graph', 'figure'), Output('labor-leak-alerts', 'children'),
     Output('total-labor-text', 'children'), Output('labor-pct-text', 'children'),
     Output('potential-savings-text', 'children'), Output('monday-summary-box', 'children')],
    [Input('stored-labor-data', 'data'), Input('stored-sales-data', 'data'),
     Input('wage-col', 'value'), Input('start-col', 'value'), Input('end-col', 'value'),
     Input('sales-col', 'value'), Input('labor-threshold', 'value')]
)
def update_labor_with_leaks(l_js, s_js, wage, start, end, rev_col, threshold):
    l_df = safe_load_df(l_js)
    s_df = safe_load_df(s_js)
    if l_df.empty or not all([wage, start, end]):
        return go.Figure(), "", "$0.00", "0.0%", "$0.00", "Upload Labor & Sales data to see the Chef's Strategy."

    hourly_labor = distribute_wages_hourly(l_df, wage, start, end)

    def format_time(h):
        if h == 0: return "12 AM"
        if h < 12: return f"{int(h)} AM"
        if h == 12: return "12 PM"
        return f"{int(h - 12)} PM"

    hourly_labor['Time_Label'] = hourly_labor['Hour'].apply(format_time)

    bar_colors = ['#5a67d8'] * len(hourly_labor)
    leak_alerts = ""
    top_3_hours = []

    total_labor = hourly_labor['Spent'].sum()
    total_rev = 0

    has_sales = not s_df.empty and rev_col in s_df.columns
    if has_sales:
        s_df[rev_col] = pd.to_numeric(s_df[rev_col].astype(str).str.replace('[$,]', '', regex=True),
                                      errors='coerce').fillna(0)
        total_rev = s_df[rev_col].sum()
        s_df['Hour'] = s_df['Date'].dt.hour
        hourly_sales = s_df.groupby('Hour')[rev_col].sum().reset_index()
        comparison = pd.merge(hourly_labor, hourly_sales, on='Hour', how='inner')

        if not comparison.empty:
            comparison['Labor_Ratio'] = (comparison['Spent'] / comparison[rev_col]) * 100
            top_3_hours = comparison.nlargest(3, 'Labor_Ratio')['Hour'].tolist()
            bar_colors = ['#f56565' if h in top_3_hours else '#5a67d8' for h in hourly_labor['Hour']]

            leaks = comparison[comparison['Labor_Ratio'] > (threshold or 30)]
            if not leaks.empty:
                leak_list = ", ".join([format_time(h) for h in leaks['Hour']])
                leak_alerts = html.Div([
                    html.Strong("⚠️ LABOR LEAK DETECTED: "),
                    f"Labor exceeded {threshold}% of sales at: {leak_list}."
                ], style={'color': '#c53030', 'backgroundColor': '#fff5f5', 'padding': '15px', 'borderRadius': '10px',
                          'border': '1px solid #feb2b2'})

    if all(c == '#5a67d8' for c in bar_colors):
        top_3_hours = hourly_labor.nlargest(3, 'Spent')['Hour'].tolist()
        bar_colors = ['#f56565' if h in top_3_hours else '#5a67d8' for h in hourly_labor['Hour']]

    labor_pct = (total_labor / total_rev * 100) if total_rev > 0 else 0
    priority_total = hourly_labor[hourly_labor['Hour'].isin(top_3_hours)]['Spent'].sum()
    savings = priority_total * 0.10

    # GENERATE CHEF'S MONDAY SUMMARY
    summary_text = [
        html.H4("👨‍🍳 Chef's Weekly Strategy", style={'margin-top': '0', 'color': '#5a67d8'}),
        html.P(f"This week, your labor-to-sales ratio is sitting at {labor_pct:.1f}%.")
    ]
    if not top_3_hours:
        summary_text.append(html.P(
            "Your labor distribution looks stable. Focus on maintaining prep efficiency during the morning shifts."))
    else:
        worst_hour = format_time(top_3_hours[0])
        summary_text.append(html.P(
            f"The most critical opportunity is at {worst_hour}. By reducing labor by just 10% in your priority windows, "
            f"you could save approximately ${savings:,.2f} this week. "
            "I recommend reviewing your 'yield and trim' prep tasks to see if they can be moved out of these peak cost hours."
        ))

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
    fig.update_layout(title="Labor Cost by Hour (Rose = Critical Priority)", template="plotly_white",
                      yaxis_tickprefix='$', font_family="Inter",
                      xaxis={'categoryorder': 'array', 'categoryarray': hourly_labor['Time_Label'].tolist()})

    return fig, leak_alerts, f"${total_labor:,.2f}", f"{labor_pct:.1f}%", f"${savings:,.2f}", summary_text


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

    topline = [html.Div([html.Small("LOW STOCK ALERTS"), html.H2(f"{low} Items", style={'margin': '5px 0'})],
                        style={'flex': '1', 'backgroundColor': '#718096', 'color': 'white', 'padding': '20px',
                               'borderRadius': '12px', 'textAlign': 'center'})]

    display_df = df.nlargest(15, stock)
    colors = ['#f56565' if v < float(thresh or 0) else '#a0aec0' for v in display_df[stock]]
    fig = px.bar(display_df, x=name if name else display_df.index, y=stock,
                 title="Inventory Levels (Rose = Below Reorder Pt)", text_auto='.0f')
    fig.update_traces(marker_color=colors, opacity=0.85, textposition='outside')
    fig.update_layout(template="plotly_white", font_family="Inter")
    return topline, fig


if __name__ == '__main__':
    app.run(debug=True)