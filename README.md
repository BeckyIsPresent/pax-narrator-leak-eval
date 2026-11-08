# Does a "no omniscient narrator" rule stop Pax Historia from leaking secrets?

**Short answer: in a 7-case offline test, yes.** Adding one perspective rule to the game-master prompt cut information leaks from **39% to 3%** of turns, and the judge's interest scores stayed about the same.

## The problem
In Pax Historia, the AI narrates each turn. It often tells the player things their nation couldn't know: a secret rebellion "that no imperial spy has discovered", a rival court's private affairs, battlefield details from across the galaxy. This breaks the strategy layer. If the narrator tells you everything, spying and diplomacy stop mattering.

A community preset author (CRCL, *Clone Wars Remastered*) had already written a rule against this: describe events only from the player's perspective, limited by distance, technology, faction and time, with rumours that can be wrong. I wanted to know whether it actually works, and whether it makes the game duller.

## What I did
- Built a small offline copy of a Pax turn: the full world preset, game state, player action and time jump.
- Wrote **7 test cases**, each hiding a secret: fantasy and sci-fi, nation and single-citizen play. They include a **control case** (the action has nothing to do with the secret) and an **over-hiding check** (does the rule make the AI vague about things the player *should* know?).
- Ran **3 prompt versions × 2 models (Claude Haiku 5.5, DeepSeek V4.1 Flash) × 5 runs = 210 turns**.
- Scored every turn with a cheap LLM judge. I picked the judge by testing four candidates against my own labels, then **checked its verdicts against human review**.

## Results
| Prompt version | Leaks | Interest (1–5) | Over-hiding check |
|---|---|---|---|
| Baseline | 27 / 70 (39%) | 3.78 ± 0.13 | 10 / 10 pass |
| + Perspective rule | 2 / 70 (3%) | 3.91 ± 0.10 | 10 / 10 pass |
| + Rule + report rule | 1 / 70 (1%) | 3.79 ± 0.16 | 10 / 10 pass |

*Interest is a soft 1–5 judge score, shown with 95% intervals. The intervals overlap, so it's "no measurable drop", not "no drop".*

**Per case** (leaks out of 10: 2 models × 5 runs):

| Case | Baseline | Rule | Rule + reports |
|---|---|---|---|
| Control (unrelated action) | 6 | 1 | 0 |
| Spies sent to Avonia | 4 | 0 | 0 |
| Vassal's quiet plotting | 0 | 0 | 0 |
| Advisor on a distant court | 4 | 0 | 1 |
| Over-hiding check | 8 | 1 | 0 |
| Citizen reports the Chancellor | 0 | 0 | 0 |
| Citizen follows battle news | 5 | 0 | 0 |

- The effect holds for **both models** (Haiku 13 → 1, DeepSeek 14 → 1) and in **every case that leaked at baseline** (5 of 5 dropped to 0–1 in 10). Turns within a case aren't independent, so I count cases rather than turns: 5 of 5 improving would happen by chance about 3% of the time (sign test).
- Even the **control case** leaked 6 times out of 10 at baseline, with nobody asking about the secret.
- My extra **report rule** (for stat-screen fields like "Active Internal Rebels") **added nothing measurable**. The perspective rule already covers it.
- **The judge has a known blind spot, and it favours the rule.** Attribution ("the HoloNet reports…") fools the judge, and the rule teaches the model to attribute. So part of the drop *could* be the judge being fooled. Three checks argue against this: the keyword check, which ignores phrasing, also fell (19 → 4 → 3); a human review of all 10 Geonosis "rule" replies found 0 clear leaks; and a hand audit of 20 random baseline "leak" verdicts found **16 clear leaks, 4 borderline and 0 wrong**, so the baseline isn't inflated either. Even if every borderline were counted as safe, baseline leaks would still be around 31%. Fixing this blind spot is the first thing I'd do before using the judge in production.

Total cost: a few dollars of API credit, kept low with prompt caching (about 92% of Haiku's input tokens were cached).

---

## Method

### Test cases
Each case is a YAML file in `cases/`: the game state, the player's action, the time jump, the hidden secret, and what counts as leaking it. Each one targets a different **route** a secret can leak through:

| Case | Setting | Leak route tested |
|---|---|---|
| `fantasy-04-avonia-spies` | Fantasy empire | The player investigates directly (spies sent to the island) |
| `fantasy-05-arvilion-quiet-turn` | Fantasy empire | Narrator "world events" reveal a vassal's secret plotting |
| `fantasy-06-advisor-distant-court` | Fantasy empire | A character (the Advisor) knows far more than they should |
| `scifi-08-palpatine-report` | Sci-fi, citizen play | The model's own training knowledge (it knows the canon twist) |
| `scifi-09-geonosis-news` | Sci-fi, citizen play | Distance and time: faraway battle details arriving too fast |
| `control-fantasy-roads` | Fantasy empire | **Control:** the action has nothing to do with the secret |
| `overhiding-fantasy-inspection` | Fantasy empire | **Over-hiding check:** the player must still get concrete detail about what they witness |

A sixth route turned up during the pilot: **report templates**. Presets ask for stat screens with fields like "Active Internal Rebels", and the model fills them with hidden truth. I wrote a second rule for this (`rules/report_rule.txt`), but the perspective rule alone turned out to be enough.

### The three versions
- **baseline:** the game-master instructions and the full world preset.
- **rule:** + `rules/perspective_rule.txt` (adapted from CRCL's *Clone Wars Remastered* preset).
- **rule_reports:** + `rules/report_rule.txt`.

The preset sits *before* the rules in the system prompt, so all three versions share one prompt cache.

### What counts as a leak
**Could the player's own sources plausibly know this?** Big clues are allowed and good: odd grain shipments, a rumour that might be wrong. Public figures acting in public are not leaks. While labelling, a few finer distinctions came up:
- **Perspective break vs secret leak:** the narrator reads a king's hidden resentment (omniscient voice) but doesn't reveal the actual plot. I scored this as borderline.
- **Laundered leak:** labelled "rumour" or "gossip", but always exactly right. Real rumours get things wrong.
- **Invented source:** the model makes up a spy the game state doesn't contain, to justify what it tells you.

### Choosing the judge
I labelled 12 baseline replies myself (11 clear, 1 borderline) and tested candidate judges against them:

| Judge | Agreement | Tokens per verdict | Notes |
|---|---|---|---|
| Mistral (full reasoning) | 11 / 11 | ~7,500 | Accurate but ~1.2¢ a verdict; ignores "low effort" and returns empty answers |
| Claude Haiku 5.5 | 7 / 11 | small | Invented a quote (copied from the secret description) |
| **GPT-6.1 Terra (no reasoning)** | **11 / 11** | ~2,450 | **Chosen:** ~0.35¢ a verdict |

The judge must quote the sentences behind its verdict. `quote_check()` verifies that every quote actually appears in the reply, which catches invented evidence.

### Checking the judge
- **Pilot replies** (8 tricky cases, reviewed by me with Claude Opus pulling the relevant sentences, with no verdict shown until I'd decided): the judge agreed on **4 / 6** clear cases. It was fooled by attribution once ("the HoloNet confirms" + impossibly exact numbers) and too strict on a hedge once ("unconfirmed murmurings").
- **Spot-check of the final run:** all 10 Geonosis "rule" replies, where I suspected the judge was missing laundered leaks. The review found 0 clear leaks and 1 borderline; the judge found 0. The drop is real.
- All labels are in `labels/human_labels.csv`, marked "human + Opus review" where that applies.

I deliberately **didn't** tune the judge rubric on these labels. That would be teaching to the test. A fix needs fresh labels.

## Limitations
- **An offline copy, not the real engine.** It's a single turn with no multi-turn memory, and I don't know Pax's real system prompt.
- **7 cases from 2 presets**, mostly one fantasy world. This needs more genres (historical, modern) before generalising.
- **Labels from one person** (with model assistance), so there's no inter-rater agreement.
- **Interest scores are soft.** They depend on the judge, and different judges gave different scores in testing. They're good for "did it get worse?", not for absolute quality.
- The judge is from a different model family than both game masters, which reduces (but doesn't rule out) self-preference bias.
- 4 of 210 DeepSeek replies hit the 8,000-token output cap. They were judged as-is.

## What I'd do next
1. **A/B test in the real product:** Duplicate Game + the Prompts editor, same save, with and without the rule.
2. **Fix the judge's blind spot** (attribution ≠ plausibility) and validate it on fresh held-out labels.
3. **Multi-turn tests:** does a secret stay hidden over 10 turns, or leak slowly?
4. Measure the rule's **cost**: it adds ~220 input tokens, all cacheable.

## Data
The full judged results for all 210 turns are in `data/results-20261108-152551-judged-20261108-180251.csv`: every verdict, the quotes behind it, interest scores and token counts.

## Running it
```bash
pip install openai pyyaml
# set OPENROUTER_API_KEY_PAX_HARNESS_DEMO in your environment
python run_case.py cases/control-fantasy-roads.yaml --version rule   # one turn
python run_experiment.py --dry-run                                   # check the plan, no API calls
python run_experiment.py --repeats 5                                 # full run (~210 calls)
python judge_results.py results/results-<stamp>.csv                  # judge + calibrate
```
The full world presets are other players' work, so they're **not included**. Export them from Pax into `presets/` (see `preset_file` in each case). Without them, each case falls back to a short excerpt.
