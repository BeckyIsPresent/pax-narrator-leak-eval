# The shared "mini Pax": everything needed to play ONE turn.
# run_case.py and run_experiment.py both use these functions,
# so the two scripts always build prompts exactly the same way.

import os
import yaml

BASE_INSTRUCTIONS = (
    "You are the game master of a grand strategy sandbox game. "
    "Given the world rules, the current game state, the player's nation and actions, "
    "and how much time passes, simulate what happens in the world during that period. "
    "Write 6 to 12 dated events in chronological order. Include the results of the "
    "player's actions AND notable events happening elsewhere in the world, involving "
    "other nations and factions. Each event has a short headline and 2 to 4 sentences."
)


def load_case(path):
    """Read a test case YAML file into a dictionary."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_preset_text(case):
    """Use the full local preset if the case points to one and it exists,
    otherwise fall back to the short paraphrased excerpt in the case file."""
    preset_file = case.get("preset_file")
    if preset_file and os.path.exists(preset_file):
        with open(preset_file, encoding="utf-8") as f:
            return f.read(), "full preset"
    return case["preset_excerpt"], "excerpt"


# The harness versions being compared. Each adds rule files on top of the shared prompt.
VERSIONS = {
    "baseline": [],
    "rule": ["rules/perspective_rule.txt"],
    "rule_reports": ["rules/perspective_rule.txt", "rules/report_rule.txt"],
}


def load_rules(version):
    texts = []
    for path in VERSIONS[version]:
        with open(path, encoding="utf-8") as f:
            texts.append(f.read())
    return "\n\n".join(texts)


def build_prompts(case, version):
    """Returns three pieces:
    - system_shared: instructions + world rules. IDENTICAL for baseline and rule runs,
      so it can be cached and reused cheaply.
    - system_extra: the extra rules for this version (none for baseline), placed AFTER the shared part.
    - user_prompt: game state + player action + time jump."""
    preset_text, _ = load_preset_text(case)
    system_shared = BASE_INSTRUCTIONS + "\n\nWORLD RULES:\n" + preset_text
    system_extra = load_rules(version)

    facts = "\n".join("- " + fact for fact in case["game_state"]["facts"])
    user_prompt = (
        f"Player nation: {case['player_nation']}\n"
        f"Current date: {case['game_state']['date']}\n"
        f"Known facts:\n{facts}\n\n"
        f"Player action: {case['player_action']}\n"
        f"Time passes: {case['time_jump']}"
    )
    return system_shared, system_extra, user_prompt


def make_client():
    from openai import OpenAI
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY_PAX_HARNESS_DEMO"],
    )


def build_system_message(model, system_shared, system_extra):
    """Anthropic models need an explicit 'cache_control' marker to cache the long shared part.
    Other providers (e.g. DeepSeek, OpenAI) cache repeated prompt starts automatically."""
    if model.startswith("anthropic/"):
        blocks = [{"type": "text", "text": system_shared, "cache_control": {"type": "ephemeral"}}]
        if system_extra:
            blocks.append({"type": "text", "text": system_extra})
        return {"role": "system", "content": blocks}
    text = system_shared + ("\n\n" + system_extra if system_extra else "")
    return {"role": "system", "content": text}


MAX_OUTPUT_TOKENS = 8000  # about twice a normal turn; stops runaway replies (one pilot reply hit 18k)


def ask_model(client, model, system_shared, system_extra, user_prompt):
    """Send one turn to the model, retrying once after a short wait if the call fails.
    Returns (reply text, input tokens, output tokens, cached input tokens, finish reason)."""
    import time
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    build_system_message(model, system_shared, system_extra),
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=MAX_OUTPUT_TOKENS,
            )
            break
        except Exception:
            if attempt == 1:
                raise
            time.sleep(5)
    usage = response.usage
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0
    choice = response.choices[0]
    return (choice.message.content or "", usage.prompt_tokens, usage.completion_tokens,
            cached, choice.finish_reason)


def find_leaks(case, output):
    """Simple keyword check: which secret keywords appear in the output?"""
    return [k for k in case["secret"]["leak_keywords"] if k.lower() in output.lower()]
