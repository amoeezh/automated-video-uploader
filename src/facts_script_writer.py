import json
import random
from datetime import date

import google.generativeai as genai

import config
from chart_builder import CHART_TYPES, MAX_RACE_ENTITIES
from retry import with_retry

genai.configure(api_key=config.GEMINI_API_KEY)

MAX_FACTS = 7
MIN_ENTITIES, MAX_ENTITIES = 4, MAX_RACE_ENTITIES
MIN_CHECKPOINTS, MAX_CHECKPOINTS = 6, 10

QUICK_FACTS_SYSTEM = f"""You are a scriptwriter for short vertical Instagram Reels (20-35
seconds) presenting surprising, verifiable "did you know" facts in ENGLISH, each
illustrated by a small data visualization. Punchy, clear, documentary-style narration -
no fluff, no "in this video".

For EACH fact, pick exactly one visualization type from this fixed list:
{json.dumps(CHART_TYPES)}
- hero_number: one striking number (value_a + unit + label_a). Use for a single standout stat.
- compare_two: two things side by side (value_a/label_a vs value_b/label_b).
- line_trend: a value that changed from one point to another (value_a@label_a -> value_b@label_b).
- meter_fill: a percentage/share of a whole (value_a is 0-100, label_a describes it).
- dumbbell_before_after: a clear before/after change (value_a/label_a -> value_b/label_b).
Never invent a new visualization type. Keep numbers real and accurate - if uncertain of an
exact figure, use a well-established rounded estimate rather than inventing precision.
Each sentence must be speakable in 3-5 seconds. Output strict JSON only."""

QUICK_FACTS_SCHEMA_HINT = {
    "title": "short internal title, not shown on screen",
    "facts": [
        {
            "sentence": "the narration sentence for this fact, in English",
            "chart_type": "one of: " + ", ".join(CHART_TYPES),
            "value_a": "number (required)",
            "value_b": "number or null (required for compare_two/line_trend/dumbbell_before_after)",
            "label_a": "short label string",
            "label_b": "short label string or empty string",
            "unit": "short unit string like '%', 'kg', 'years', or ''",
        }
    ],
    "caption": "Instagram caption, 1-2 short sentences, no hashtags in this field",
    "hashtags": ["5 to 8 relevant hashtags without the # symbol"],
}

TIMELINE_RACE_SYSTEM = f"""You are a data storyteller creating a short vertical Instagram
Reel (25-40 seconds) built around ONE continuous animated "bar chart race": {MIN_ENTITIES}
to {MAX_ENTITIES} entities (countries/empires/companies) whose bars grow, shrink, and
reorder as a year counter advances across a historical timeline, narrated in ENGLISH.

You must produce:
1. {MIN_ENTITIES}-{MAX_ENTITIES} entities (short names).
2. {MIN_CHECKPOINTS}-{MAX_CHECKPOINTS} checkpoint years spanning the full timeline
   (include the start and end year), each with one numeric value per entity, in the SAME
   unit throughout (prefer "% of world total" style units so numbers stay small and
   comparable). Use well-established, roughly-accurate historical estimates - rounded
   estimates are fine, invented/implausible numbers are not.
3. 4-7 short narration sentences (spoken in order over the whole animation, NOT tied to
   specific years) that tell the story of how the ranking changed over time - hook,
   turning points, and where things stand today.
Each sentence must be speakable in 3-5 seconds. Output strict JSON only."""

TIMELINE_RACE_SCHEMA_HINT = {
    "title": "short internal title, not shown on screen",
    "chart_title": "on-screen chart heading, e.g. 'World Superpowers by Land Occupied'",
    "unit": "short unit string shown after each number, e.g. '%'",
    "start_year": "integer",
    "end_year": "integer",
    "entities": [f"{MIN_ENTITIES} to {MAX_ENTITIES} short entity names"],
    "checkpoints": [
        {"year": "integer", "values": "array of numbers, same length and order as entities"}
    ],
    "sentences": ["4 to 7 narration sentences in English, spoken in order"],
    "caption": "Instagram caption, 1-2 short sentences, no hashtags in this field",
    "hashtags": ["5 to 8 relevant hashtags without the # symbol"],
}


def _load_topics():
    return json.load(open(config.FACTS_TOPICS_FILE))


def _load_history():
    with open(config.FACTS_STATE_FILE) as f:
        return json.load(f)


def _pick_topic(pillars_key):
    pillars = _load_topics()[pillars_key]
    random.seed(f"{date.today().isoformat()}-{random.random()}")
    return random.choice(pillars)


def _generate(prompt):
    model = genai.GenerativeModel(
        "gemini-flash-latest",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)
    return json.loads(response.text)


def write_quick_facts_script():
    history = _load_history()
    topic = _pick_topic("quick_facts_pillars")
    avoid = history["used_titles"][-30:]

    prompt = f"""{QUICK_FACTS_SYSTEM}

Topic pillar: {topic}
Today's date: {date.today().isoformat()}

Avoid repeating these previously used titles/ideas:
{json.dumps(avoid)}

Return JSON with exactly this shape:
{json.dumps(QUICK_FACTS_SCHEMA_HINT, indent=2)}
"""
    data = with_retry(lambda: _generate(prompt), attempts=3, delay=15, label="Gemini quick-facts generation")

    facts = data.get("facts", [])[:MAX_FACTS]
    for fact in facts:
        if fact.get("chart_type") not in CHART_TYPES:
            fact["chart_type"] = "hero_number"

    return {
        "format": "quick_facts",
        "title": data.get("title", topic),
        "facts": facts,
        "caption": data.get("caption", ""),
        "hashtags": data.get("hashtags", []),
    }


def write_timeline_race_script():
    history = _load_history()
    topic = _pick_topic("timeline_race_pillars")
    avoid = history["used_titles"][-30:]

    prompt = f"""{TIMELINE_RACE_SYSTEM}

Topic: {topic}
Today's date: {date.today().isoformat()}

Avoid repeating these previously used titles/ideas:
{json.dumps(avoid)}

Return JSON with exactly this shape:
{json.dumps(TIMELINE_RACE_SCHEMA_HINT, indent=2)}
"""
    data = with_retry(lambda: _generate(prompt), attempts=3, delay=15, label="Gemini timeline-race generation")

    return {
        "format": "timeline_race",
        "title": data.get("title", topic),
        "chart_title": data.get("chart_title", topic),
        "unit": data.get("unit", ""),
        "start_year": data.get("start_year"),
        "end_year": data.get("end_year"),
        "entities": data.get("entities", []),
        "checkpoints": data.get("checkpoints", []),
        "sentences": data.get("sentences", [])[:7],
        "caption": data.get("caption", ""),
        "hashtags": data.get("hashtags", []),
    }


def write_script():
    fmt = random.choice(["quick_facts", "timeline_race"])
    return write_quick_facts_script() if fmt == "quick_facts" else write_timeline_race_script()


if __name__ == "__main__":
    print(json.dumps(write_script(), indent=2))
