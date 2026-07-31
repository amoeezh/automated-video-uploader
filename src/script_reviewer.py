import json

from groq import Groq

import config

client = Groq(api_key=config.GROQ_API_KEY)

REVIEW_PROMPT = """You are a fact-checking editor for short-form video scripts. You will receive
a JSON script object. Your job:

1. Check every claim for factual accuracy. If something is wrong, misleading, or unverifiable,
   correct or remove it.
2. Tighten the wording so each sentence is speakable in 3-5 seconds.
3. Make sure the hook (first sentence) is strong and not clickbait that the rest doesn't pay off.
4. Keep the same JSON shape you were given. Do not add fields. Do not add commentary.
5. Keep "visual_keywords" aligned 1:1 with "sentences" (same length, same order).

Return strict JSON only, no markdown fences, no explanation.
"""


def review_script(script: dict) -> dict:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": json.dumps(script)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    reviewed = json.loads(response.choices[0].message.content)

    if len(reviewed.get("visual_keywords", [])) != len(reviewed.get("sentences", [])):
        reviewed["visual_keywords"] = script["visual_keywords"]
        reviewed["sentences"] = script["sentences"]

    return reviewed


if __name__ == "__main__":
    import script_writer

    draft = script_writer.write_script()
    print(json.dumps(review_script(draft), indent=2))
