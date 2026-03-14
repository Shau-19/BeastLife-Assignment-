import sqlite3
import random
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import plotly.express as px
import streamlit as st

from classifier.categorize import classify

DB = "data/beastlife.db"

CAT_COLORS = {
    "Order Tracking":     "#4361ee",
    "Delivery Delay":     "#f72585",
    "Refund Request":     "#7209b7",
    "Product Complaint":  "#3a0ca3",
    "Subscription Issue": "#4cc9f0",
    "Payment Failure":    "#f77f00",
    "General Inquiry":    "#06d6a0",
}

AUTO_REPLIES = {
    "Order Tracking":     "Hi! Share your order ID and we will send the live tracking link instantly.",
    "Subscription Issue": "Manage your plan here: beastlife.in/account/subscription",
    "General Inquiry":    "Delivery: 3-5 days | Returns: 7 days | Free delivery above Rs 499",
}

ESCALATION = {
    "Delivery Delay":    "Assign to logistics team",
    "Refund Request":    "Assign to billing team",
    "Product Complaint": "Assign to quality team — HIGH PRIORITY",
    "Payment Failure":   "Assign to payments team",
}

AUTOMATION_TIPS = [
    ("Order Tracking",     "28%", "Auto-fetch order status via API and reply with tracking link. No agent needed."),
    ("Delivery Delay",     "20%", "Proactively detect delays and send apology + revised ETA before customer asks."),
    ("Refund Request",     "16%", "Auto-check eligibility and trigger refund workflow or escalate to billing."),
    ("Product Complaint",  "14%", "Auto-log complaint and assign to quality team with high priority."),
    ("Subscription Issue", "10%", "Self-service bot for pause, cancel, upgrade. 70% auto-handled."),
    ("Payment Failure",    "7%",  "Detect failed transactions and auto-send payment retry link."),
]

# confidence threshold — same as api.py
CONFIDENCE_THRESHOLD = 0.65


# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="Beastlife Intelligence", page_icon="🐾", layout="wide")

st.markdown("""
<style>
  .kpi  { background:#1a1a2e; border-radius:10px; padding:18px; text-align:center; color:white; }
  .kpi .val { font-size:2rem; font-weight:700; color:#e94560; }
  .kpi .lbl { font-size:0.8rem; color:#aab4d4; margin-top:4px; }
  .qrow { background:#1a1a2e; border-left:4px solid #ccc; border-radius:6px;
          padding:10px 14px; margin-bottom:8px; font-size:0.87rem; color:white; }
  .tip  { border-radius:10px; padding:14px 18px; color:white; margin-bottom:10px; }
  .tip h4 { margin:0 0 4px 0; font-size:0.9rem; }
  .tip p  { margin:0; font-size:0.8rem; opacity:0.9; }
</style>
""", unsafe_allow_html=True)


# ── db helpers ────────────────────────────────────────────────────────────────

def load_data(channel="All", category="All", status="All"):
    conn = sqlite3.connect(DB)
    q, args = "SELECT * FROM queries WHERE 1=1", []
    if channel  != "All": q += " AND channel=?";  args.append(channel)
    if category != "All": q += " AND category=?"; args.append(category)
    if status   != "All": q += " AND status=?";   args.append(status)
    df = pd.read_sql_query(q + " ORDER BY timestamp DESC", conn, params=args)
    conn.close()
    return df


def save_query(message, channel, category, confidence, provider, auto_resolved, sentiment):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT INTO queries "
        "(id, message, category, channel, timestamp, status, confidence, auto_resolved, ai_provider) "
        "VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
        (random.randint(900000, 999999), message, category, channel,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         confidence, 1 if auto_resolved else 0, f"{provider} | sentiment:{sentiment}")
    )
    conn.commit()
    conn.close()


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🐾 Beastlife")
    st.markdown("**Customer Intelligence Hub**")
    st.divider()

    provider = st.selectbox(
        "AI Provider",
        ["auto", "groq", "openai", "mock"],
        format_func=lambda x: {
            "auto":   "Auto (Groq → OpenAI → Rules)",
            "groq":   "Groq — llama-3.3-70b",
            "openai": "OpenAI — gpt-4o-mini",
            "mock":   "Rule-Based (Offline)",
        }[x],
    )
    st.divider()
    channel  = st.selectbox("Channel",  ["All", "WhatsApp", "Instagram DM", "Email", "Website Chat"])
    category = st.selectbox("Category", ["All"] + list(CAT_COLORS.keys()))
    status   = st.selectbox("Status",   ["All", "open", "resolved", "escalated"])
    if st.button("Refresh", use_container_width=True):
        st.rerun()


# ── load data ─────────────────────────────────────────────────────────────────

df    = load_data(channel, category, status)
total = len(df)

st.markdown("# 🐾 Beastlife — Customer Intelligence Dashboard")
st.divider()


# ── kpi row ───────────────────────────────────────────────────────────────────

c1, c2, c3, c4, c5 = st.columns(5)
open_n      = len(df[df.status == "open"])
resolved_n  = len(df[df.status == "resolved"])
escalated_n = len(df[df.status == "escalated"])
auto_pct    = round(len(df[df.auto_resolved == 1]) / total * 100) if total else 0

for col, val, lbl in zip(
    [c1, c2, c3, c4, c5],
    [total, open_n, resolved_n, escalated_n, f"{auto_pct}%"],
    ["Total Queries", "Open", "Resolved", "Escalated", "Auto-Resolved"],
):
    col.markdown(
        f'<div class="kpi"><div class="val">{val}</div><div class="lbl">{lbl}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)


# ── top issues + provider usage ───────────────────────────────────────────────
# quick insight widgets for managers

ti_col, pv_col = st.columns(2)

with ti_col:
    st.markdown("#### Top Customer Issues")
    top3 = df.category.value_counts().head(3)
    for i, (cat, cnt) in enumerate(top3.items(), 1):
        pct = round(cnt / total * 100) if total else 0
        st.markdown(f"**{i}. {cat}** — {pct}%")

with pv_col:
    st.markdown("#### AI Provider Usage")
    if "ai_provider" in df.columns and df["ai_provider"].notna().any():
        # extract provider name before the pipe separator
        prov = df["ai_provider"].dropna().str.split("|").str[0].str.strip()
        for p, cnt in prov.value_counts().items():
            st.markdown(f"**{p}** — {round(cnt/total*100)}%")
    else:
        st.caption("Run the live classifier to see provider stats")

st.divider()


# ── charts row 1: issue distribution + channel ────────────────────────────────

col1, col2 = st.columns([1.2, 1])

with col1:
    st.markdown("#### Issue Distribution")
    counts = df.category.value_counts().reset_index()
    counts.columns = ["category", "count"]
    fig = px.pie(counts, names="category", values="count", hole=0.5,
                 color="category", color_discrete_map=CAT_COLORS)
    fig.update_traces(textinfo="label+percent", textposition="outside")
    fig.update_layout(showlegend=False, height=320,
                      margin=dict(t=10, b=10, l=10, r=10),
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("#### Queries by Channel")
    ch = df.channel.value_counts().reset_index()
    ch.columns = ["channel", "count"]
    fig2 = px.bar(ch, x="count", y="channel", orientation="h",
                  text="count", color_discrete_sequence=["#4361ee"])
    fig2.update_traces(textposition="outside")
    fig2.update_layout(showlegend=False, height=320,
                       margin=dict(t=10, b=10, l=10, r=10),
                       paper_bgcolor="rgba(0,0,0,0)",
                       xaxis_title="", yaxis_title="")
    st.plotly_chart(fig2, use_container_width=True)


# ── charts row 2: weekly trend + status ──────────────────────────────────────

col3, col4 = st.columns([1.6, 1])

with col3:
    st.markdown("#### Weekly Trend")
    if not df.empty:
        df2 = df.copy()
        df2["timestamp"] = pd.to_datetime(df2["timestamp"])
        df2["week"]      = df2["timestamp"].dt.to_period("W").astype(str)
        weekly = df2.groupby(["week", "category"]).size().reset_index(name="count")
        fig3 = px.area(weekly, x="week", y="count",
                       color="category", color_discrete_map=CAT_COLORS)
        fig3.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10),
                           paper_bgcolor="rgba(0,0,0,0)",
                           legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig3, use_container_width=True)

with col4:
    st.markdown("#### Status Breakdown")
    st_cnt = df.status.value_counts().reset_index()
    st_cnt.columns = ["status", "count"]
    fig4 = px.pie(st_cnt, names="status", values="count", hole=0.55,
                  color="status",
                  color_discrete_map={"open": "#f72585", "resolved": "#06d6a0", "escalated": "#f77f00"})
    fig4.update_traces(textinfo="label+percent", textposition="outside")
    fig4.update_layout(showlegend=False, height=280,
                       margin=dict(t=10, b=10, l=10, r=10),
                       paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig4, use_container_width=True)

st.divider()


# ── live classifier ───────────────────────────────────────────────────────────

left, right = st.columns([1.1, 1])

with left:
    st.markdown("#### Live Query Classifier")
    st.caption("Guardrails active: input sanitization · output validation · confidence threshold · sentiment check")

    msg    = st.text_area("Paste a customer message", height=90,
                          placeholder="e.g. Where is my order #845231?")
    ch_sel = st.selectbox("Channel", ["WhatsApp", "Instagram DM", "Email", "Website Chat"])

    if st.button("Classify", type="primary", use_container_width=True):
        if msg.strip():
            with st.spinner("Classifying..."):
                res = classify(msg, provider=provider)

            cat       = res["category"]
            conf      = res["confidence"]
            sentiment = res["sentiment"]

            # apply confidence threshold guardrail
            auto = res["auto_resolvable"] and conf >= CONFIDENCE_THRESHOLD

            st.success(f"**{cat}**")

            a, b, c, d = st.columns(4)
            a.metric("Confidence",  f"{conf:.0%}")
            b.metric("Sentiment",   "😡 Negative" if sentiment == "negative" else "😊 Neutral")
            c.metric("Threshold",   "✅ Pass" if conf >= CONFIDENCE_THRESHOLD else "❌ Fail")
            d.metric("Auto-Reply",  "Yes" if auto else "No")

            # show why decision was made
            if sentiment == "negative":
                st.error("Negative sentiment detected → forced escalation regardless of category")
            elif conf < CONFIDENCE_THRESHOLD:
                st.warning(f"Confidence {conf:.0%} below threshold {CONFIDENCE_THRESHOLD:.0%} → escalated for safety")
            elif auto:
                st.info(f"Auto-reply: {AUTO_REPLIES[cat]}")
            else:
                st.warning(f"Escalate: {ESCALATION.get(cat, 'Assign to agent')}")

            save_query(msg, ch_sel, cat, conf, res["provider"], auto, sentiment)
        else:
            st.warning("Please enter a message.")

with right:
    st.markdown("#### Recent Queries")
    for _, row in df.head(10).iterrows():
        color = CAT_COLORS.get(row.category, "#888")
        st.markdown(f"""
        <div class="qrow" style="border-left-color:{color}">
          <span style="background:{color};color:white;padding:2px 8px;
                border-radius:10px;font-size:0.72rem">{row.category}</span>
          <span style="color:#aab4d4;font-size:0.75rem"> · {row.channel} · {str(row.timestamp)[:16]}</span>
          <br><span style="margin-top:4px;display:block">
            {row.message[:85]}{"..." if len(row.message) > 85 else ""}
          </span>
        </div>""", unsafe_allow_html=True)

st.divider()


# ── automation opportunities ──────────────────────────────────────────────────

st.markdown("#### Automation Opportunities")
cols = st.columns(3)
for i, (cat, pct, desc) in enumerate(AUTOMATION_TIPS):
    color = CAT_COLORS.get(cat, "#667eea")
    cols[i % 3].markdown(f"""
    <div class="tip" style="background:{color}cc">
      <h4>{cat} — {pct} of queries</h4>
      <p>{desc}</p>
    </div>""", unsafe_allow_html=True)


# ── raw data ──────────────────────────────────────────────────────────────────

with st.expander("Raw Data"):
    st.dataframe(
        df[["id", "message", "category", "channel", "status", "confidence", "timestamp"]],
        use_container_width=True, height=300,
    )