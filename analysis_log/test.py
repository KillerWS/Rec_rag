import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask
from db import init_db, execute_query

app = Flask(__name__)
init_db(app)

def get_interaction_events_2(limit: int = 100):
    try:
        limit_value = int(limit)
    except (TypeError, ValueError):
        limit_value = 100
    if limit_value <= 0:
        limit_value = 100
    if limit_value > 10000:
        limit_value = 10000

    query = f"SELECT * FROM interaction_events_2 LIMIT {limit_value}"
    return execute_query(query)

import json
import pandas as pd
import numpy as np

# ---------- config ----------
LIKERT_MAX = 5
def rev(x):
    # reverse coding for 1..5
    return (LIKERT_MAX + 1) - x

CL_ITEMS = ["CL_L1", "CL_L2R", "CL_L3", "CL_L4"]
TRN_ITEMS = ["TRN_T1", "TRN_T2", "TRN_T3", "TRN_T4", "TRN_T5R"]
CONF_ITEMS = ["CONF_C1", "CONF_C2", "CONF_C3", "CONF_C4R", "CONF_C5"]

# ---------- helpers ----------
def safe_json_loads(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return {}
    if isinstance(x, dict):
        return x
    try:
        return json.loads(x)
    except Exception:
        return {}

def cronbach_alpha(df_items: pd.DataFrame) -> float:
    """
    Cronbach's alpha for item matrix (rows=observations, cols=items)
    Uses sample variance (ddof=1). Requires at least 2 items.
    """
    df_items = df_items.dropna(axis=0, how="any")
    k = df_items.shape[1]
    if k < 2 or df_items.shape[0] < 2:
        return float("nan")
    item_vars = df_items.var(axis=0, ddof=1)
    total_var = df_items.sum(axis=1).var(ddof=1)
    if total_var == 0 or np.isnan(total_var):
        return float("nan")
    return float((k / (k - 1)) * (1 - item_vars.sum() / total_var))

def mean_sd(series: pd.Series):
    series = series.dropna()
    if len(series) == 0:
        return (float("nan"), float("nan"))
    return (float(series.mean()), float(series.std(ddof=1)))

# ---------- main ----------
with app.app_context():
    df = get_interaction_events_2(limit=10000)  # 160 rows也可直接全取
    print("raw rows:", len(df))

# 1) parse context_json (system, task_type)
df["context_dict"] = df["context_json"].apply(safe_json_loads)
df["system"] = df["context_dict"].apply(lambda d: d.get("system"))
df["task_type"] = df["context_dict"].apply(lambda d: d.get("task_type"))

# 2) parse likert_answers to columns
df["likert_dict"] = df["likert_answers"].apply(safe_json_loads)

all_likert_keys = sorted({k for d in df["likert_dict"] for k in d.keys()})
likert_wide = pd.DataFrame([{k: d.get(k) for k in all_likert_keys} for d in df["likert_dict"]])

# make numeric
for c in likert_wide.columns:
    likert_wide[c] = pd.to_numeric(likert_wide[c], errors="coerce")

df2 = pd.concat([df.reset_index(drop=True), likert_wide.reset_index(drop=True)], axis=1)

# 3) reverse-code to match "higher=better" for TRN/CONF
# TRN: only TRN_T5R is reverse
df2["TRN_T5"] = rev(df2["TRN_T5R"])
df2["TRN_T1c"] = df2["TRN_T1"]
df2["TRN_T2c"] = df2["TRN_T2"]
df2["TRN_T3c"] = df2["TRN_T3"]
df2["TRN_T4c"] = df2["TRN_T4"]

# CONF: only CONF_C4R is reverse
df2["CONF_C4"] = rev(df2["CONF_C4R"])
df2["CONF_C1c"] = df2["CONF_C1"]
df2["CONF_C2c"] = df2["CONF_C2"]
df2["CONF_C3c"] = df2["CONF_C3"]
df2["CONF_C5c"] = df2["CONF_C5"]

# 4) Cognitive Load: enforce "higher = higher load"
# L2 (mentally demanding) should be in high-load direction -> DO NOT reverse
# L1/L3/L4 are low-load phrased -> reverse them
df2["CL_L1c"] = rev(df2["CL_L1"])
df2["CL_L2c"] = df2["CL_L2R"]   # treat as NOT reversed for high-load scoring
df2["CL_L3c"] = rev(df2["CL_L3"])
df2["CL_L4c"] = rev(df2["CL_L4"])

# 5) scale scores (mean of corrected items)
df2["Transparency"] = df2[["TRN_T1c","TRN_T2c","TRN_T3c","TRN_T4c","TRN_T5"]].mean(axis=1)
df2["DecisionConfidence"] = df2[["CONF_C1c","CONF_C2c","CONF_C3c","CONF_C4","CONF_C5c"]].mean(axis=1)
df2["CognitiveLoad"] = df2[["CL_L1c","CL_L2c","CL_L3c","CL_L4c"]].mean(axis=1)

# 6) Cronbach alpha (overall across all 160 task-level rows)
alpha_trn = cronbach_alpha(df2[["TRN_T1c","TRN_T2c","TRN_T3c","TRN_T4c","TRN_T5"]])
alpha_conf = cronbach_alpha(df2[["CONF_C1c","CONF_C2c","CONF_C3c","CONF_C4","CONF_C5c"]])
alpha_cl = cronbach_alpha(df2[["CL_L1c","CL_L2c","CL_L3c","CL_L4c"]])

print("Cronbach alpha:")
print("  Transparency:", round(alpha_trn, 3))
print("  DecisionConfidence:", round(alpha_conf, 3))
print("  CognitiveLoad:", round(alpha_cl, 3))

# 7) Table 4.2 summary: Mean [SD] per System × Task
# Expect system in {"script","agent"} and task_type in {"simple","exploratory"}
summary = []
for scale in ["Transparency","DecisionConfidence","CognitiveLoad"]:
    for system in ["script","agent"]:
        row = {"Scale": scale, "System": system}
        for task in ["simple","exploratory"]:
            m, s = mean_sd(df2.loc[(df2["system"]==system) & (df2["task_type"]==task), scale])
            row[task] = f"{m:.2f} [{s:.2f}]"
        summary.append(row)

summary_df = pd.DataFrame(summary)
print("\nDescriptives (Mean [SD]) by System × Task:")
print(summary_df)

# 8) optional: generate LaTeX table body (matching your format)
def latex_scale_name(scale, alpha):
    label = {
        "Transparency": "Transparency",
        "DecisionConfidence": "Decision Confidence",
        "CognitiveLoad": "Cognitive Load",
    }[scale]
    return f"{label} ($\\alpha={alpha:.2f}$)"

latex_lines = []
for scale, alpha in [("Transparency", alpha_trn), ("DecisionConfidence", alpha_conf), ("CognitiveLoad", alpha_cl)]:
    sc_name = latex_scale_name(scale, alpha)
    script_simple = summary_df[(summary_df.Scale==scale)&(summary_df.System=="script")]["simple"].iloc[0]
    script_expl = summary_df[(summary_df.Scale==scale)&(summary_df.System=="script")]["exploratory"].iloc[0]
    agent_simple = summary_df[(summary_df.Scale==scale)&(summary_df.System=="agent")]["simple"].iloc[0]
    agent_expl = summary_df[(summary_df.Scale==scale)&(summary_df.System=="agent")]["exploratory"].iloc[0]

    latex_lines.append(rf"\multirow{{2}}{{*}}{{{sc_name}}} & Script & {script_simple} & {script_expl} \\")
    latex_lines.append(rf"& Agent  & {agent_simple} & {agent_expl} \\")
    latex_lines.append(r"\addlinespace")

print("\n--- LaTeX rows (paste into tabular) ---")
print("\n".join(latex_lines))
