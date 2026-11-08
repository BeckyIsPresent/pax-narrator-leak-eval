# Judge every reply listed in a results spreadsheet, using the AI judge.
# If human labels exist (labels/human_labels.csv), also report how often the judge agrees with us.
#
# Run:  python judge_results.py results/results-20261108-132129.csv

import os
import sys
import csv
import harness
import judge

import datetime

results_csv = sys.argv[1]
judge_model = judge.JUDGE_MODEL
if "--judge-model" in sys.argv:
    judge_model = sys.argv[sys.argv.index("--judge-model") + 1]
judge_effort = judge.JUDGE_EFFORT
if "--judge-effort" in sys.argv:
    judge_effort = sys.argv[sys.argv.index("--judge-effort") + 1]
judge_max_tokens = judge.JUDGE_MAX_TOKENS
if "--judge-max-tokens" in sys.argv:
    judge_max_tokens = int(sys.argv[sys.argv.index("--judge-max-tokens") + 1])
with open(results_csv, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

cases = {}  # load each case file once
import glob
for path in glob.glob("cases/*.yaml"):
    case = harness.load_case(path)
    cases[case["id"]] = case

print(f"Replies to judge: {len(rows)} (judge: {judge_model}, reasoning effort: {judge_effort}, max tokens: {judge_max_tokens})")
answer = input("Go ahead? Type y and press Enter: ")
if answer.strip().lower() != "y":
    print("Cancelled. Nothing was spent.")
    sys.exit()

client = harness.make_client()
for i, row in enumerate(rows, start=1):
    with open(row["output_file"], encoding="utf-8") as f:
        output = f.read()
    try:
        verdict = judge.judge_output(client, cases[row["case_id"]], output,
                                     model=judge_model, effort=judge_effort, max_tokens=judge_max_tokens)
    except Exception as error:
        print(f"[{i}/{len(rows)}] ERROR judging {row['output_file']}: {error}")
        verdict = {"leak": "", "leak_quotes": [], "clue_quotes": [], "interest": "", "reasoning": f"ERROR: {error}", "judge_tokens": 0, "judge_reasoning_tokens": 0, "quote_check": "", "extra_pass": None}
    row["judge_leak"] = verdict["leak"]
    row["judge_leak_quotes"] = " | ".join(verdict.get("leak_quotes", []))
    row["judge_clue_quotes"] = " | ".join(verdict.get("clue_quotes", []))
    row["judge_interest"] = verdict["interest"]
    row["judge_extra_pass"] = "" if verdict.get("extra_pass") is None else verdict.get("extra_pass")
    row["judge_reasoning"] = verdict.get("reasoning", "")
    row["judge_model"] = judge_model
    row["judge_effort"] = judge_effort
    row["judge_quote_check"] = verdict.get("quote_check", "")
    row["judge_tokens"] = verdict.get("judge_tokens", 0)
    row["judge_reasoning_tokens"] = verdict.get("judge_reasoning_tokens", 0)
    print(f"[{i}/{len(rows)}] {row['model']} | {row['version']} | run {row['run']} | leak: {verdict['leak']} | interest: {verdict['interest']} | judge tokens: {row['judge_tokens']}")
    if row["judge_quote_check"].startswith("QUOTE NOT FOUND"):
        print("    WARNING: the judge quoted text that is not in the reply")

# ---------- Save ----------
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
judged_csv = results_csv.replace(".csv", f"-judged-{stamp}.csv")  # never overwrite an earlier judging
with open(judged_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

# ---------- Summary ----------
def summarise(group):
    judged = [r for r in group if r["judge_leak"] != ""]
    leaks = sum(1 for r in judged if r["judge_leak"] is True)
    interests = [float(r["judge_interest"]) for r in judged if r["judge_interest"] != ""]
    avg = sum(interests) / len(interests) if interests else 0
    text = f"leaks {leaks}/{len(judged)} | avg interest {avg:.1f}"
    extras = [r for r in judged if r.get("judge_extra_pass") != ""]
    if extras:
        passed = sum(1 for r in extras if r["judge_extra_pass"] is True)
        text += f" | extra check passed {passed}/{len(extras)}"
    return text

print("\nJUDGE SUMMARY - per case")
for case_id, model, version in sorted({(r["case_id"], r["model"], r["version"]) for r in rows}):
    group = [r for r in rows if r["case_id"] == case_id and r["model"] == model and r["version"] == version]
    print(f"  {case_id:32} {model:36} {version:9} {summarise(group)}")

print("\nJUDGE SUMMARY - all cases together")
for model, version in sorted({(r["model"], r["version"]) for r in rows}):
    group = [r for r in rows if r["model"] == model and r["version"] == version]
    print(f"  {model:36} {version:9} {summarise(group)}")

# ---------- Calibration against our own human labels ----------
labels_path = "labels/human_labels.csv"
if os.path.exists(labels_path):
    with open(labels_path, encoding="utf-8") as f:
        labels = {r["output_name"]: r for r in csv.DictReader(f)}
    agree, compared, borderline = 0, 0, 0
    print("\nCALIBRATION (judge vs human)")
    for row in rows:
        # match on the exact file name (timestamp included), so labels only ever
        # apply to the reply that was actually read and labelled
        key = os.path.basename(row["output_file"])
        label = labels.get(key)
        if not label or row["judge_leak"] == "":
            continue
        if label["human_leak"] == "borderline":
            borderline += 1
            print(f"  borderline | judge: {row['judge_leak']} | {key}")
            continue
        human = label["human_leak"] == "yes"
        compared += 1
        if human == row["judge_leak"]:
            agree += 1
        else:
            print(f"  DISAGREE | human: {human} | judge: {row['judge_leak']} | {key}")
    if compared:
        print(f"  Agreement: {agree}/{compared} clear-cut cases ({borderline} borderline not counted)")
    else:
        print("  No labelled replies in this run (labels only match the exact files you labelled).")

total_judge = sum(int(r["judge_tokens"] or 0) for r in rows)
total_reasoning = sum(int(r["judge_reasoning_tokens"] or 0) for r in rows)
bad_quotes = sum(1 for r in rows if str(r["judge_quote_check"]).startswith("QUOTE NOT FOUND"))
errors = sum(1 for r in rows if r["judge_leak"] == "")
print(f"\nJudge tokens used: {total_judge} total, about {total_judge // max(len(rows), 1)} per verdict "
      f"({total_reasoning // max(len(rows), 1)} of them reasoning)")
print(f"Invented quotes: {bad_quotes} | Errors: {errors}")
print("Saved to:", judged_csv)
