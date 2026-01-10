import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

# ==========================================
# 1. ENTERPRISE CONFIGURATION & SESSION STATE
# ==========================================
st.set_page_config(
    page_title="StockPilot | Chef Statement Enterprise",
    page_icon="👨‍🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'audit_history' not in st.session_state:
    st.session_state['audit_history'] = []

# ==========================================
# 2. PROFESSIONAL CSS STYLING (FIXED)
# ==========================================
st.markdown("""
    <style>
    :root { --primary: #1E3A8A; --secondary: #3B82F6; --background: #F9FAFB; }
    .main { background-color: var(--background); }
    .stMetric { 
        background-color: #ffffff; 
        padding: 24px !important; 
        border-radius: 15px !important; 
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
        border-left: 5px solid var(--primary) !important;
    }
    .report-card { 
        background: white; 
        padding: 2rem; 
        border-radius: 1rem; 
        border: 1px solid #E5E7EB; 
        margin-bottom: 1rem; 
    }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stButton>button { width: 100%; border-radius: 8px; background-color: var(--primary); color: white; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. GLOBAL DATA DICTIONARY (Hover Call-outs)
# ==========================================
tooltips = {
    "revenue": "Total Sales Revenue before expenses. Your operational baseline.",
    "cogs": "Cost of Goods Sold: The direct cost to acquire or produce the items sold.",
    "turnover": "Inventory Turnover: Measures efficiency. Higher = you move stock faster.",
    "dsi": "Days Sales of Inventory: The average days your cash is trapped in a product.",
    "gmroi": "Gross Margin Return on Investment: Profit earned per dollar invested in stock.",
    "rop": "Reorder Point: The mathematical tripwire that triggers a new purchase order.",
    "ss": "Safety Stock: The buffer required to protect against supplier delays.",
    "sell_through": "Velocity metric: Percentage of inventory sold relative to amount received.",
    "stock_to_sales": "Compares on-hand inventory value to actual sales value.",
    "recovery": "Estimated profit reclaimed by optimizing stock and reducing holding costs."
}


# ==========================================
# 4. ADVANCED ANALYTIC ENGINE
# ==========================================
class StockPilotEngine:
    @staticmethod
    def calculate_diagnostics(data):
        # 4.1 Financial Integrity
        gp = data['revenue'] - data['cogs']
        margin_pct = (gp / data['revenue']) * 100 if data['revenue'] > 0 else 0

        # 4.2 The KPI Suite
        turnover = data['cogs'] / data['avg_inv'] if data['avg_inv'] > 0 else 0
        dsi = 365 / turnover if turnover > 0 else 0
        gmroi = gp / data['avg_inv'] if data['avg_inv'] > 0 else 0
        sell_through = (data['units_sold'] / data['units_rec']) * 100 if data['units_rec'] > 0 else 0
        stock_to_sales = data['avg_inv'] / data['revenue'] if data['revenue'] > 0 else 0

        # 4.3 Advanced Supply Chain Logic (Demand Volatility)
        # Using a 1.65 Z-score for a 95% Service Level
        daily_demand_sigma = data['daily_sales'] * 0.20  # 20% volatility assumption
        safety_stock = 1.65 * np.sqrt(data['lead_time']) * daily_demand_sigma
        rop = (data['daily_sales'] * data['lead_time']) + safety_stock

        # 4.4 Economic Impact Model
        carrying_cost_rate = 0.25  # Industry standard 25%
        holding_costs = data['avg_inv'] * carrying_cost_rate
        recovery = (holding_costs * 0.15) + (gp * 0.05)  # 15% efficiency + 5% stockout prevention

        return {
            "gp": gp, "margin": margin_pct, "turnover": turnover, "dsi": dsi,
            "gmroi": gmroi, "sell_through": sell_through, "sts": stock_to_sales,
            "rop": rop, "ss": safety_stock, "recovery": recovery
        }


# ==========================================
# 5. SIDEBAR: DATA INGESTION & CONTROL
# ==========================================
st.sidebar.title("👨‍💻 Analyst Control Panel")
st.sidebar.markdown("Configure client parameters for the Chef Statement.")

with st.sidebar.expander("💳 Financial Core", expanded=True):
    rev_val = st.number_input("Total Revenue ($)", 1000, 10000000, 450000, help=tooltips['revenue'])
    cogs_val = st.number_input("Total COGS ($)", 500, 8000000, 280000, help=tooltips['cogs'])
    inv_val = st.number_input("Avg Inventory Value ($)", 100, 2000000, 85000)

with st.sidebar.expander("📦 Supply Chain & Velocity", expanded=True):
    d_sales = st.number_input("Avg Daily Units Sold", 1, 1000, 65)
    l_time = st.number_input("Lead Time (Days)", 1, 120, 14)
    u_sold = st.number_input("Units Sold (Period)", value=1950)
    u_rec = st.number_input("Units Received (Period)", value=2200)
    on_hand = st.number_input("Current Stock on Hand", value=740)

# Process Data
inputs = {
    'revenue': rev_val, 'cogs': cogs_val, 'avg_inv': inv_val,
    'daily_sales': d_sales, 'lead_time': l_time,
    'units_sold': u_sold, 'units_rec': u_rec
}
res = StockPilotEngine.calculate_diagnostics(inputs)

# ==========================================
# 6. MAIN DASHBOARD RENDER
# ==========================================
st.title("👨‍🍳 The Chef Statement")
st.markdown(f"**Audit Status:** Operational Diagnostic Active | **Timestamp:** {datetime.now().strftime('%H:%M:%S')}")

tabs = st.tabs(["🎯 Strategic Assessment", "📊 Robust Inventory Model", "🔮 Capital Simulator", "🛡️ Competitive Moat",
                "📝 Audit History"])

# --- TAB 1: STRATEGIC ASSESSMENT ---
with tabs[0]:
    st.markdown("### Executive Summary: The Performance Gap")
    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.markdown(f"""
        <div class='report-card'>
        <h4>Operational Diagnostic</h4>
        Current <strong>Inventory Turnover</strong> is <strong>{res['turnover']:.2f}x</strong>. 
        Capital is illiquid for <strong>{res['dsi']:.0f} days</strong>. 
        <br><br>
        <strong>The Friction Point:</strong> Procurement data is lagging demand by 15%. 
        By automating ROP triggers, we estimate a <strong>${res['recovery']:,.2f}</strong> margin recovery.
        </div>
        """, unsafe_allow_html=True)

        # Plotly Margin Gauge
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=res['margin'],
            title={'text': "Gross Margin %"},
            gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#1E3A8A"},
                   'steps': [{'range': [0, 35], 'color': "#ff4b4b"}, {'range': [35, 100], 'color': "#00d400"}]}))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_b:
        st.metric("Margin Recovery Potential", f"${res['recovery']:,.2f}",
                  help=tooltips['recovery'], delta="Reclaimable")
        st.write("---")
        st.subheader("Priority Actions")
        st.warning("1. Liquitdate bottom 10% SKUs")
        st.info("2. Audit Supplier Lead Times")
        st.error("3. Implement Prescriptive ROP")

# --- TAB 2: ROBUST INVENTORY MODEL (KPIs) ---
with tabs[1]:
    st.markdown("### Operational Liquidity (KPI Suite)")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Turnover", f"{res['turnover']:.2f}x", help=tooltips['turnover'])
    k2.metric("DSI", f"{res['dsi']:.0f} Days", help=tooltips['dsi'])
    k3.metric("GMROI", f"${res['gmroi']:.2f}", help=tooltips['gmroi'])
    k4.metric("Sell-Through", f"{res['sell_through']:.1f}%", help=tooltips['sell_through'])
    k5.metric("Stock-to-Sales", f"{res['sts']:.2f}", help=tooltips['stock_to_sales'])

    st.markdown("---")

    p1, p2 = st.columns(2)
    with p1:
        st.subheader("Predictive Reorder Logic")
        st.metric("Reorder Point (ROP)", f"{int(res['rop'])} Units", help=tooltips['rop'])
        if on_hand < res['rop']:
            st.error(f"🚨 ALERT: Stock ({on_hand}) is BELOW trigger level. Order immediately.")
        else:
            st.success(f"✅ STABLE: Current stock ({on_hand}) is sufficient.")
        st.caption(f"Includes Safety Stock buffer of {int(res['ss'])} units (95% Service Level).")

    with p2:
        # Stock Status Bar Chart
        bar_df = pd.DataFrame({
            'Levels': ['On Hand', 'Reorder Point', 'Safety Stock'],
            'Quantity': [on_hand, res['rop'], res['ss']]
        })
        fig_bar = px.bar(bar_df, x='Levels', y='Quantity', color='Levels', title="Inventory Health Status")
        st.plotly_chart(fig_bar, use_container_width=True)

# --- TAB 3: CAPITAL SIMULATOR ---
with tabs[2]:
    st.header("Capital Liberation Simulator")
    st.write("Determine how operational efficiency converts to bankable cash.")

    s_col1, s_col2 = st.columns(2)
    with s_col1:
        reduction = st.slider("Improve Lead Time (Reduce Days):", 0, int(l_time), 0)
        new_lt = l_time - reduction

        # New ROP Calculation
        new_rop = (d_sales * new_lt) + (res['ss'] * 0.8)  # Improved LT reduces needed buffer
        cash_freed = (res['rop'] - new_rop) * (cogs_val / (u_sold if u_sold > 0 else 1))

    with s_col2:
        st.metric("Cash Unlocked", f"${max(0, cash_freed):,.2f}", delta=f"{reduction} Day Gain")
        st.info("Unlocked capital represents cash no longer required to sit in safety buffers.")

# --- TAB 4: COMPETITIVE MOAT ---
with tabs[3]:
    st.header("Strategic Advantage: Us vs. Standard Dashboards")
    moat_df = pd.DataFrame({
        "Feature": ["Data Silo Integration", "Prescriptive Diagnostics", "Z-Score Safety Logic", "Self-Funding ROI"],
        "Off-the-Shelf SaaS": ["❌ Manual Sync", "❌ Descriptive Only", "❌ Rigid Templates", "❌ Sunk Cost"],
        "StockPilot Partners": ["✅ Full-Stack Audit", "✅ Actionable (Monday Morning)", "✅ Custom-Built", "✅ ROI Driven"]
    })
    st.table(moat_df)

# --- TAB 5: AUDIT HISTORY (Session State Management) ---
with tabs[4]:
    st.subheader("Audit Log")
    if st.button("Save Current Assessment to Log"):
        entry = {"Timestamp": datetime.now(), "DSI": res['dsi'], "Recovery": res['recovery']}
        st.session_state['audit_history'].append(entry)
        st.success("Assessment Cached.")

    if st.session_state['audit_history']:
        st.write(pd.DataFrame(st.session_state['audit_history']))

st.markdown("---")
st.caption("Proprietary Model | Data Analysis Partners 2026 | StockPilot Alpha v4.2")