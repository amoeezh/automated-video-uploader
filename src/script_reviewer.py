import json

from groq import Groq

import config
from retry import with_retry
from script_writer import GAG_TEMPLATES

client = Groq(api_key=config.GROQ_API_KEY)

REVIEW_PROMPT = f"""You are a comedy editor and kid-safety reviewer for short-form meme/joke
videos narrated in HINDI (Devanagari script) aimed at kids and families. You will receive a JSON
script object.

Your job:
1. Make sure it is actually funny: a clear silly setup, a build-up, and a real punchline that pays
   off. Tighten weak jokes.
2. Enforce kid-safety: remove/rewrite anything scary, violent, mean-spirited, romantic, or
   adult-themed. Keep it wholesome slapstick/meme humor only.
3. Keep ALL sentence and caption text in HINDI (Devanagari script). Fix any stray English words
   (except unavoidable proper nouns) by translating them to Hindi.
4. Tighten wording so each sentence is speakable in 3-4 seconds.
5. Keep "visual_keywords" aligned 1:1 with "sentences" (same length, same order), and every value
   must be exactly one of: {json.dumps(GAG_TEMPLATES)}. Never invent new tags.
6. Keep the same JSON shape you were given. Do not add fields. Do not add commentary.

Return strict JSON only, no markdown fences, no explanation.
"""


def _review(script):
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": json.dumps(script, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(response.choices[0].message.content)


def review_script(script: dict) -> dict:
    reviewed = with_retry(lambda: _review(script), attempts=3, delay=15, label="Groq script review")

    if len(reviewed.get("visual_keywords", [])) != len(reviewed.get("sentences", [])):
        reviewed["visual_keywords"] = script["visual_keywords"]
        reviewed["sentences"] = script["sentences"]

    reviewed["visual_keywords"] = [
        kw if kw in GAG_TEMPLATES else script["visual_keywords"][i % len(script["visual_keywords"])]
        for i, kw in enumerate(reviewed["visual_keywords"])
    ]

    return reviewed


if __name__ == "__main__":
    import script_writer

    draft = script_writer.write_script()
    print(json.dumps(review_script(draft), indent=2, ensure_ascii=False))
