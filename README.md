# LiwaSync – Smart Campus Energy Management (Proof of Concept)

Liwa University Hackathon · AI Solutions for Energy Optimization Towards Smart Campuses

LiwaSync monitors classroom occupancy, detects wasted lighting/AC energy, predicts real
attendance with a machine-learning model, collects anonymous temperature feedback
(LiwaTemp) and turns it all into ranked recommendations for facilities staff.

## Run it

Needs **Python 3.12 or newer** (check with `python3 --version`). From inside the project folder:

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

**Windows (PowerShell)**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The install downloads over 100 MB and only needs doing once. Next time, just activate the
environment and run `streamlit run app.py`. Stop the app with `Ctrl+C`.

Open http://localhost:8501. The student poll on its own (for a QR code on the classroom door) is at
http://localhost:8501/?view=student. On the demo day, run the app on a laptop on the same Wi-Fi
and point the QR code at `http://<laptop-ip>:8501/?view=student`, or deploy free on Streamlit Community Cloud.

## Test it

Each step lists what you should see with the included data and default sidebar settings.

1. **🏫 Live campus** opens at Tuesday 10:00: **16 / 24** rooms in use, **4** empty rooms with AC/lights on,
   **22.9 kW** being wasted. Move the *Day* and *Hour* sliders in the sidebar and the room tiles change colour.
2. **📊 Energy analytics:** **4,743 kWh** this week, **1,812 kWh** avoidable (**38%**), **AED 8,156** and
   **10.9 t CO₂** per semester.
3. **🤖 AI forecast:** forecast error **±3.2** students vs **±10.2** when planning by enrolment (**69%** lower);
   **292** class slots can move to smaller free rooms, saving **916 kWh** a week.
4. **🌡️ LiwaTemp:** **11 rooms flagged**. Submit a vote here, or open http://localhost:8501/?view=student
   (the phone page). Refresh the dashboard and the vote is counted in the comfort chart.
5. **✅ Recommendations:** **134** recommendations. Set *Decision* to *Approve* on a few rows: the approved-savings
   tiles update and an *Export approved actions (CSV)* button appears.
6. **📄 Report:** weekly energy chart, savings by action type (Auto-off 968, Right-size 916, No-show 143,
   AC comfort 40 kWh/week) and two CSV downloads.
7. **Sidebar assumptions:** change the electricity tariff and every AED figure updates; move the
   *Underutilised below* slider and room statuses change.
8. **Phone test (optional):** with the phone on the same Wi-Fi, open the *Network URL* that Streamlit prints
   in the terminal, followed by `/?view=student`.

Votes are saved to `data/feedback.csv`, so test votes change the comfort numbers. Click **🔄 Reset demo data**
in the sidebar to go back to the original data and the numbers above.

**If something goes wrong**
- `streamlit: command not found`: the environment isn't active; run the `activate` line again.
- Windows says running scripts is disabled: run `Set-ExecutionPolicy -Scope Process Bypass`, then activate again.
- Port 8501 already in use: `streamlit run app.py --server.port 8502`.
- `pip` can't find a version: your Python is older than 3.12.

## What's inside

| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard (6 tabs) + student-only poll view |
| `engine.py` | Analytics: status classification, energy/waste model, random-forest forecast, right-sizing optimiser, comfort flags, recommendations, KPIs |
| `data_gen.py` | Simulated campus: 24 rooms in 3 buildings, ~200 class sections, 6 weeks of hourly data, LiwaTemp votes |
| `data/*.csv` | Generated data (regenerate with `python data_gen.py` or the sidebar button) |

## How it maps to the challenge (Monitor → Analyze → Control & Optimize → Report)

- **Monitor** – *Live campus* tab: every room's status (Occupied / Underutilised / Empty with devices on / No-show / Pre-cooling), seats filled, AC and lights state at any simulated day and hour.
- **Analyze** – *Energy analytics* tab: avoidable kWh, AED and CO₂; waste by building, room and hour-of-week. *AI forecast* tab: random-forest model predicts actual attendance (MAE ≈ 3 students vs ≈ 10 when planning by enrolment).
- **Control & Optimize** – *Recommendations* tab: auto-off schedules, no-show alerts, AI right-sizing (greedy best-fit into free smaller rooms) and AC setpoint reviews from LiwaTemp. Staff approve or dismiss; nothing is switched automatically.
- **Report** – *Report* tab: weekly trend, savings by action type, CSV exports.

## Assumptions (all editable / replaceable)

- All data is simulated. Swap `data/*.csv` for timetable, occupancy-sensor/Wi-Fi counts and BMS exports to go live.
- Room power: lighting ≈ 10 W/m², AC ≈ 45 W/m²; room area = 1.6 m²/seat + 15 m².
- Tariff AED 0.30/kWh and 0.40 kg CO₂/kWh are placeholders (set in the sidebar).
- AC running in the hour before a class counts as pre-cooling, not waste.
- Raising a setpoint by 1 °C is assumed to save ~5% of cooling energy.
- LiwaTemp flag: ≥5 votes and ≥50% on one side.
