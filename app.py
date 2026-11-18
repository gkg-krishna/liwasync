"""
LiwaSync - Smart Campus Energy Management System (Proof of Concept)
Run:  streamlit run app.py
Student poll only (for a QR code on the classroom door):  http://<host>:8501/?view=student
"""
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_gen
import engine as E

DATA = Path(__file__).parent / "data"
if not (DATA / "rooms.csv").exists():
    data_gen.main(str(DATA))

st.set_page_config(page_title="LiwaSync", page_icon="⚡", layout="wide")

# ---------------------------------------------------------------- styling ---
STATUS_COL = {"Occupied": "#0ca30c", "Underutilised": "#fab219",
              "Empty · devices ON": "#d03b3b", "No-show": "#ec835a",
              "Empty · off": "#c3c2b7", "Pre-cooling": "#86b6ef"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"

st.markdown("""
<style>
.block-container {padding-top: 1.4rem;}
.ls-brand {display:flex;align-items:center;gap:.6rem;margin-bottom:.2rem}
.ls-brand h1 {font-size:1.9rem;margin:0;letter-spacing:-.02em}
.ls-sub {color:#52514e;margin-bottom:1rem}
.kpi {background:#fff;border:1px solid rgba(11,11,11,.10);border-radius:12px;padding:14px 16px}
.kpi .l {font-size:.78rem;color:#52514e;text-transform:uppercase;letter-spacing:.04em}
.kpi .v {font-size:1.7rem;font-weight:700;color:#0b0b0b;line-height:1.2}
.kpi .s {font-size:.8rem;color:#898781}
.bldg {font-weight:600;margin:.4rem 0 .3rem;color:#0b0b0b}
.grid {display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:8px;margin-bottom:12px}
.tile {border-radius:10px;padding:8px 10px;border:1px solid rgba(11,11,11,.10);background:#fff;
       border-left:6px solid var(--c);min-height:86px}
.tile .id {font-weight:700;font-size:.95rem}
.tile .st {font-size:.72rem;color:#52514e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile .occ {font-size:.85rem;margin-top:2px}
.tile .bar {height:5px;background:#f0efec;border-radius:3px;margin-top:4px;overflow:hidden}
.tile .bar i {display:block;height:100%;background:var(--c)}
.tile .dev {font-size:.7rem;color:#52514e;margin-top:3px;white-space:nowrap}
.legend span {display:inline-flex;align-items:center;gap:6px;margin-right:14px;font-size:.8rem;color:#52514e}
.legend b {width:12px;height:12px;border-radius:3px;display:inline-block}
.note {background:#f9f9f7;border:1px solid rgba(11,11,11,.08);border-radius:10px;padding:10px 14px;
       font-size:.85rem;color:#52514e}
</style>""", unsafe_allow_html=True)


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div>'
                 f'<div class="s">{sub}</div></div>', unsafe_allow_html=True)


def style_fig(fig, h=340):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=78, b=10), plot_bgcolor="#fcfcfb",
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(family="system-ui, sans-serif", color=INK2),
                      legend=dict(orientation="h", y=1.01, yanchor="bottom", x=0, title=None),
                      title=dict(y=0.985, yanchor="top", x=0.01, font=dict(color=INK, size=15)))
    fig.update_xaxes(gridcolor=GRID, linecolor="#c3c2b7", zeroline=False)
    fig.update_yaxes(gridcolor=GRID, linecolor="#c3c2b7", zeroline=False)
    return fig


@st.cache_data(show_spinner="Running LiwaSync analytics…")
def run(underuse, feedback_mtime):
    return E.build(str(DATA), underuse=underuse)


def fb_mtime():
    return (DATA / "feedback.csv").stat().st_mtime


# ----------------------------------------------------- STUDENT POLL VIEW ---
def liwatemp_form(rooms, key="poll", compact=False):
    with st.form(key, clear_on_submit=True):
        room = st.selectbox("Which classroom are you in?", rooms.room_id.tolist(), key=key + "_room")
        vote = st.radio("How does the temperature feel right now?",
                        ["🥶 Too cold", "🙂 Comfortable", "🥵 Too warm"],
                        horizontal=not compact, key=key + "_vote")
        comment = st.text_input("Suggestion (optional)", max_chars=140, key=key + "_c",
                                placeholder="e.g. AC vent blows directly on the front row")
        ok = st.form_submit_button("Submit anonymously", type="primary", width="stretch")
    if ok:
        now = datetime.now()
        day = E.DAY_ORDER[min(now.weekday(), 4)]
        week = int(pd.read_csv(DATA / "sessions.csv", usecols=["week"]).week.max())
        row = pd.DataFrame([{"week": week, "day": day, "hour": min(max(now.hour, 8), 17),
                             "room_id": room, "vote": vote.split(" ", 1)[1], "comment": comment.strip()}])
        row.to_csv(DATA / "feedback.csv", mode="a", header=False, index=False)
        st.success("Thank you! Your response was recorded anonymously - no name or ID is stored.")
        st.cache_data.clear()


if st.query_params.get("view") == "student":
    rooms = pd.read_csv(DATA / "rooms.csv")
    st.markdown('<div class="ls-brand"><h1>🌡️ LiwaTemp</h1></div>'
                '<div class="ls-sub">Anonymous classroom temperature feedback · Liwa University</div>',
                unsafe_allow_html=True)
    liwatemp_form(rooms, "student", compact=True)
    st.caption("Your vote helps facilities staff tune the air-conditioning - and save energy.")
    st.stop()

# --------------------------------------------------------------- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚡ LiwaSync")
    st.caption("Proof of concept · simulated campus data")
    st.markdown("**Simulated clock** (current week)")
    day = st.select_slider("Day", E.DAY_ORDER, value="Tue")
    hour = st.slider("Hour", 8, 17, 10, format="%d:00")
    st.divider()
    st.markdown("**Assumptions**")
    tariff = st.number_input("Electricity tariff (AED/kWh)", 0.05, 2.0, E.TARIFF_AED_PER_KWH, 0.01)
    co2f = st.number_input("Grid emission factor (kg CO₂/kWh)", 0.1, 1.0, E.CO2_KG_PER_KWH, 0.01)
    underuse = st.slider("Underutilised below (% of seats)", 10, 60, int(E.UNDERUSE_THRESHOLD * 100), 5) / 100
    st.divider()
    if st.button("🔄 Reset demo data", width="stretch"):
        data_gen.main(str(DATA))
        st.cache_data.clear()
        st.rerun()
    st.caption("Tariff and emission factor are placeholder assumptions for the demo - "
               "replace with Liwa University's actual figures.")

B = run(underuse, fb_mtime())
rooms, df, week, fc, plan, com = B["rooms"], B["df"], B["week"], B["forecast"], B["plan"], B["comfort"]
wk = df[df.week == week]
K = E.kpis(wk, tariff, co2f)
recs = E.recommendations(wk, com, plan, tariff)

st.markdown('<div class="ls-brand"><h1>⚡ LiwaSync</h1></div>'
            '<div class="ls-sub">Smart Campus Energy Management · classroom occupancy, comfort and '
            'AI-driven recommendations for facilities staff</div>', unsafe_allow_html=True)

t_live, t_an, t_ai, t_temp, t_rec, t_rep = st.tabs(
    ["🏫 Live campus", "📊 Energy analytics", "🤖 AI forecast", "🌡️ LiwaTemp",
     "✅ Recommendations", "📄 Report"])

# ================================================================ MONITOR ==
with t_live:
    now = wk[(wk.day == day) & (wk.hour == hour)].copy()

    def label(r):
        if r.status == "Empty":
            if r.precool:
                return "Pre-cooling"
            return "Empty · devices ON" if (r.lights_on or r.ac_on) else "Empty · off"
        return r.status
    now["label"] = now.apply(label, axis=1)
    waste_kw = now.waste_kwh.sum()
    c = st.columns(4)
    kpi(c[0], "Rooms in use", f"{(now.present > 0).sum()} / {len(now)}", f"{day} {hour:02d}:00")
    kpi(c[1], "Empty with AC/lights on", f"{(now.label == 'Empty · devices ON').sum()}",
        "candidates for auto-off")
    seat = now[now.booked]
    kpi(c[2], "Seat utilisation", f"{seat.present.sum() / max(seat.capacity.sum(), 1):.0%}",
        f"{int(seat.present.sum())} students in {int(seat.capacity.sum())} booked seats")
    kpi(c[3], "Power being wasted", f"{waste_kw:.1f} kW", f"≈ AED {waste_kw * tariff:.2f} this hour")

    st.markdown('<div class="legend" style="margin:14px 0 4px">' + "".join(
        f'<span><b style="background:{v}"></b>{k}</span>' for k, v in STATUS_COL.items()) + "</div>",
        unsafe_allow_html=True)
    for b, name in data_gen.BUILDINGS.items():
        col = st
        tiles = []
        for r in now[now.building == b].sort_values("room_id").itertuples():
            colr = STATUS_COL[r.label]
            pct = min(r.present / r.capacity, 1)
            tiles.append(
                f'<div class="tile" style="--c:{colr}"><div class="id">{r.room_id}</div>'
                f'<div class="st">{r.course or "&nbsp;"}</div><div class="st"><b>{r.label}</b></div>'
                f'<div class="occ">{r.present}/{r.capacity} seats</div>'
                f'<div class="bar"><i style="width:{pct * 100:.0f}%"></i></div>'
                f'<div class="dev">{"❄️ AC" if r.ac_on else "– AC"}&nbsp;&nbsp;'
                f'{"💡 Lights" if r.lights_on else "– Lights"}</div></div>')
        col.markdown(f'<div class="bldg">Building {b} · {name}</div><div class="grid">'
                     + "".join(tiles) + "</div>", unsafe_allow_html=True)

    with st.expander("Room table (this hour)"):
        st.dataframe(now[["room_id", "building_name", "capacity", "course", "present", "label",
                          "ac_on", "lights_on", "kwh", "waste_kwh"]]
                     .rename(columns={"label": "status", "kwh": "kW now", "waste_kwh": "kW wasted"}),
                     hide_index=True, width="stretch")

# ================================================================ ANALYZE ==
with t_an:
    c = st.columns(4)
    kpi(c[0], "Classroom energy this week", f"{K['total_kwh']:,.0f} kWh", "lights + AC, 24 rooms")
    kpi(c[1], "Avoidable energy", f"{K['waste_kwh']:,.0f} kWh", f"{K['waste_pct']:.0%} of classroom use")
    kpi(c[2], "Avoidable cost / semester", f"AED {K['waste_aed_semester']:,.0f}",
        f"{E.SEMESTER_WEEKS} weeks at AED {tariff:.2f}/kWh")
    kpi(c[3], "Avoidable CO₂ / semester", f"{K['co2_kg_semester'] / 1000:,.1f} t", f"at {co2f} kg/kWh")

    a, b = st.columns(2)
    wb = wk[wk.waste_type != ""].groupby(["building", "waste_type"]).waste_kwh.sum().reset_index()
    wb["building_name"] = "Building " + wb.building
    fig = px.bar(wb, x="building_name", y="waste_kwh", color="waste_type", barmode="stack",
                 color_discrete_sequence=SERIES, title="Avoidable energy by building (kWh / week)",
                 labels={"building_name": "", "waste_kwh": "kWh", "waste_type": ""})
    fig.update_traces(marker_line_color="#fcfcfb", marker_line_width=2,
                      hovertemplate="%{x}<br>%{fullData.name}: %{y:.0f} kWh<extra></extra>")
    a.plotly_chart(style_fig(fig), width="stretch")

    hm = wk.pivot_table(index="day", columns="hour", values="waste_kwh", aggfunc="sum").reindex(E.DAY_ORDER)
    fig = go.Figure(go.Heatmap(z=hm.values, x=[f"{h:02d}:00" for h in hm.columns], y=hm.index,
                               colorscale=[[0, "#f0efec"], [.25, "#9ec5f4"], [.6, "#2a78d6"], [1, "#0d366b"]],
                               xgap=2, ygap=2, zmin=0, colorbar=dict(title="kWh"),
                               hovertemplate="%{y} %{x}<br>%{z:.1f} kWh avoidable<extra></extra>"))
    fig.update_layout(title="When is energy wasted? (campus-wide, kWh)")
    b.plotly_chart(style_fig(fig), width="stretch")

    ru = wk.groupby(["room_id", "capacity"]).agg(
        booked=("booked", "mean"),
        seat=("present", "sum"), cap=("capacity", "sum"), occ_h=("present", lambda s: (s > 0).sum()),
        waste=("waste_kwh", "sum")).reset_index()
    booked_rows = wk[wk.booked].groupby("room_id").agg(p=("present", "sum"), c=("capacity", "sum"))
    ru["seat_util"] = ru.room_id.map(booked_rows.p / booked_rows.c).fillna(0)
    ru = ru.sort_values("waste", ascending=False)
    a, b = st.columns(2)
    fig = px.bar(ru, x="room_id", y="waste", title="Avoidable energy by room (kWh / week)",
                 labels={"room_id": "", "waste": "kWh"}, color_discrete_sequence=[SERIES[0]],
                 hover_data={"capacity": True, "seat_util": ":.0%", "booked": ":.0%"})
    fig.update_traces(marker_line_color="#fcfcfb", marker_line_width=1)
    fig.update_xaxes(tickangle=-90, tickfont_size=10)
    a.plotly_chart(style_fig(fig), width="stretch")
    fig = px.scatter(ru, x="capacity", y="seat_util", size="waste", hover_name="room_id",
                     title="Seats filled when booked vs room size (bubble = waste)",
                     labels={"capacity": "Room capacity (seats)", "seat_util": "Seats filled when booked"},
                     color_discrete_sequence=[SERIES[1]])
    fig.add_hline(y=underuse, line_dash="dot", line_color=MUTED,
                  annotation_text=f"underutilised < {underuse:.0%}", annotation_font_color=INK2)
    fig.update_traces(marker_line_color="#fcfcfb", marker_line_width=2, opacity=.8)
    fig.update_xaxes(tickvals=sorted(ru.capacity.unique()))
    fig.update_yaxes(tickformat=".0%")
    b.plotly_chart(style_fig(fig), width="stretch")
    st.markdown('<div class="note"><b>How waste is counted.</b> Empty room with AC/lights on = full load '
                'is avoidable (except AC in the hour before a class = pre-cooling). Underutilised class = '
                'difference between the room used and the smallest room that would fit the students '
                '(+15% margin). Room power: lighting ≈ 10 W/m², AC ≈ 45 W/m² (simulated).</div>',
                unsafe_allow_html=True)

# ===================================================================== AI ==
with t_ai:
    st.markdown("#### Predicting real attendance - so rooms are right-sized *before* class")
    c = st.columns(4)
    kpi(c[0], "Model", "Random forest", "scikit-learn · 200 trees")
    kpi(c[1], "Forecast error (MAE)", f"±{fc['mae']:.1f} students", f"tested on week {week} (unseen)")
    kpi(c[2], "Naive error (enrolment)", f"±{fc['naive_mae']:.1f} students", "planning by enrolled count")
    kpi(c[3], "Improvement", f"{1 - fc['mae'] / fc['naive_mae']:.0%}", "lower error than enrolment")

    a, b = st.columns([3, 2])
    t = fc["test"]
    fig = px.scatter(t, x="present", y="pred", hover_data=["course", "day", "hour", "room_id", "enrolled"],
                     labels={"present": "Actual attendance", "pred": "Predicted attendance"},
                     title=f"Predicted vs actual attendance · week {week}",
                     color_discrete_sequence=[SERIES[0]], opacity=.7)
    m = max(t.present.max(), t.pred.max())
    fig.add_trace(go.Scatter(x=[0, m], y=[0, m], mode="lines", line=dict(color=MUTED, dash="dot"),
                             name="perfect prediction", hoverinfo="skip", showlegend=False))
    fig.add_annotation(x=m * .92, y=m * .98, text="perfect prediction", showarrow=False,
                       font=dict(color=MUTED, size=11), xanchor="right")
    a.plotly_chart(style_fig(fig, 380), width="stretch")
    imp = fc["importance"].rename({"enrolled": "Enrolled students", "lag_mean": "Avg past attendance",
                                   "lag1": "Last week's attendance", "hour": "Time of day",
                                   "week": "Week of semester", "day_idx": "Day of week",
                                   "dept_idx": "Department"}).sort_values()
    fig = px.bar(x=imp.values, y=imp.index, orientation="h", title="What drives the prediction",
                 labels={"x": "Importance", "y": ""}, color_discrete_sequence=[SERIES[2]])
    b.plotly_chart(style_fig(fig, 380), width="stretch")

    st.markdown(f"#### Next week's right-sizing plan · {len(plan)} class slots can move to smaller free rooms")
    st.caption("Greedy best-fit optimiser: classes in the largest rooms first, only into rooms that are free in that slot, "
               "forecast + 15% safety margin.")
    if not plan.empty:
        c = st.columns(3)
        kpi(c[0], "Energy saved / week", f"{plan.kwh_saved_week.sum():,.0f} kWh")
        kpi(c[1], "Cost saved / semester", f"AED {plan.kwh_saved_week.sum() * tariff * E.SEMESTER_WEEKS:,.0f}")
        kpi(c[2], "Class sections affected", f"{plan.course.nunique()}", f"{len(plan)} weekly slots")
        st.dataframe(plan.rename(columns={"kwh_saved_week": "kWh saved"}), hide_index=True,
                     width="stretch", height=280)

# ============================================================== LIWATEMP ==
with t_temp:
    left, right = st.columns([2, 3])
    with left:
        st.markdown("#### Student view")
        st.caption("Students open this from a QR code on the classroom door: `?view=student`")
        liwatemp_form(rooms)
        st.markdown(f'<div class="note">Flag rule: at least <b>{E.COMFORT_MIN_VOTES} votes</b> and '
                    f'<b>≥{E.COMFORT_SHARE:.0%}</b> on one side → facilities review. '
                    'No names or student IDs are collected.</div>', unsafe_allow_html=True)
    with right:
        st.markdown("#### Comfort by room (this week)")
        cm = com.assign(k=com.cold_share - com.warm_share).sort_values("k", ascending=False)
        long = cm.melt(id_vars=["room_id", "votes"], value_vars=["cold", "ok", "warm"],
                       var_name="vote", value_name="n")
        long["share"] = long.n / long.votes
        long["vote"] = long.vote.map({"cold": "Too cold", "ok": "Comfortable", "warm": "Too warm"})
        fig = px.bar(long, x="room_id", y="share", color="vote", barmode="stack",
                     category_orders={"vote": ["Too cold", "Comfortable", "Too warm"]},
                     color_discrete_map={"Too cold": "#2a78d6", "Comfortable": "#c3c2b7", "Too warm": "#e34948"},
                     labels={"room_id": "", "share": "Share of votes", "vote": ""},
                     hover_data={"n": True, "votes": True, "share": ":.0%"})
        fig.add_hline(y=E.COMFORT_SHARE, line_dash="dot", line_color=INK2)
        fig.update_traces(marker_line_color="#fcfcfb", marker_line_width=2)
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(style_fig(fig, 320), width="stretch")
        fl = com[com.flag != ""].sort_values("votes", ascending=False)
        st.markdown(f"**🚩 {len(fl)} rooms flagged for AC review**")
        st.dataframe(fl.assign(cold_share=fl.cold_share.map("{:.0%}".format),
                               warm_share=fl.warm_share.map("{:.0%}".format))
                     [["room_id", "flag", "votes", "cold_share", "warm_share", "ac_setpoint_c"]]
                     .rename(columns={"room_id": "Room", "flag": "Flag", "votes": "Votes",
                                      "cold_share": "Too cold", "warm_share": "Too warm",
                                      "ac_setpoint_c": "AC setpoint °C"}),
                     hide_index=True, width="stretch")
        fbw = B["feedback"][(B["feedback"].week == week) & (B["feedback"].comment != "")]
        st.markdown("**Latest anonymous comments**")
        for r in fbw.tail(6).iloc[::-1].itertuples():
            st.markdown(f"- *{r.comment}* - {r.room_id}, {r.vote.lower()}")

# ======================================================= CONTROL/OPTIMIZE ==
with t_rec:
    st.markdown("#### Recommendations for facilities staff")
    st.caption("LiwaSync recommends; people decide. Nothing changes the AC or lights automatically - "
               "approved actions are exported to the facilities team / BMS schedule.")
    if recs.empty:
        st.info("No recommendations this week.")
    else:
        types = ["All"] + sorted(recs.type.unique())
        f = st.radio("Filter", types, horizontal=True, label_visibility="collapsed")
        view = recs if f == "All" else recs[recs.type == f]
        if "decisions" not in st.session_state:
            st.session_state.decisions = {}
        view = view.assign(decision=view.id.map(lambda i: st.session_state.decisions.get(i, "Pending")))
        edited = st.data_editor(
            view[["id", "priority", "type", "room", "action", "kwh_week", "aed_semester", "decision"]],
            column_config={
                "decision": st.column_config.SelectboxColumn("Decision", options=["Pending", "Approve", "Dismiss"]),
                "kwh_week": st.column_config.NumberColumn("kWh/week", format="%.1f"),
                "aed_semester": st.column_config.NumberColumn("AED/semester", format="%.0f"),
                "action": st.column_config.TextColumn("Recommended action", width="large"),
            },
            disabled=["id", "priority", "type", "room", "action", "kwh_week", "aed_semester"],
            hide_index=True, width="stretch", height=420, key=f"ed_{f}")
        for r in edited.itertuples():
            st.session_state.decisions[r.id] = r.decision
        dec = recs.id.map(lambda i: st.session_state.decisions.get(i, "Pending"))
        appr = recs[dec == "Approve"]
        c = st.columns(4)
        kpi(c[0], "Open recommendations", f"{(dec == 'Pending').sum()}")
        kpi(c[1], "Approved", f"{len(appr)}")
        kpi(c[2], "Approved savings / week", f"{appr.kwh_week.sum():,.0f} kWh")
        kpi(c[3], "Approved savings / semester", f"AED {appr.aed_semester.sum():,.0f}")
        if len(appr):
            st.download_button("⬇️ Export approved actions (CSV)", appr.to_csv(index=False),
                               "liwasync_approved_actions.csv", "text/csv")

# ================================================================= REPORT ==
with t_rep:
    st.markdown(f"#### Weekly energy report · week {week}")
    trend = df.groupby("week").agg(total=("kwh", "sum"), waste=("waste_kwh", "sum")).reset_index()
    trend["Useful energy"] = trend.total - trend.waste
    trend = trend.rename(columns={"waste": "Avoidable energy"})
    a, b = st.columns([1, 1])
    fig = px.bar(trend, x="week", y=["Useful energy", "Avoidable energy"],
                 color_discrete_sequence=["#c3c2b7", SERIES[1]],
                 title="Classroom energy per week (kWh)", labels={"value": "kWh", "week": "Week", "variable": ""})
    fig.update_traces(marker_line_color="#fcfcfb", marker_line_width=2)
    a.plotly_chart(style_fig(fig), width="stretch")
    by_type = recs.groupby("type").agg(n=("id", "count"), kwh=("kwh_week", "sum"),
                                       aed=("aed_semester", "sum")).sort_values("kwh", ascending=False)
    with b:
        st.markdown("**Savings potential by action type**")
        st.dataframe(by_type.rename(columns={"n": "Actions", "kwh": "kWh / week", "aed": "AED / semester"}).rename_axis("Action type")
                     .style.format({"kWh / week": "{:,.0f}", "AED / semester": "{:,.0f}"}),
                     width="stretch")
        tot = by_type.kwh.sum()
        st.markdown(f'<div class="note">If every recommendation is approved: <b>{tot:,.0f} kWh/week</b>, '
                    f'<b>AED {tot * tariff * E.SEMESTER_WEEKS:,.0f}</b> and '
                    f'<b>{tot * co2f * E.SEMESTER_WEEKS / 1000:,.1f} t CO₂</b> per semester across 24 '
                    f'simulated classrooms.</div>', unsafe_allow_html=True)
    summary = pd.DataFrame({
        "Metric": ["Classroom energy (kWh/week)", "Avoidable energy (kWh/week)", "Avoidable share",
                   "Seat utilisation when booked", "Room booking rate", "Rooms flagged by LiwaTemp",
                   "Forecast MAE (students)", "Recommendations"],
        "Value": [f"{K['total_kwh']:,.0f}", f"{K['waste_kwh']:,.0f}", f"{K['waste_pct']:.0%}",
                  f"{K['seat_util']:.0%}", f"{K['room_util']:.0%}", f"{(com.flag != '').sum()}",
                  f"{fc['mae']:.1f}", f"{len(recs)}"]})
    st.dataframe(summary, hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Download weekly report (CSV)", recs.to_csv(index=False),
                       f"liwasync_week{week}_recommendations.csv", "text/csv", width="stretch")
    c2.download_button("⬇️ Download room-hour data (CSV)",
                       wk.drop(columns=["building_name"]).to_csv(index=False),
                       f"liwasync_week{week}_room_hours.csv", "text/csv", width="stretch")
