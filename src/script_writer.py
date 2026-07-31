import json
import random
from datetime import date

import google.generativeai as genai

import config

genai.configure(api_key=config.GEMINI_API_KEY)

SYSTEM_PROMPT = """You are a scriptwriter for short vertical Instagram Reels (30-45 seconds).
Write tight, punchy, factually accurate narration. No fluff, no "in this video", no intros
that waste time. Hook the viewer in the first sentence. Each sentence must be short enough
to be spoken in 3-5 seconds. Output strict JSON only, matching the schema given."""

SCHEMA_HINT = {
    "title": "short internal title, not shown on screen",
    "sentences": ["sentence 1", "sentence 2", "... 6-8 sentences total"],
    "visual_keywords": ["one or two search keywords per sentence, same length as sentences"],
    "caption": "Instagram caption text, 1-3 sentences, no hashtags in this field",
    "hashtags": ["5 to 8 relevant hashtags without the # symbol"],
}


def pick_topic(history):
    pillars = json.load(open(config.TOPICS_FILE))["pillars"]
    random.seed(f"{date.today().isoformat()}-{random.random()}")
    return random.choice(pillars)


def load_history():
    with open(config.STATE_FILE) as f:
        return json.load(f)


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
{json.dumps(SCHEMA_HINT, indent=2)}
"""

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)
    data = json.loads(response.text)

    if len(data["sentences"]) > config.MAX_SENTENCES:
        data["sentences"] = data["sentences"][: config.MAX_SENTENCES]
        data["visual_keywords"] = data["visual_keywords"][: config.MAX_SENTENCES]

    return data


if __name__ == "__main__":
    print(json.dumps(write_script(), indent=2))
