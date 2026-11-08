# Run ONE test case once, with or without the perspective rule. Handy for quick checks.
# Run:  python run_case.py cases/fantasy-04-avonia-spies.yaml
#       python run_case.py cases/fantasy-04-avonia-spies.yaml --version rule
#       python run_case.py cases/fantasy-04-avonia-spies.yaml --version rule_reports
#       python run_case.py cases/fantasy-04-avonia-spies.yaml --model deepseek/deepseek-v4.1-flash-1017

import os
import sys
import datetime
import harness

model = "anthropic/claude-haiku-5.5"
if "--model" in sys.argv:
    model = sys.argv[sys.argv.index("--model") + 1]

case = harness.load_case(sys.argv[1])
version = "baseline"
if "--version" in sys.argv:
    version = sys.argv[sys.argv.index("--version") + 1]

system_shared, system_extra, user_prompt = harness.build_prompts(case, version)
client = harness.make_client()
output, tokens_in, tokens_out, cached, finish = harness.ask_model(client, model, system_shared, system_extra, user_prompt)
leaked = harness.find_leaks(case, output)

os.makedirs("results", exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
out_path = f"results/{case['id']}__{version}__{stamp}.txt"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(output)

print(output)
print("\n---")
print("Model:", model, "| Version:", version, "| World rules:", harness.load_preset_text(case)[1])
print("Leaked keywords:", leaked if leaked else "none")
print(f"Tokens: {tokens_in} in ({cached} from cache), {tokens_out} out")
print("Saved to:", out_path)
