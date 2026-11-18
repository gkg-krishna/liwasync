"""
LiwaSync - simulated campus data generator.

Creates three CSV files in ./data:
  rooms.csv     - classroom inventory (building, capacity, area, AC setpoint)
  sessions.csv  - 6 weeks of hourly timetable slots with attendance and device state
  feedback.csv  - anonymous LiwaTemp votes for the current week

All numbers are SIMULATED for the proof of concept. Swap these files for real
timetable / occupancy-sensor / BMS exports to run LiwaSync on live data.
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
WEEKS = 6                      # weeks 1-5 = history, week 6 = "current week"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
HOURS = list(range(8, 18))     # 08:00 - 17:00 slot starts

BUILDINGS = {
    "A": "Engineering & Computing",
    "B": "Business",
    "C": "Media & Health Sciences",
}
CAPACITY_MIX = [20, 20, 30, 30, 40, 40, 60, 100]

COURSES = [
    ("IT101", "Intro to Programming", 38), ("IT205", "Databases", 26),
    ("IT310", "Networks", 18), ("IT330", "Machine Learning", 34),
    ("IT402", "Cybersecurity", 22), ("EE201", "Circuits", 30),
    ("BA101", "Principles of Management", 55), ("BA220", "Marketing", 28),
    ("BA305", "Corporate Finance", 16), ("AC110", "Accounting I", 44),
    ("MC120", "Media Writing", 19), ("MC250", "Digital Production", 14),
    ("HS101", "Anatomy", 85), ("HS210", "Nutrition", 24),
    ("HS330", "Public Health", 12), ("GE100", "Arabic Communication", 36),
    ("GE120", "English Composition", 27), ("GE150", "UAE Studies", 92),
    ("MA101", "Calculus I", 40), ("MA201", "Statistics", 33),
]


def make_rooms(rng):
    rows = []
    for b in BUILDINGS:
        for i, cap in enumerate(CAPACITY_MIX):
            area = round(1.6 * cap + 15, 1)                       # m2
            rows.append({
                "room_id": f"{b}{101 + i}",
                "building": b,
                "building_name": BUILDINGS[b],
                "floor": 1 + i // 4,
                "capacity": cap,
                "area_m2": area,
                "light_kw": round(area * 0.010, 2),                # ~10 W/m2 LED
                "ac_kw": round(area * 0.045, 2),                   # electrical draw of cooling
                "ac_setpoint_c": int(rng.choice([20, 21, 22, 23, 24], p=[.2, .3, .25, .15, .1])),
            })
    return pd.DataFrame(rows)


def attendance_rate(day, hour, week, rng):
    """Typical attendance pattern: early mornings, Thursday/Friday afternoons
    and late slots are weaker; attendance drifts down mid-semester."""
    r = 0.86
    if hour == 8:
        r -= 0.16
    if hour >= 16:
        r -= 0.12
    if day in ("Thu", "Fri") and hour >= 13:
        r -= 0.14
    r -= 0.02 * max(0, week - 2)
    return float(np.clip(r + rng.normal(0, 0.07), 0.08, 1.0))


def make_timetable(rooms, rng):
    """Assign each course 3 weekly slots. Placement is deliberately imperfect
    (as on real campuses): some small classes sit in large rooms."""
    tt = []
    occupied = set()
    room_list = rooms.to_dict("records")
    sections = []
    for code, name, base in COURSES:
        for s in range(int(rng.integers(8, 13))):
            enrolled = int(np.clip(round(base * rng.uniform(0.6, 1.3)), 8, 98))
            sections.append((f"{code}-{s + 1:02d}", name, enrolled))
    for code, name, enrolled in sections:
        placed = 0
        tries = 0
        own_slots = set()          # (day, hour) this section already uses: one room per hour
        while placed < 3 and tries < 500:
            tries += 1
            day = rng.choice(DAYS)
            hour = int(rng.choice(HOURS))
            fits = [r for r in room_list if r["capacity"] >= enrolled]
            # 35% of the time a course lands in an oversized room
            if rng.random() < 0.35:
                big = [r for r in fits if r["capacity"] >= 2 * enrolled]
                fits = big or fits
            else:
                fits = sorted(fits, key=lambda r: r["capacity"])[:6]
            room = fits[rng.integers(len(fits))]
            key = (room["room_id"], day, hour)
            if key in occupied or (day, hour) in own_slots:
                continue
            occupied.add(key)
            own_slots.add((day, hour))
            tt.append({"course": code, "course_name": name, "enrolled": enrolled,
                       "room_id": room["room_id"], "day": day, "hour": hour})
            placed += 1
    return pd.DataFrame(tt)


def make_sessions(rooms, timetable, rng):
    rows = []
    tt_idx = {(t.room_id, t.day, t.hour): t for t in timetable.itertuples()}
    for week in range(1, WEEKS + 1):
        for room in rooms.itertuples():
            for day in DAYS:
                for hour in HOURS:
                    t = tt_idx.get((room.room_id, day, hour))
                    if t is not None:
                        present = int(round(t.enrolled * attendance_rate(day, hour, week, rng)))
                        # occasional cancelled class: booked but nobody shows
                        if rng.random() < 0.04:
                            present = 0
                        lights_on, ac_on = 1, 1
                        course, cname, enrolled = t.course, t.course_name, t.enrolled
                    else:
                        present = 0
                        course, cname, enrolled = "", "", 0
                        # Empty rooms: AC usually left on all day, lights often left on
                        ac_on = int(rng.random() < 0.75)
                        lights_on = int(rng.random() < 0.35)
                    rows.append({
                        "week": week, "day": day, "hour": hour,
                        "room_id": room.room_id, "course": course,
                        "course_name": cname, "enrolled": enrolled,
                        "present": present, "lights_on": lights_on, "ac_on": ac_on,
                    })
    return pd.DataFrame(rows)


def make_feedback(rooms, sessions, rng):
    """LiwaTemp votes for the current week. Cold complaints are more likely in
    rooms with low setpoints, warm complaints with high setpoints."""
    cur = sessions[(sessions.week == WEEKS) & (sessions.present > 0)]
    sp = rooms.set_index("room_id")["ac_setpoint_c"]
    comments_cold = ["Need a jacket in here", "AC is blasting directly on the front rows",
                     "Too cold to focus", ""]
    comments_warm = ["Stuffy after 30 min", "Back of the room is warm", ""]
    comments_ok = ["", "", "Fine today"]
    rows = []
    for s in cur.itertuples():
        n_votes = rng.binomial(s.present, 0.07)
        setp = sp[s.room_id]
        p_cold = {20: .70, 21: .55, 22: .25, 23: .12, 24: .05}[setp]
        p_warm = {20: .03, 21: .05, 22: .12, 23: .30, 24: .55}[setp]
        for _ in range(n_votes):
            u = rng.random()
            if u < p_cold:
                v, c = "Too cold", rng.choice(comments_cold)
            elif u < p_cold + p_warm:
                v, c = "Too warm", rng.choice(comments_warm)
            else:
                v, c = "Comfortable", rng.choice(comments_ok)
            rows.append({"week": WEEKS, "day": s.day, "hour": s.hour,
                         "room_id": s.room_id, "vote": v, "comment": c})
    return pd.DataFrame(rows)


def main(out_dir="data"):
    rng = np.random.default_rng(SEED)
    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    rooms = make_rooms(rng)
    tt = make_timetable(rooms, rng)
    sessions = make_sessions(rooms, tt, rng)
    feedback = make_feedback(rooms, sessions, rng)
    rooms.to_csv(out / "rooms.csv", index=False)
    sessions.to_csv(out / "sessions.csv", index=False)
    feedback.to_csv(out / "feedback.csv", index=False)
    print(f"rooms={len(rooms)} sessions={len(sessions)} "
          f"booked={int((sessions.course != '').sum())} feedback={len(feedback)}")


if __name__ == "__main__":
    main()
