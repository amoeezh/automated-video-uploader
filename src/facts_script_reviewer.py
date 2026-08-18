import json

from groq import Groq

import config
from chart_builder import CHART_TYPES
from retry import with_retry

client = Groq(api_key=config.GROQ_API_KEY)

QUICK_FACTS_REVIEW_PROMPT = f"""You are a fact-checking editor for short-form "did you know"
Instagram Reels narrated in English, each fact illustrated by a small chart.

Your job:
1. Check every numeric claim. If a number is wrong, outdated, or implausible, correct it to a
   well-established, roughly-accurate estimate. If genuinely uncertain, soften the wording
   ("roughly", "about") rather than stating false precision.
2. Make sure each sentence is a real, interesting, verifiable fact - not a vague generality.
3. Tighten wording so each sentence is speakable in 3-5 seconds.
4. Keep "chart_type" for every fact one of exactly: {json.dumps(CHART_TYPES)}. Never invent a
   new type. Keep value_a/value_b/label_a/label_b/unit consistent with the (possibly corrected)
   sentence.
5. Keep the same JSON shape you were given (same number of facts, same field names). Do not add
   fields or commentary.

Return strict JSON only, no markdown fences, no explanation.
"""

TIMELINE_RACE_REVIEW_PROMPT = """You are a fact-checking editor for a short-form Instagram Reel
built around one animated historical "bar chart race" (a year counter advancing while bars for
several entities grow/shrink/reorder), narrated in English.

Your job:
1. Check the historical data for plausibility: is the relative ranking of entities at each
   checkpoint year roughly correct? Is the order of magnitude right? Correct any checkpoint
   values that are clearly wrong or historically implausible - use well-established rounded
   estimates, not invented precision.
2. Make sure checkpoints are sorted chronologically and every checkpoint has exactly one value
   per entity, in the same order as the "entities" list.
3. Make sure the narration sentences tell a coherent story of how the ranking changed over time
   (hook, key turning points, where things stand today/at end_year), and are each speakable in
   3-5 seconds.
4. Keep the same JSON shape you were given (same field names, same entity count, same or
   corrected checkpoint years/values). Do not add fields or commentary.

Return strict JSON only, no markdown fences, no explanation.
"""


def _review(system_prompt, script, label):
    def call():
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(script)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        return json.loads(response.choices[0].message.content)

    return with_retry(call, attempts=3, delay=15, label=label)


def review_quick_facts(script):
    reviewed = _review(QUICK_FACTS_REVIEW_PROMPT, script, "Groq quick-facts review")

    facts = reviewed.get("facts")
    if not facts or len(facts) != len(script["facts"]):
        facts = script["facts"]
    for fact in facts:
        if fact.get("chart_type") not in CHART_TYPES:
            fact["chart_type"] = "hero_number"

    reviewed["facts"] = facts
    reviewed["format"] = "quick_facts"
    reviewed.setdefault("title", script.get("title"))
    reviewed.setdefault("caption", script.get("caption", ""))
    reviewed.setdefault("hashtags", script.get("hashtags", []))
    return reviewed


def review_timeline_race(script):
    reviewed = _review(TIMELINE_RACE_REVIEW_PROMPT, script, "Groq timeline-race review")

    if not reviewed.get("entities") or not reviewed.get("checkpoints"):
        reviewed["entities"] = script.get("entities")
        reviewed["checkpoints"] = script.get("checkpoints")
    if len(reviewed.get("entities") or []) != len(script.get("entities") or []):
        reviewed["entities"] = script.get("entities")
        reviewed["checkpoints"] = script.get("checkpoints")

    reviewed["format"] = "timeline_race"
    reviewed.setdefault("start_year", script.get("start_year"))
    reviewed.setdefault("end_year", script.get("end_year"))
    reviewed.setdefault("chart_title", script.get("chart_title"))
    reviewed.setdefault("unit", script.get("unit"))
    reviewed.setdefault("title", script.get("title"))
    reviewed.setdefault("caption", script.get("caption", ""))
    reviewed.setdefault("hashtags", script.get("hashtags", []))
    if not reviewed.get("sentences"):
        reviewed["sentences"] = script.get("sentences", [])
    return reviewed


def review_script(script):
    if script.get("format") == "timeline_race":
        return review_timeline_race(script)
    return review_quick_facts(script)


if __name__ == "__main__":
    import facts_script_writer

    draft = facts_script_writer.write_script()
    print(json.dumps(review_script(draft), indent=2))
