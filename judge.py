# The AI judge: a DIFFERENT model reads one game-master reply and decides
# whether it leaked the secret, which sentences are clues, and how interesting it was.
# It only reads the reply + a short description of the secret (not the whole preset),
# so judging is cheap.

import json

JUDGE_MODEL = "openai/gpt-6.1-terra"

# Judge selection, calibrated on 12 hand-labelled replies (labels/human_labels.csv):
#   Mistral Large 4, full reasoning : 11/11 agreement, ~7,500 tokens/verdict (~1.2c)
#   Mistral Large 4, effort low/none: ignored the setting, ran out of room -> empty answers
#   Claude Haiku 5.5, no reasoning  :  7/11 agreement, false alarms on clues, 1 invented quote
#   GPT-6.1 Terra, no reasoning     : 11/11 agreement, ~2,450 tokens/verdict (~0.35c), 0 invented quotes
JUDGE_EFFORT = "none"       # none / minimal / low / medium / high, or "default" to not send it
JUDGE_MAX_TOKENS = 1000     # a verdict is ~200 tokens of JSON

RUBRIC = """You are judging the output of an AI game master in a grand strategy game.

The player controls: {player_nation}
The player's action this turn: {player_action}
Time that passed: {time_jump}

THE SECRET (known to the game master, but NOT to the player or their agents at the start):
{secret_description}

DEFINITIONS
- LEAK: the text gives the player information that none of the player's sources could
  plausibly have. This includes: confirming that the secret exists, naming who is behind it,
  or showing the conspirators' private actions, orders or thoughts from an all-knowing
  narrator's point of view. A leak is a logic failure by the game master.
- CLUE (allowed, even if it is a big clue): anything the player's spies, informants,
  officials or the public could plausibly observe or be told within the time that passed,
  such as purchases, gatherings, rumours, songs, missing agents, or suspicious behaviour.
  Mentioning a public figure behaving publicly is NOT a leak.

INTEREST (1-5): how surprising, interesting and satisfying the turn is for the player.
5 = gripping, the player's action clearly mattered and invites them to think;
3 = fine but flat; 1 = dull, confusing or nonsensical.

{extra_section}

THE GAME MASTER'S OUTPUT:
<<<
{output}
>>>

Reply with ONLY a JSON object, no other text:
{{"leak": true or false,
  "leak_quotes": ["exact sentences that leak, empty if none"],
  "clue_quotes": ["up to 3 exact sentences that are the strongest clues"],
  "interest": 1-5,
  "extra_pass": true, false or null,
  "reasoning": "one or two sentences explaining the leak verdict"}}"""


def parse_json(text):
    """Models sometimes wrap JSON in ```json fences. Strip them, then parse."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def call_judge(client, prompt, model, effort, max_tokens):
    """One judge call. If the model rejects the reasoning setting, retry without it."""
    settings = dict(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,          # as consistent as possible
        max_tokens=max_tokens,
    )
    if effort == "default":
        return client.chat.completions.create(**settings)
    try:
        return client.chat.completions.create(**settings, extra_body={"reasoning": {"effort": effort}})
    except Exception:
        return client.chat.completions.create(**settings)


def quote_check(quotes, output):
    """Safety check: every quoted 'leak' sentence must really appear in the reply.
    Compares the first 40 characters, ignoring case, spacing and quote styles."""
    def norm(text):
        for a, b in (("\u201c", '"'), ("\u201d", '"'), ("\u2019", "'"), ("\u2018", "'")):
            text = text.replace(a, b)
        return " ".join(text.lower().split())
    out = norm(output)
    missing = [q for q in quotes if q.strip() and norm(q)[:40] not in out]
    return "ok" if not missing else "QUOTE NOT FOUND: " + " | ".join(missing)


def judge_output(client, case, output, model=None, effort=None, max_tokens=None):
    """Ask the judge model for a verdict. Returns a dict, or raises an error."""
    extra = case.get("judge_extra")
    if extra:
        extra_section = f"EXTRA CHECK: {extra.strip()}\nAnswer it in the field extra_pass (true or false)."
    else:
        extra_section = "EXTRA CHECK: none. Set extra_pass to null."
    prompt = RUBRIC.format(
        extra_section=extra_section,
        player_nation=case["player_nation"],
        player_action=case["player_action"],
        time_jump=case["time_jump"],
        secret_description=case["secret"]["description"],
        output=output,
    )
    last_error = None
    for attempt in range(2):  # one retry if the JSON comes back broken
        response = call_judge(client, prompt, model or JUDGE_MODEL,
                              effort or JUDGE_EFFORT, max_tokens or JUDGE_MAX_TOKENS)
        content = response.choices[0].message.content
        if not content:
            # Typical cause: a reasoning model spent the whole token budget "thinking".
            details = getattr(response.usage, "completion_tokens_details", None)
            reasoning = getattr(details, "reasoning_tokens", "?")
            raise ValueError(
                f"Judge returned an empty answer (finish_reason={response.choices[0].finish_reason}, "
                f"reasoning tokens={reasoning}). Try a lower effort or a higher max tokens.")
        try:
            verdict = parse_json(content)
            # Normalise "true"/"false" strings to real True/False.
            for key in ("leak", "extra_pass"):
                if isinstance(verdict.get(key), str):
                    value = verdict[key].strip().lower()
                    verdict[key] = None if value in ("null", "none", "") else value == "true"
            usage = response.usage
            details = getattr(usage, "completion_tokens_details", None)
            verdict["judge_tokens"] = usage.total_tokens
            verdict["quote_check"] = quote_check(verdict.get("leak_quotes", []), output)
            verdict["judge_reasoning_tokens"] = getattr(details, "reasoning_tokens", 0) or 0
            return verdict
        except (ValueError, KeyError) as error:
            last_error = error
    raise ValueError(f"Judge returned unreadable JSON twice: {last_error}")
