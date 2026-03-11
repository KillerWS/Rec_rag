import os
import sys
import json
import numpy as np
import pandas as pd

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask
from db import init_db, execute_query

app = Flask(__name__)
init_db(app)

def get_interaction_events_2(limit: int = 10000):
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        limit_value = 10000
    if limit_value <= 0:
        limit_value = 10000
    if limit_value > 10000:
        limit_value = 10000

    query = f"SELECT * FROM interaction_events_2 LIMIT {limit_value}"
    return execute_query(query)

# ---------------- helpers ----------------
def safe_json_loads(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return {}
    if isinstance(x, dict):
        return x
    try:
        return json.loads(x)
    except Exception:
        return {}

def mean_sd(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return (float("nan"), float("nan"))
    return (float(s.mean()), float(s.std(ddof=1)))

def fmt(m, s, digits=1):
    if np.isnan(m) or np.isnan(s):
        return "NA"
    return f"{m:.{digits}f} ({s:.{digits}f})"

def fmt_int(m, s):
    # for seconds -> integer formatting
    if np.isnan(m) or np.isnan(s):
        return "NA"
    return f"{int(round(m))} ({int(round(s))})"

# ---------------- analysis ----------------
with app.app_context():
    df = get_interaction_events_2(limit=10000)

print("raw rows:", len(df))

# Parse context_json for grouping keys
df["context_dict"] = df["context_json"].apply(safe_json_loads)
df["system"] = df["context_dict"].apply(lambda d: d.get("system"))
df["task_type"] = df["context_dict"].apply(lambda d: d.get("task_type"))

# Keep only fields we need
cols = [
    "session_id",
    "system",
    "task_type",
    "task_completion_time",
    "preference_adjust_count",
    "visualization_trigger_count",
    "rag_query_local_count",
]
df2 = df[cols].copy()

# Quick sanity prints (optional)
print("cells (rows):")
print(df2.groupby(["system", "task_type"]).size())

print("sessions per cell:")
print(df2.groupby(["system", "task_type"])["session_id"].nunique())

# --- 1) Compute cell stats (mean, SD) ---
# We will compute for each system × task: TCT, PA, VIZ
cell_stats = {}
for system in ["script", "agent"]:
    for task in ["simple", "exploratory"]:
        sub = df2[(df2["system"] == system) & (df2["task_type"] == task)]

        tct_m, tct_s = mean_sd(sub["task_completion_time"])
        pa_m, pa_s = mean_sd(sub["preference_adjust_count"])
        viz_m, viz_s = mean_sd(sub["visualization_trigger_count"])

        cell_stats[(system, task)] = {
            "tct": (tct_m, tct_s),
            "pa": (pa_m, pa_s),
            "viz": (viz_m, viz_s),
        }

# --- 2) RAG-L total per system × task (sum within each task for each session) ---
rag_total_stats = {}
for system in ["script", "agent"]:
    for task in ["simple", "exploratory"]:
        sub = df2[(df2["system"] == system) & (df2["task_type"] == task)].copy()
        # per session sum within this task
        per_session_total = sub.groupby("session_id")["rag_query_local_count"].sum()
        m, s = mean_sd(per_session_total)
        rag_total_stats[(system, task)] = (m, s)

# --- 3) Print a compact table to console ---
def show(system_label, system_key):
    tct_simple = fmt_int(*cell_stats[(system_key, "simple")]["tct"])
    tct_expl   = fmt_int(*cell_stats[(system_key, "exploratory")]["tct"])

    pa_simple  = fmt(*cell_stats[(system_key, "simple")]["pa"], digits=1)
    pa_expl    = fmt(*cell_stats[(system_key, "exploratory")]["pa"], digits=1)

    viz_simple = fmt(*cell_stats[(system_key, "simple")]["viz"], digits=1)
    viz_expl   = fmt(*cell_stats[(system_key, "exploratory")]["viz"], digits=1)

    rag_simple = fmt(*rag_total_stats[(system_key, "simple")], digits=1)
    rag_expl   = fmt(*rag_total_stats[(system_key, "exploratory")], digits=1)

    print(f"\n{system_label}")
    print("  TCT:", tct_simple, "|", tct_expl)
    print("  PA :", pa_simple,  "|", pa_expl)
    print("  VIZ:", viz_simple, "|", viz_expl)
    print("  RAG-L total:", rag_simple, "|", rag_expl)

show("Script-driven", "script")
show("Agent-driven", "agent")

# --- 4) Emit LaTeX rows for your table ---
latex_rows = []

for system_key in ["script", "agent"]:
    system_label = "Script-driven" if system_key == "script" else "Agent-driven"

    tct_simple = fmt_int(*cell_stats[(system_key, "simple")]["tct"])
    tct_expl   = fmt_int(*cell_stats[(system_key, "exploratory")]["tct"])

    pa_simple  = fmt(*cell_stats[(system_key, "simple")]["pa"], digits=1)
    pa_expl    = fmt(*cell_stats[(system_key, "exploratory")]["pa"], digits=1)

    viz_simple = fmt(*cell_stats[(system_key, "simple")]["viz"], digits=1)
    viz_expl   = fmt(*cell_stats[(system_key, "exploratory")]["viz"], digits=1)

    rag_simple = fmt(*rag_total_stats[(system_key, "simple")], digits=1)
    rag_expl   = fmt(*rag_total_stats[(system_key, "exploratory")], digits=1)

    latex_rows.append(
        f"{system_label} & {tct_simple} & {tct_expl} & {pa_simple} & {pa_expl} & {viz_simple} & {viz_expl} & {rag_simple} & {rag_expl} \\\\"
    )

print("\n--- LaTeX table rows (paste under \\midrule) ---")
print("\n".join(latex_rows))


s = df2[(df2.system=="script") & (df2.task_type=="simple")].sort_values("session_id")["task_completion_time"].to_numpy()
a = df2[(df2.system=="agent") & (df2.task_type=="simple")].sort_values("session_id")["task_completion_time"].to_numpy()

print("len s/a:", len(s), len(a))
print("all equal elementwise?:", np.array_equal(s, a))
print("max abs diff:", np.max(np.abs(s - a)))
print("mean diff:", np.mean(s - a))
