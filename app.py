from __future__ import annotations

import os

from dotenv import load_dotenv
import streamlit as st

from agent import answer, is_configured
from analytics import morning_brief, position_weights, risk_flags
from data import load_closed_positions, load_open_positions, load_totals, source_status
from memory import add_message, clear_messages, recent_messages
from macro_data import fred_snapshot, horizon_map
from prices import live_prices


load_dotenv()
st.set_page_config(page_title="Investor OS", page_icon="📈", layout="wide")

st.markdown("""
<style>
  .stApp { background: #0b1020; color: #e6edf7; }
  [data-testid="stMetric"] { background: #121a2f; padding: 14px; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

positions = load_open_positions()
totals = load_totals()
weighted = position_weights(positions)
source_date = source_status()

st.title("Investor OS")
st.caption(f"Portfolio snapshot recorded through {source_date}. It is not live market data.")

cash = totals.get("Uninvested cash")
net_gain = totals.get("Net gain after fees")
return_rate = totals.get("Reported total return")
portfolio_value = totals.get("Workbook-implied portfolio value")

metrics = st.columns(4)
metrics[0].metric("Workbook-implied portfolio", f"EUR {portfolio_value:,.2f}" if portfolio_value else "Not recorded")
metrics[1].metric("Open cost basis", f"EUR {totals.get('Open-position cost basis', 0):,.2f}")
metrics[2].metric("Cash recorded", f"EUR {cash:,.2f}" if cash is not None else "Not recorded")
metrics[3].metric("Net gain after fees", f"EUR {net_gain:,.2f}" if net_gain is not None else "Not recorded", f"{return_rate:.1f}%" if return_rate is not None else None)

overview, macro_tab, brief_tab, chat_tab, history_tab = st.tabs(["Portfolio", "Macro regime", "Morning brief", "Ask the agent", "Trade history"])

with overview:
    st.subheader("Open positions")
    display = weighted[["Holding", "Ticker", "Type", "Quantity", "Remaining cost basis (EUR)", "Unrealised P&L (EUR)", "Portfolio value (EUR)", "Weight"]].copy()
    st.dataframe(display, use_container_width=True, hide_index=True, column_config={
        "Weight": st.column_config.NumberColumn(format="%.1f%%"),
        "Remaining cost basis (EUR)": st.column_config.NumberColumn(format="EUR %.2f"),
        "Unrealised P&L (EUR)": st.column_config.NumberColumn(format="EUR %.2f"),
        "Portfolio value (EUR)": st.column_config.NumberColumn(format="EUR %.2f"),
    })
    st.subheader("Risk controls")
    for flag in risk_flags(positions):
        st.warning(flag)
    if st.button("Fetch latest reference prices"):
        with st.spinner("Fetching provider reference prices..."):
            quotes, warnings = live_prices(positions)
        if not quotes.empty:
            st.dataframe(quotes, use_container_width=True, hide_index=True, column_config={
                "Last close": st.column_config.NumberColumn(format="%.2f"),
                "Day change": st.column_config.NumberColumn(format="%.2f%%"),
            })
        for warning in warnings:
            st.caption(warning)
        st.caption("Reference prices are display-only. They are not converted to EUR and do not update the Investor OS.")

with macro_tab:
    st.subheader("Market map")
    st.caption("The big picture: risk today, the next few months, and the longer liquidity cycle.")
    if "market_map" not in st.session_state:
        st.session_state.market_map = horizon_map(fred_snapshot())
    if st.button("Refresh market map"):
        with st.spinner("Reading Treasury, credit, volatility, and liquidity data..."):
            st.session_state.market_map = horizon_map(fred_snapshot())
    columns = st.columns(3)
    for column, (label, entries) in zip(columns, st.session_state.market_map.items()):
        with column:
            st.markdown(f"### {label}")
            for entry in entries:
                st.write(f"• {entry}")

with brief_tab:
    st.markdown(morning_brief(positions, totals, source_date))
    st.download_button("Download brief", morning_brief(positions, totals, source_date), file_name="morning-brief.md", mime="text/markdown")

with chat_tab:
    if not is_configured():
        st.info("Add OPENAI_API_KEY to financial-agent/.env to enable the grounded chat. The dashboard runs without it.")
    for message in recent_messages():
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Ask about a holding, risk, thesis, or macro driver")
    if question:
        add_message("user", question)
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            if not is_configured():
                reply = "Chat is not configured yet. Add OPENAI_API_KEY to `financial-agent/.env`, then restart the dashboard."
                st.markdown(reply)
            else:
                with st.spinner("Reviewing your Investor OS..."):
                    reply = answer(question)
                st.markdown(reply)
        add_message("assistant", reply)
    if st.button("Reset chat memory"):
        clear_messages()
        st.rerun()

with history_tab:
    closed = load_closed_positions()
    st.subheader("Closed positions")
    st.dataframe(closed, use_container_width=True, hide_index=True)
    st.caption("Cumulative gains are imported from the workbook. Refresh the source files after broker updates.")
