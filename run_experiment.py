# Run EVERY case, EVERY harness version (baseline, rule, rule_reports), on every model, several times.
# Results go into one spreadsheet (results/results-<time>.csv) plus a summary table.
#
# Run:  python run_experiment.py                 (asks before spending anything)
#       python run_experiment.py --repeats 5
#       python run_experiment.py --dry-run       (fake replies, costs nothing - for testing)

import os
import sys
import csv
import glob
import datetime
import json
import harness
import judge

# ---------- Settings ----------
MODELS = [
    "anthropic/claude-haiku-5.5",
    "deepseek/deepseek-v4.1-flash-1017",
]
VERSIONS = list(harness.VERSIONS)  # baseline, rule, rule_reports
DEFAULT_REPEATS = 3

# ---------- Read the command line ----------
dry_run = "--dry-run" in sys.argv
repeats = DEFAULT_REPEATS
if "--repeats" in sys.argv:
    repeats = int(sys.argv[sys.argv.index("--repeats") + 1])

# ---------- Load all cases ----------
cases = [harness.load_case(path) for path in sorted(glob.glob("cases/*.yaml"))]

# ---------- Safety check before spending money ----------
total_calls = len(cases) * len(VERSIONS) * len(MODELS) * repeats
print(f"Cases: {len(cases)} | Versions: {len(VERSIONS)} | Models: {len(MODELS)} | Repeats: {repeats}")
for case in cases:
    print(f"  {case['id']}: world rules = {harness.load_preset_text(case)[1]}")
print(f"Total API calls: {total_calls}" + ("  (DRY RUN - free)" if dry_run else ""))

client = None
if not dry_run:
    answer = input("Go ahead? Type y and press Enter: ")
    if answer.strip().lower() != "y":
        print("Cancelled. Nothing was spent.")
        sys.exit()
    client = harness.make_client()

# ---------- Record the setup, so the run can be reproduced ----------
os.makedirs("results/outputs", exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
csv_path = f"results/results-{stamp}.csv"
run_info = {
    "started": stamp,
    "models": MODELS,
    "versions": {v: harness.VERSIONS[v] for v in VERSIONS},
    "rule_texts": {v: harness.load_rules(v) for v in VERSIONS},
    "repeats": repeats,
    "cases": [c["id"] for c in cases],
    "max_output_tokens": harness.MAX_OUTPUT_TOKENS,
    "base_instructions": harness.BASE_INSTRUCTIONS,
    "judge": {"model": judge.JUDGE_MODEL, "effort": judge.JUDGE_EFFORT, "max_tokens": judge.JUDGE_MAX_TOKENS},
    "dry_run": dry_run,
}
with open(f"results/run_info-{stamp}.json", "w", encoding="utf-8") as f:
    json.dump(run_info, f, indent=2)

# ---------- The main loop (each row is saved immediately, so a crash loses nothing) ----------
FIELDS = ["case_id", "genre", "model", "version", "run", "leaked", "leaked_keywords",
          "input_tokens", "cached_input_tokens", "output_tokens", "finish_reason", "output_file"]
csv_file = open(csv_path, "w", newline="", encoding="utf-8")
writer = csv.DictWriter(csv_file, fieldnames=FIELDS)
writer.writeheader()
rows = []
call_number = 0

for case in cases:
    for model in MODELS:
        for version in VERSIONS:
            for run in range(1, repeats + 1):
                call_number += 1
                system_shared, system_extra, user_prompt = harness.build_prompts(case, version)

                if dry_run:
                    output, tokens_in, tokens_out, cached, finish = "(dry run - no API call made)", 0, 0, 0, "dry"
                else:
                    try:
                        output, tokens_in, tokens_out, cached, finish = harness.ask_model(
                            client, model, system_shared, system_extra, user_prompt)
                    except Exception as error:
                        # One failed call (e.g. a wrong model ID) shouldn't kill the whole experiment.
                        print(f"[{call_number}/{total_calls}] ERROR for {model}: {error}")
                        continue

                leaked = harness.find_leaks(case, output)

                safe_model = model.replace("/", "_")
                out_file = f"results/outputs/{stamp}__{case['id']}__{safe_model}__{version}__run{run}.txt"
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(output)

                row = {
                    "case_id": case["id"],
                    "genre": case["genre"],
                    "model": model,
                    "version": version,
                    "run": run,
                    "leaked": bool(leaked),
                    "leaked_keywords": "; ".join(leaked),
                    "input_tokens": tokens_in,
                    "cached_input_tokens": cached,
                    "output_tokens": tokens_out,
                    "finish_reason": finish,
                    "output_file": out_file,
                }
                rows.append(row)
                writer.writerow(row)
                csv_file.flush()  # make sure it's on disk right now
                print(f"[{call_number}/{total_calls}] {case['id']} | {model} | {version} | run {run} | "
                      f"keyword leak: {bool(leaked)}" + (f" | CUT OFF ({finish})" if finish == "length" else ""))

if not rows:
    print("No successful calls.")
    sys.exit()

csv_file.close()

# ---------- Summary: leak rate per model and version ----------
print("\nLEAK RATE (keyword check - crude; use judge_results.py for real verdicts)")
for model in MODELS:
    for version in VERSIONS:
        group = [r for r in rows if r["model"] == model and r["version"] == version]
        if group:
            leaks = sum(r["leaked"] for r in group)
            print(f"  {model:40} {version:9} {leaks}/{len(group)} leaked")

total_in = sum(r["input_tokens"] for r in rows)
total_out = sum(r["output_tokens"] for r in rows)
total_cached = sum(r["cached_input_tokens"] for r in rows)
print(f"\nTokens: {total_in} in ({total_cached} read from cache), {total_out} out")
print("Spreadsheet saved to:", csv_path)
print("Next: python judge_results.py", csv_path)
