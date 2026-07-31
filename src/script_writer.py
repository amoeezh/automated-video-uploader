import json
import random
from datetime import date

import google.generativeai as genai

import config

genai.configure(api_key=config.GEMINI_API_KEY)

SYSTEM_PROMPT = """You are a scriptwriter for short vertical Instagram Reels (30-45 seconds)
that tell TRUE historical stories. Every video is a real, verifiable historical story with a
narrative arc, not just a list of facts. No fluff, no "in this video", no intros that waste time.

Structure every script like this:
1. Hook (1 sentence): drop the viewer into the middle of the story or its stakes, don't summarize it.
2. Setup (1-2 sentences): who, where, when.
3. Rising action / conflict (2-4 sentences): what happened, the tension, the stakes, the turn.
4. Resolution (1-2 sentences): how it concluded.
5. Lesson (exactly 1 final sentence): what we can actually learn from this story today. Start
   this sentence with something like "The lesson:" or "What this teaches us is" or a natural
   equivalent. It must be a genuine takeaway, not a restatement of the facts.

Each sentence must be short enough to be spoken in 3-5 seconds. Keep it historically accurate —
if a detail is disputed or unverified, don't state it as fact. Output strict JSON only, matching
the schema given."""

SCHEMA_HINT = {
    "title": "short internal title, not shown on screen",
    "sentences": ["7 to 9 sentences total, following the hook/setup/conflict/resolution/lesson structure. The LAST sentence must always be the lesson."],
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
        "gemini-flash-latest",
        generation_config={"response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt)
    data = json.loads(response.text)

    if len(data["sentences"]) > config.MAX_SENTENCES:
        # Keep the lesson (always the last sentence) even when trimming down to budget.
        keep = config.MAX_SENTENCES - 1
        data["sentences"] = data["sentences"][:keep] + [data["sentences"][-1]]
        data["visual_keywords"] = data["visual_keywords"][:keep] + [data["visual_keywords"][-1]]

    return data


if __name__ == "__main__":
    print(json.dumps(write_script(), indent=2))
