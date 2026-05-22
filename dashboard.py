import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Supply Chain Carbon Tracker",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; }
.block-container { padding-top: 1.5rem; }
.section-header {
    background: linear-gradient(90deg, #1A5632, #2D8653);
    color: white; padding: 8px 16px; border-radius: 6px;
    font-weight: 600; font-size: 0.95rem; margin: 1rem 0 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Data ──────────────────────────────────────────────────────────────────────
MATERIAL_EF = {
    "Wheat grain": 0.58, "Sugar (refined)": 0.62, "Vegetable oils": 3.30,
    "Dairy ingredients": 3.20, "Packaging — HDPE": 1.85, "Packaging — recycled": 0.43,
    "Chemical additives": 2.10, "Metal components": 1.89
}
TRANSPORT_EF = {
    "Road-HGV": 0.062, "Road-Med": 0.103, "Rail-Diesel": 0.028,
    "Rail-Electric": 0.016, "Sea": 0.008, "Air": 0.602
}
ELECTRICITY_EF = 0.716
DIESEL_EF = 2.68
WASTE_EF = 0.558

raw_suppliers = [
    ["S-01","AgriSource Punjab",       "Tier 1","Raw Materials",      "Punjab",        85.0, 42000,1800,"Wheat grain",       180000,"Road-HGV",   420,90, 2400],
    ["S-02","SugarCo Maharashtra",     "Tier 1","Raw Materials",      "Maharashtra",   62.0, 31000, 900,"Sugar (refined)",    95000,"Road-HGV",   680,48, 1200],
    ["S-03","PalmOil Traders",         "Tier 1","Raw Materials",      "Karnataka",     48.0, 18000, 600,"Vegetable oils",     72000,"Road-Med",   310,36,  900],
    ["S-04","DairyLink Cooperative",   "Tier 1","Raw Materials",      "Gujarat",       74.0, 55000,2100,"Dairy ingredients",  65000,"Road-HGV",   520,33,  800],
    ["S-05","PackRight Industries",    "Tier 1","Packaging",          "Tamil Nadu",    55.0, 28000, 800,"Packaging — HDPE",   48000,"Rail-Diesel",980,24,  600],
    ["S-06","GreenBox Cartons",        "Tier 1","Packaging",          "Haryana",       38.0, 22000, 500,"Packaging — recycled",62000,"Road-HGV", 210,31,  750],
    ["S-07","ChemAdd Solutions",       "Tier 1","Chemical Additives", "Gujarat",       29.0, 15000, 400,"Chemical additives", 18000,"Road-Med",  460, 9,  220],
    ["S-08","MetalForm Components",    "Tier 1","Industrial Inputs",  "Maharashtra",   33.0, 38000,1200,"Metal components",   25000,"Road-HGV",  340,13,  310],
    ["S-09","GrainTrade East",         "Tier 2","Raw Materials",      "West Bengal",   42.0, 19000, 750,"Wheat grain",        95000,"Rail-Diesel",1140,48, 1100],
    ["S-10","SoyaPress Foods",         "Tier 2","Raw Materials",      "Madhya Pradesh",36.0, 21000, 680,"Vegetable oils",     55000,"Road-HGV",  590,28,  670],
    ["S-11","EcoPack Vietnam",         "Tier 2","Packaging",          "Vietnam",       25.0, 12000, 350,"Packaging — HDPE",   30000,"Sea",       5800,30,  420],
    ["S-12","SpiceSource Kerala",      "Tier 2","Chemical Additives", "Kerala",        18.0,  9500, 280,"Chemical additives", 12000,"Road-Med",  810, 6,  180],
]

cols = ["id","name","tier","category","state","spend","electricity_kwh","diesel_litres",
        "material_type","material_kg","transport_mode","distance_km","cargo_tonnes","waste_kg"]

df_base = pd.DataFrame(raw_suppliers, columns=cols)

def calc_emissions(df, elec_ef=ELECTRICITY_EF, diesel_ef=DIESEL_EF, 
                   rail_pct=0.0, recycled_pct=0.0, renew_pct=0.0):
    d = df.copy()
    effective_elec_ef = elec_ef * (1 - renew_pct * 0.94)

    d["scope2"] = d["electricity_kwh"] * effective_elec_ef / 1000

    d["scope1"] = d["diesel_litres"] * diesel_ef / 1000

    def mat_ef(row):
        ef = MATERIAL_EF.get(row["material_type"], 1.0)
        if "Packaging" in row["material_type"] and recycled_pct > 0:
            ef_recycled = MATERIAL_EF.get("Packaging — recycled", 0.43)
            ef = ef * (1 - recycled_pct) + ef_recycled * recycled_pct
        return row["material_kg"] * ef / 1000
    d["scope3_goods"] = d.apply(mat_ef, axis=1)

    def trans_ef(row):
        mode = row["transport_mode"]
        base_ef = TRANSPORT_EF.get(mode, 0.062)
        if mode in ["Road-HGV","Road-Med"] and rail_pct > 0:
            rail_ef = TRANSPORT_EF["Rail-Diesel"]
            effective_ef = base_ef * (1 - rail_pct) + rail_ef * rail_pct
        else:
            effective_ef = base_ef
        return row["cargo_tonnes"] * row["distance_km"] * effective_ef / 1000
    d["scope3_transport"] = d.apply(trans_ef, axis=1)

    d["scope3_waste"] = d["waste_kg"] * WASTE_EF / 1000
    d["scope3_total"] = d["scope3_goods"] + d["scope3_transport"] + d["scope3_waste"]
    d["total"] = d["scope2"] + d["scope1"] + d["scope3_total"]
    return d

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌿 Carbon Tracker")
    st.markdown("**GreenFoods India Ltd.** | FY2024")
    st.divider()

    st.markdown("### 🔀 Scenario Controls")
    rail_shift = st.slider("Modal shift: Road → Rail (%)", 0, 80, 0, 5,
                           help="% of road freight shifted to rail") / 100
    recycled_switch = st.slider("Switch to recycled packaging (%)", 0, 100, 0, 10,
                                help="% of virgin packaging replaced with recycled") / 100
    renewable_pct = st.slider("Renewable energy at Tier 1 (%)", 0, 100, 0, 10,
                              help="% of electricity from renewables at Tier 1 sites") / 100

    st.divider()
    st.markdown("### 🏭 Filter Suppliers")
    tiers = st.multiselect("Tier", ["Tier 1","Tier 2"], default=["Tier 1","Tier 2"])
    categories = st.multiselect("Category", df_base["category"].unique().tolist(),
                                 default=df_base["category"].unique().tolist())
    st.divider()
    st.caption("📊 Emission factors: GHG Protocol / GLEC 2023 / IPCC AR6 / CEA India")

# ── Compute ───────────────────────────────────────────────────────────────────
df = calc_emissions(df_base, rail_pct=rail_shift, recycled_pct=recycled_switch, renew_pct=renewable_pct)
df_base_calc = calc_emissions(df_base)

df_filtered = df[df["tier"].isin(tiers) & df["category"].isin(categories)]
df_base_filt = df_base_calc[df_base_calc["tier"].isin(tiers) & df_base_calc["category"].isin(categories)]

total_now = df_filtered["total"].sum()
total_base = df_base_filt["total"].sum()
savings = total_base - total_now
pct_reduction = savings / total_base if total_base > 0 else 0
sbt_target = 0.30

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🌿 Supply Chain Carbon Footprint Tracker")
st.caption("GHG Protocol — Scope 1 · Scope 2 · Scope 3  |  FMCG Sector  |  12 Suppliers  |  Base Year FY2024")

# ── KPI Row ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Emissions", f"{total_now:.1f} tCO₂e",
          f"{-savings:.1f} tCO₂e vs base" if savings != 0 else "Base case")
k2.metric("Scope 3 Share", f"{(df_filtered['scope3_total'].sum()/total_now*100):.1f}%", "of total")
k3.metric("Top Emitter", df_filtered.loc[df_filtered['total'].idxmax(),'name'] if len(df_filtered)>0 else "—",
          f"{df_filtered['total'].max():.1f} tCO₂e" if len(df_filtered)>0 else "")
k4.metric("Scenario Savings", f"{savings:.1f} tCO₂e", f"{pct_reduction:.1%} reduction")
sbt_gap = total_base * sbt_target - savings
k5.metric("SBT 2030 Gap", f"{max(sbt_gap,0):.1f} tCO₂e",
          "✅ Target met!" if sbt_gap <= 0 else f"{pct_reduction:.1%} / 30% needed")

st.divider()

# ── Row 1: Bar Chart + Scope Breakdown ───────────────────────────────────────
c1, c2 = st.columns([2, 1])

with c1:
    st.markdown('<div class="section-header">📊 Emissions by Supplier</div>', unsafe_allow_html=True)
    df_sorted = df_filtered.sort_values("total", ascending=True)
    colors = ["#1A5632" if t == "Tier 1" else "#5B9E78" for t in df_sorted["tier"]]
    fig_bar = go.Figure(go.Bar(
        x=df_sorted["total"], y=df_sorted["name"],
        orientation="h",
        marker_color=colors,
        text=df_sorted["total"].round(1),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:.1f} tCO₂e<extra></extra>"
    ))
    fig_bar.update_layout(
        height=400, margin=dict(l=0,r=30,t=10,b=10),
        xaxis_title="tCO₂e", yaxis_title="",
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Arial", size=11),
        xaxis=dict(gridcolor="#EEEEEE"),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with c2:
    st.markdown('<div class="section-header">🥧 Emissions by Scope</div>', unsafe_allow_html=True)
    scope_vals = {
        "Scope 1 (Fuel)": df_filtered["scope1"].sum(),
        "Scope 2 (Electricity)": df_filtered["scope2"].sum(),
        "Scope 3 Cat.1\n(Goods)": df_filtered["scope3_goods"].sum(),
        "Scope 3 Cat.4\n(Transport)": df_filtered["scope3_transport"].sum(),
        "Scope 3 Cat.5\n(Waste)": df_filtered["scope3_waste"].sum(),
    }
    fig_pie = go.Figure(go.Pie(
        labels=list(scope_vals.keys()),
        values=[round(v,1) for v in scope_vals.values()],
        hole=0.42,
        marker_colors=["#1A5632","#2D8653","#E67E22","#F39C12","#85929E"],
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value:.1f} tCO₂e (%{percent})<extra></extra>"
    ))
    fig_pie.update_layout(
        height=400, margin=dict(l=0,r=0,t=10,b=10),
        legend=dict(orientation="v", font=dict(size=10)),
        paper_bgcolor="white", font=dict(family="Arial")
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Row 2: Stacked bar by category + Scenario waterfall ──────────────────────
c3, c4 = st.columns([1, 1])

with c3:
    st.markdown('<div class="section-header">🔥 Emission Hotspot: Scope Breakdown per Supplier</div>', unsafe_allow_html=True)
    fig_stack = go.Figure()
    scope_map = {
        "Scope 1": ("scope1", "#1A5632"),
        "Scope 2": ("scope2", "#2D8653"),
        "S3: Goods": ("scope3_goods", "#E67E22"),
        "S3: Transport": ("scope3_transport", "#F39C12"),
        "S3: Waste": ("scope3_waste", "#AED6F1"),
    }
    df_s = df_filtered.sort_values("total", ascending=False)
    for label, (col, color) in scope_map.items():
        fig_stack.add_trace(go.Bar(
            name=label, x=df_s["name"], y=df_s[col].round(2),
            marker_color=color,
            hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y:.2f}} tCO₂e<extra></extra>"
        ))
    fig_stack.update_layout(
        barmode="stack", height=380, margin=dict(l=0,r=0,t=10,b=80),
        xaxis_tickangle=-35, plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", y=-0.35, font=dict(size=10)),
        yaxis_title="tCO₂e", font=dict(family="Arial", size=10),
        yaxis=dict(gridcolor="#EEEEEE"),
    )
    st.plotly_chart(fig_stack, use_container_width=True)

with c4:
    st.markdown('<div class="section-header">🔀 Scenario Waterfall — Reduction Pathway</div>', unsafe_allow_html=True)
    scenarios_wf = {
        "Base (FY2024)": total_base,
        "Rail shift": -calc_emissions(df_base, rail_pct=0.40)["total"].sum() + total_base
               if rail_shift == 0 else -(df_base_filt["total"].sum() - calc_emissions(df_base, rail_pct=0.40)[df_base_calc["tier"].isin(tiers) & df_base_calc["category"].isin(categories)]["total"].sum()),
        "Recycled pkg": None,
        "Renewables": None,
        "Projected": total_now,
    }
    base_em = total_base
    rail_em = calc_emissions(df_base, rail_pct=0.40)[df_base_calc["tier"].isin(tiers) & df_base_calc["category"].isin(categories)]["total"].sum()
    rec_em  = calc_emissions(df_base, rail_pct=0.40, recycled_pct=0.50)[df_base_calc["tier"].isin(tiers) & df_base_calc["category"].isin(categories)]["total"].sum()
    ren_em  = calc_emissions(df_base, rail_pct=0.40, recycled_pct=0.50, renew_pct=0.60)[df_base_calc["tier"].isin(tiers) & df_base_calc["category"].isin(categories)]["total"].sum()

    wf_labels = ["Base (FY2024)", "Rail shift\n(–40%)", "Recycled pkg\n(–50%)", "Renewables\n(–60%)", "Scenario\nTotal"]
    wf_vals   = [base_em, rail_em - base_em, rec_em - rail_em, ren_em - rec_em, ren_em]
    wf_colors = ["#1A5632","#E74C3C","#E74C3C","#E74C3C","#2D8653"]
    wf_measure= ["absolute","relative","relative","relative","total"]

    fig_wf = go.Figure(go.Waterfall(
        name="Pathway", measure=wf_measure,
        x=wf_labels, y=[round(v,1) for v in wf_vals],
        connector={"line": {"color": "#AAAAAA", "width": 1}},
        increasing={"marker": {"color": "#E74C3C"}},
        decreasing={"marker": {"color": "#2D8653"}},
        totals={"marker": {"color": "#1A5632"}},
        text=[f"{v:.1f}" for v in wf_vals],
        textposition="outside",
    ))
    fig_wf.add_hline(y=total_base*0.70, line_dash="dash", line_color="#F39C12",
                     annotation_text="SBT 2030 target (–30%)", annotation_position="right")
    fig_wf.update_layout(
        height=380, margin=dict(l=0,r=60,t=10,b=10),
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="tCO₂e", font=dict(family="Arial", size=10),
        showlegend=False, yaxis=dict(gridcolor="#EEEEEE"),
    )
    st.plotly_chart(fig_wf, use_container_width=True)

# ── Row 3: Data table + Tier comparison ──────────────────────────────────────
c5, c6 = st.columns([3, 1])

with c5:
    st.markdown('<div class="section-header">📋 Supplier Emission Detail</div>', unsafe_allow_html=True)
    display_cols = ["id","name","tier","category","scope1","scope2","scope3_goods",
                    "scope3_transport","scope3_waste","scope3_total","total"]
    display_labels = ["ID","Supplier","Tier","Category","Scope 1","Scope 2",
                      "S3:Goods","S3:Trans.","S3:Waste","S3 Total","TOTAL tCO₂e"]
    df_display = df_filtered[display_cols].round(2).copy()
    df_display.columns = display_labels
    st.dataframe(
        df_display.style
            .background_gradient(subset=["TOTAL tCO₂e"], cmap="YlOrRd")
            .format("{:.2f}", subset=["Scope 1","Scope 2","S3:Goods","S3:Trans.","S3:Waste","S3 Total","TOTAL tCO₂e"]),
        use_container_width=True, height=320, hide_index=True
    )

with c6:
    st.markdown('<div class="section-header">📊 By Tier</div>', unsafe_allow_html=True)
    tier_summary = df_filtered.groupby("tier")["total"].agg(["sum","mean","count"]).reset_index()
    tier_summary.columns = ["Tier","Total tCO₂e","Avg/Supplier","Count"]
    tier_summary = tier_summary.round(1)
    fig_tier = go.Figure(go.Bar(
        x=tier_summary["Tier"], y=tier_summary["Total tCO₂e"],
        marker_color=["#1A5632","#5B9E78"],
        text=tier_summary["Total tCO₂e"],
        textposition="outside",
    ))
    fig_tier.update_layout(
        height=320, margin=dict(l=0,r=0,t=10,b=10),
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="tCO₂e", font=dict(family="Arial", size=11),
        yaxis=dict(gridcolor="#EEEEEE"),
    )
    st.plotly_chart(fig_tier, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("📊 **Data sources:** Emission factors from GHG Protocol Corporate Standard, GLEC Framework 2023, IPCC AR6, CEA India Grid EF 2023, Ecoinvent 3.9  |  Model built for portfolio demonstration  |  Sector: FMCG–Food & Beverage  |  All values in tCO₂e")
