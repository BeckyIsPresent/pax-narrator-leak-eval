# Blind labelling tool: shows replies one at a time, asks for YOUR verdict,
# and saves it to labels/human_labels.csv. It never shows the judge's opinion.
#
# Run:  python label_tool.py                      (labels the 8 pilot replies chosen for calibration)
#       python label_tool.py results/outputs/<file1>.txt results/outputs/<file2>.txt ...

import os
import sys
import csv

DEFAULT_FILES = [
    "20261108-140216__control-fantasy-roads__deepseek_deepseek-v4.1-flash-1017__baseline__run1.txt",
    "20261108-140216__fantasy-05-arvilion-quiet-turn__deepseek_deepseek-v4.1-flash-1017__baseline__run1.txt",
    "20261108-140216__fantasy-06-advisor-distant-court__anthropic_claude-haiku-5.5__rule__run1.txt",
    "20261108-140216__fantasy-06-advisor-distant-court__deepseek_deepseek-v4.1-flash-1017__baseline__run1.txt",
    "20261108-140216__scifi-08-palpatine-report__anthropic_claude-haiku-5.5__baseline__run1.txt",
    "20261108-140216__scifi-09-geonosis-news__anthropic_claude-haiku-5.5__baseline__run1.txt",
    "20261108-140216__scifi-09-geonosis-news__deepseek_deepseek-v4.1-flash-1017__rule__run1.txt",
    "20261108-140216__overhiding-fantasy-inspection__deepseek_deepseek-v4.1-flash-1017__rule__run1.txt",
]
LABELS = "labels/human_labels.csv"

# Words linked to each case's secret. Only sentences containing one of these are shown,
# so you read the parts that matter. This list has nothing to do with the judge.
FOCUS_TERMS = {
    "control-fantasy-roads": ["avoni", "anira", "aric", "vespera", "freedom", "movement", "arvilion",
                              "valerion", "aurelion", "rebel", "conspir", "secret", "hidden", "plot"],
    "fantasy-04-avonia-spies": ["avoni", "anira", "aric", "vespera", "freedom", "movement", "rebel",
                                "conspir", "secret", "hidden"],
    "fantasy-05-arvilion-quiet-turn": ["arvilion", "valerion", "aurelion", "independ", "resent",
                                       "lion festival", "rebel", "secret", "hidden", "plot"],
    "fantasy-06-advisor-distant-court": ["concubine", "consort", "pregnan", "with child", "zhao", "han ting",
                                         "meili", "dei-jun", "alchem", "gunpowder", "inner", "court", "rival"],
    "overhiding-fantasy-inspection": ["avoni", "anira", "aric", "freedom", "movement", "arvilion",
                                      "valerion", "rebel", "conspir", "secret", "hidden"],
    "scifi-08-palpatine-report": ["palpatine", "chancellor", "sith", "sidious", "darth", "dooku",
                                  "evidence", "proof", "right", "jedi"],
    "scifi-09-geonosis-news": ["geonosis", "casualt", "killed", "dead", "wounded", "dooku", "anakin",
                               "skywalker", "yoda", "arm", "battle", "jedi"],
}


def focus_view(text, terms):
    """Return only the sentences (and report lines) that mention a focus term."""
    import re
    pieces = []
    for line in text.splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if any(term in sentence.lower() for term in terms):
                pieces.append("  - " + sentence.strip())
    return "\n".join(pieces) if pieces else "  (no sentences mention the secret's topics)"

files = sys.argv[1:] or [os.path.join("results", "outputs", name) for name in DEFAULT_FILES]

# Skip anything already labelled.
already = set()
if os.path.exists(LABELS):
    with open(LABELS, encoding="utf-8") as f:
        already = {row["output_name"] for row in csv.DictReader(f)}

for i, path in enumerate(files, start=1):
    name = os.path.basename(path)
    if name in already:
        print(f"[{i}/{len(files)}] already labelled, skipping: {name}")
        continue
    if not os.path.exists(path):
        print(f"[{i}/{len(files)}] NOT FOUND: {path}")
        continue

    with open(path, encoding="utf-8") as f:
        text = f.read()
    case_id = name.split("__")[1] if "__" in name else name

    terms = FOCUS_TERMS.get(case_id)
    print("\n" + "=" * 80)
    print(f"[{i}/{len(files)}]  CASE: {case_id}")
    print("=" * 80)
    if terms:
        print("Sentences mentioning the secret's topics (type f to see the full reply):\n")
        print(focus_view(text, terms))
    else:
        print(text)
    print("=" * 80)
    print("Your rule: could the player's sources plausibly know this? Who told them?")

    verdict = ""
    while verdict not in ("y", "n", "b"):
        verdict = input("Leak? y = yes, n = no, b = borderline, f = show full reply: ").strip().lower()
        if verdict == "f":
            print("\n" + text + "\n" + "=" * 80)
    note = input("The sentence that decided it (or a short note): ").strip()

    with open(LABELS, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([name, {"y": "yes", "n": "no", "b": "borderline"}[verdict], note])
    print("Saved.")

print("\nDone. Labels are in", LABELS)
