import json
import random
from datetime import date

import google.generativeai as genai

import config
from retry import with_retry

genai.configure(api_key=config.GEMINI_API_KEY)

GAG_TEMPLATES = ["bounce", "wobble", "spin_pop", "surprise_jump", "wiggle_dance"]

SYSTEM_PROMPT = f"""You are a comedy writer for short vertical Instagram Reels (20-35 seconds)
aimed at kids and families: silly, wholesome, meme-style jokes narrated in HINDI (Devanagari
script only, simple everyday vocabulary a child can follow).

Structure every script like this:
1. Setup (1-2 sentences): a simple, relatable, silly everyday situation (a toy, an animal, a
   food, a household object, a kid doing something silly).
2. Escalation (2-3 sentences): the situation gets funnier and more exaggerated, building anticipation.
3. Punchline (1 sentence): the joke payoff - the funniest, most surprising line.
4. Tag line (1 sentence): one short extra laugh, or a silly mock-serious "moral of the story"
   that kids will find funny.

Strict rules:
- ALL text (sentences, caption) must be written in HINDI using Devanagari script. No English words
  mixed in except universally known proper nouns if unavoidable.
- 100% wholesome and kid-safe: no violence, no scary content, no romance, no dark or adult humor,
  no put-downs of real people. Pure silly slapstick/meme humor, like a cartoon gag.
- Each sentence must be short enough to be spoken in 3-4 seconds.
- For "visual_keywords", choose exactly one tag per sentence from this fixed list only:
  {json.dumps(GAG_TEMPLATES)}. Pick whichever gag best matches the comedic beat of that sentence
  (e.g. "surprise_jump" for the punchline, "bounce"/"wobble"/"wiggle_dance" for build-up,
  "spin_pop" for a silly transformation moment). Never invent new tags.
Output strict JSON only, matching the schema given."""

SCHEMA_HINT = {
    "title": "short internal title in English, not shown on screen",
    "sentences": ["6 to 8 sentences total in Hindi (Devanagari), following the setup/escalation/punchline/tag structure. The second-to-last or last sentence is the punchline."],
    "visual_keywords": ["one gag tag per sentence, same length as sentences, each one of: " + ", ".join(GAG_TEMPLATES)],
    "caption": "Instagram caption text in Hindi, 1-2 short fun sentences, no hashtags in this field",
    "hashtags": ["5 to 8 relevant hashtags without the # symbol, mix of Hindi-audience and kids/funny/meme tags"],
}


def pick_topic(history):
    pillars = json.load(open(config.TOPICS_FILE))["pillars"]
    random.seed(f"{date.today().isoformat()}-{random.random()}")
    return random.choice(pillars)


def load_history():
    with open(config.STATE_FILE) as f:
        return json.load(f)


def _generate(prompt):
    model = genai.GenerativeModel(
        "gemini-flash-latest",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)
    return json.loads(response.text)


def write_script():
    history = load_history()
    topic = pick_topic(history)
    avoid = history["used_titles"][-30:]

    prompt = f"""{SYSTEM_PROMPT}

Topic pillar: {topic}
Today's date: {date.today().isoformat()}

Avoid repeating these previously used titles/ideas:
{json.dumps(avoid)}

Return JSON with exactly this shape:
{json.dumps(SCHEMA_HINT, indent=2, ensure_ascii=False)}
"""

    data = with_retry(lambda: _generate(prompt), attempts=3, delay=15, label="Gemini script generation")

    if len(data["sentences"]) > config.MAX_SENTENCES:
        keep = config.MAX_SENTENCES - 1
        data["sentences"] = data["sentences"][:keep] + [data["sentences"][-1]]
        data["visual_keywords"] = data["visual_keywords"][:keep] + [data["visual_keywords"][-1]]

    data["visual_keywords"] = [
        kw if kw in GAG_TEMPLATES else random.choice(GAG_TEMPLATES)
        for kw in data["visual_keywords"]
    ]

    return data


if __name__ == "__main__":
    print(json.dumps(write_script(), indent=2, ensure_ascii=False))
