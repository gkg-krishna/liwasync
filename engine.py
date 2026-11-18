"""
LiwaSync analytics engine.

  Monitor  -> classify every room-hour as Occupied / Underutilised / Empty / No-show
  Analyze  -> energy model, waste detection, ML attendance forecast, comfort flags
  Optimize -> ranked recommendations (auto-off schedules, room right-sizing,
              AC setpoint review) for facilities staff to approve
  Report   -> KPI summaries used by the dashboard and the CSV export
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

# ---- Assumptions (editable in the sidebar) ---------------------------------
TARIFF_AED_PER_KWH = 0.30     # assumed commercial tariff for the PoC
CO2_KG_PER_KWH = 0.40         # assumed grid emission factor for the PoC
SEMESTER_WEEKS = 15
UNDERUSE_THRESHOLD = 0.35     # < 35% of seats filled = underutilised
SETPOINT_SAVING_PER_C = 0.05  # ~5% of cooling energy per +1 C (rule of thumb)
COMFORT_MIN_VOTES = 5
COMFORT_SHARE = 0.50
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def load(data_dir="data"):
    rooms = pd.read_csv(f"{data_dir}/rooms.csv")
    sessions = pd.read_csv(f"{data_dir}/sessions.csv").fillna({"course": "", "course_name": ""})
    feedback = pd.read_csv(f"{data_dir}/feedback.csv").fillna({"comment": ""})
    return rooms, sessions, feedback


# ---------------------------------------------------------------- MONITOR ---
def classify(sessions: pd.DataFrame, rooms: pd.DataFrame,
             underuse: float = UNDERUSE_THRESHOLD) -> pd.DataFrame:
    df = sessions.merge(rooms, on="room_id", how="left")
    df["booked"] = df["course"] != ""
    df["occupancy"] = df["present"] / df["capacity"]
    df["status"] = np.select(
        [df.booked & (df.present == 0), df.present == 0, df.occupancy < underuse],
        ["No-show", "Empty", "Underutilised"], default="Occupied")
    df["kwh"] = df.lights_on * df.light_kw + df.ac_on * df.ac_kw
    return df


# ---------------------------------------------------------------- ANALYZE ---
def _right_size_kwh(present: int, rooms: pd.DataFrame) -> float:
    """kWh/hour of the smallest room that would fit `present` (+15% margin)."""
    need = math.ceil(present * 1.15)
    fit = rooms[rooms.capacity >= need]
    if fit.empty:
        return np.nan
    best = fit.sort_values("capacity").iloc[0]
    return best.light_kw + best.ac_kw


def add_waste(df: pd.DataFrame, rooms: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().sort_values(["week", "room_id", "day", "hour"]).reset_index(drop=True)
    # AC running in the hour right before a booked class is legitimate pre-cooling
    nxt_booked = df.groupby(["week", "room_id", "day"])["booked"].shift(-1, fill_value=False)
    df["precool"] = (df.status == "Empty") & nxt_booked & (df.ac_on == 1)
    waste = np.zeros(len(df))
    empty = df.status.isin(["Empty", "No-show"])
    waste[empty.values] = df.loc[empty, "kwh"].values
    pc = df.precool.values
    waste[pc] = (df.lights_on * df.light_kw).values[pc]
    under = df.status == "Underutilised"
    ideal = df.loc[under, "present"].apply(lambda p: _right_size_kwh(p, rooms))
    waste[under.values] = np.clip(df.loc[under, "kwh"].values - ideal.fillna(0).values, 0, None)
    df["waste_kwh"] = waste
    df["waste_type"] = np.where(empty, "Empty room, devices on",
                        np.where(under & (df.waste_kwh > 0), "Oversized room", ""))
    return df


def comfort(feedback: pd.DataFrame, rooms: pd.DataFrame,
            min_votes=COMFORT_MIN_VOTES, share=COMFORT_SHARE) -> pd.DataFrame:
    if feedback.empty:
        return pd.DataFrame(columns=["room_id", "votes", "cold", "ok", "warm", "flag"])
    t = feedback.pivot_table(index="room_id", columns="vote", values="day",
                             aggfunc="count", fill_value=0)
    for c in ["Too cold", "Comfortable", "Too warm"]:
        if c not in t:
            t[c] = 0
    t = t.rename(columns={"Too cold": "cold", "Comfortable": "ok", "Too warm": "warm"})
    t["votes"] = t.cold + t.ok + t.warm
    t["cold_share"] = t.cold / t.votes
    t["warm_share"] = t.warm / t.votes
    t["flag"] = np.where((t.votes >= min_votes) & (t.cold_share >= share), "Too cold",
                 np.where((t.votes >= min_votes) & (t.warm_share >= share), "Too warm", ""))
    t = t.reset_index().merge(rooms[["room_id", "ac_setpoint_c", "ac_kw"]], on="room_id")
    return t[["room_id", "votes", "cold", "ok", "warm", "cold_share", "warm_share",
              "flag", "ac_setpoint_c", "ac_kw"]]


# ---- AI: attendance forecast -------------------------------------------------
FEATURES = ["enrolled", "hour", "day_idx", "week", "lag1", "lag_mean", "dept_idx"]


def _features(booked: pd.DataFrame) -> pd.DataFrame:
    b = booked.sort_values("week").copy()
    b["day_idx"] = b.day.map({d: i for i, d in enumerate(DAYS_ORDER_FULL)})
    b["dept_idx"] = b.course.str[:2].astype("category").cat.codes
    g = b.groupby(["course", "day", "hour"])["present"]
    b["lag1"] = g.shift(1)
    b["lag_mean"] = g.transform(lambda s: s.shift(1).expanding().mean())
    return b


DAYS_ORDER_FULL = DAY_ORDER


def forecast(sessions: pd.DataFrame, current_week: int):
    """Random-forest model predicting how many students will actually attend
    each class. Trained on past weeks, validated on the current week, then
    used to forecast next week so rooms can be right-sized *before* the class."""
    booked = sessions[sessions.course != ""]
    f = _features(booked)
    train = f[(f.week < current_week) & f.lag1.notna()]
    test = f[(f.week == current_week) & f.lag1.notna()]
    model = RandomForestRegressor(n_estimators=200, max_depth=8, random_state=0)
    model.fit(train[FEATURES], train.present)
    test = test.assign(pred=model.predict(test[FEATURES]))
    mae = mean_absolute_error(test.present, test.pred)
    naive_mae = mean_absolute_error(test.present, test.enrolled)

    # forecast next week from current week as lag
    nxt = f[f.week == current_week].copy()
    hist = f[f.week <= current_week].groupby(["course", "day", "hour"])["present"].mean()
    nxt["lag1"] = nxt.present
    nxt["lag_mean"] = nxt.set_index(["course", "day", "hour"]).index.map(hist)
    nxt["week"] = current_week + 1
    nxt["pred_next"] = model.predict(nxt[FEATURES]).round().astype(int)
    imp = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
    return {"model": model, "test": test, "mae": mae, "naive_mae": naive_mae,
            "next": nxt, "importance": imp}


# --------------------------------------------------------------- OPTIMIZE ---
def right_size_plan(next_week: pd.DataFrame, rooms: pd.DataFrame,
                    timetable_slots: set, margin=1.15) -> pd.DataFrame:
    """Greedy best-fit: move forecast-small classes into the smallest free room
    that still fits, starting with classes in the largest (most power-hungry)
    rooms. Never moves a class into a room that is already booked in that slot."""
    r = rooms.set_index("room_id")
    taken = set(timetable_slots)
    cands = []
    for s in next_week.itertuples():
        need = max(1, math.ceil(s.pred_next * margin))
        cur = r.loc[s.room_id]
        if cur.capacity <= need:
            continue
        cands.append((s, need, cur.light_kw + cur.ac_kw))
    moves = []
    for s, need, cur_kwh in sorted(cands, key=lambda x: -x[2]):
        options = rooms[(rooms.capacity >= need) & (rooms.capacity < r.loc[s.room_id].capacity)]
        options = options[[(rid, s.day, s.hour) not in taken for rid in options.room_id]]
        if options.empty:
            continue
        best = options.assign(k=options.light_kw + options.ac_kw).sort_values(["k", "capacity"]).iloc[0]
        saving = cur_kwh - best.k
        if saving <= 0.3:
            continue
        taken.add((best.room_id, s.day, s.hour))
        taken.discard((s.room_id, s.day, s.hour))
        moves.append({"course": s.course, "day": s.day, "hour": s.hour,
                      "from_room": s.room_id, "from_cap": int(r.loc[s.room_id].capacity),
                      "to_room": best.room_id, "to_cap": int(best.capacity),
                      "enrolled": s.enrolled, "forecast": int(s.pred_next),
                      "kwh_saved_week": round(saving, 2)})
    return pd.DataFrame(moves)


def recommendations(df_week: pd.DataFrame, comfort_t: pd.DataFrame, plan: pd.DataFrame,
                    tariff=TARIFF_AED_PER_KWH) -> pd.DataFrame:
    recs = []
    # 1. Auto-off schedules for rooms left running while empty
    idle = df_week[(df_week.status == "Empty") & ~df_week.precool]
    idle = idle[(idle.lights_on + idle.ac_on) > 0]
    g = idle.groupby("room_id").agg(hours=("hour", "count"), kwh=("kwh", "sum"),
                                    ac_h=("ac_on", "sum"), light_h=("lights_on", "sum"))
    for room, row in g.sort_values("kwh", ascending=False).iterrows():
        if row.kwh < 5:
            continue
        recs.append({"type": "Auto-off schedule", "room": room,
                     "action": f"Switch off AC/lights in unbooked slots "
                               f"({int(row.hours)} idle hours this week: AC {int(row.ac_h)}h, lights {int(row.light_h)}h)",
                     "kwh_week": row.kwh})
    # 2. No-shows: booked but empty
    ns = df_week[df_week.status == "No-show"]
    for room, g in ns.groupby("room_id"):
        slots = ", ".join(f"{r.course} {r.day} {r.hour:02d}:00" for r in g.itertuples())
        recs.append({"type": "No-show alert", "room": room,
                     "action": f"Booked but nobody attended ({slots}) - ask departments to log "
                               f"cancellations so the room is not cooled",
                     "kwh_week": g.kwh.sum()})
    # 3. Right-size rooms using the AI forecast (one recommendation per class section)
    if not plan.empty:
        groups = list(plan.groupby(["course", "from_room"]))
        small = [g for _, g in groups if g.kwh_saved_week.sum() < 5]
        if small:
            sm = pd.concat(small)
            recs.append({"type": "Right-size room (AI forecast)", "room": "Campus",
                         "action": f"Apply {len(sm)} smaller room moves from next week's AI plan "
                                   f"across {sm.course.nunique()} class sections, each under 5 kWh/week "
                                   f"(see AI forecast tab)",
                         "kwh_week": sm.kwh_saved_week.sum()})
        for (course, frm), g in groups:
            if g.kwh_saved_week.sum() < 5:
                continue
            slots = ", ".join(f"{r.day} {r.hour:02d}:00→{r.to_room}" for r in g.itertuples())
            r0 = g.iloc[0]
            recs.append({"type": "Right-size room (AI forecast)", "room": frm,
                         "action": f"{course}: forecast {int(g.forecast.mean())} of {r0.enrolled} enrolled "
                                   f"in a {r0.from_cap}-seat room - move to smaller free rooms ({slots})",
                         "kwh_week": g.kwh_saved_week.sum()})
    # 4. Comfort / AC setpoint review from LiwaTemp
    flagged = comfort_t[comfort_t.flag != ""]
    occ_hours = df_week[df_week.present > 0].groupby("room_id").size()
    for c in flagged.itertuples():
        h = occ_hours.get(c.room_id, 0)
        if c.flag == "Too cold":
            kwh = c.ac_kw * h * SETPOINT_SAVING_PER_C
            act = (f"{c.cold}/{c.votes} students report TOO COLD at {c.ac_setpoint_c}°C - "
                   f"review setpoint, suggest {c.ac_setpoint_c + 1}°C")
        else:
            kwh = 0.0
            act = (f"{c.warm}/{c.votes} students report TOO WARM at {c.ac_setpoint_c}°C - "
                   f"check AC unit / airflow")
        recs.append({"type": "AC comfort review (LiwaTemp)", "room": c.room_id,
                     "action": act, "kwh_week": kwh})
    out = pd.DataFrame(recs)
    if out.empty:
        return out
    out["kwh_week"] = out.kwh_week.round(1)
    out["aed_week"] = (out.kwh_week * tariff).round(2)
    out["aed_semester"] = (out.aed_week * SEMESTER_WEEKS).round(0)
    out["priority"] = pd.cut(out.kwh_week, [-1, 10, 40, 1e9], labels=["Low", "Medium", "High"])
    out.loc[out.type.str.startswith("AC comfort"), "priority"] = "High"
    out = out.sort_values("kwh_week", ascending=False).reset_index(drop=True)
    out.insert(0, "id", [f"R{i + 1:03d}" for i in range(len(out))])
    return out


# ----------------------------------------------------------------- REPORT ---
def kpis(df_week: pd.DataFrame, tariff=TARIFF_AED_PER_KWH, co2=CO2_KG_PER_KWH):
    total = df_week.kwh.sum()
    waste = df_week.waste_kwh.sum()
    booked = df_week[df_week.booked]
    return {
        "total_kwh": total,
        "waste_kwh": waste,
        "waste_pct": waste / total if total else 0,
        "waste_aed_week": waste * tariff,
        "waste_aed_semester": waste * tariff * SEMESTER_WEEKS,
        "co2_kg_semester": waste * co2 * SEMESTER_WEEKS,
        "seat_util": (booked.present.sum() / booked.capacity.sum()) if len(booked) else 0,
        "room_util": df_week.booked.mean(),
    }


def build(data_dir="data", current_week=None, underuse=UNDERUSE_THRESHOLD):
    rooms, sessions, feedback = load(data_dir)
    week = current_week or int(sessions.week.max())
    df = add_waste(classify(sessions, rooms, underuse), rooms)
    fc = forecast(sessions, week)
    slots = set(zip(*[sessions[(sessions.week == week) & (sessions.course != "")][c]
                      for c in ["room_id", "day", "hour"]]))
    plan = right_size_plan(fc["next"], rooms, slots)
    com = comfort(feedback[feedback.week == week], rooms)
    return {"rooms": rooms, "sessions": sessions, "feedback": feedback, "df": df,
            "week": week, "forecast": fc, "plan": plan, "comfort": com}
