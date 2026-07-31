import json

from groq import Groq

import config

client = Groq(api_key=config.GROQ_API_KEY)

REVIEW_PROMPT = """You are a historian and fact-checking editor for short-form historical
storytelling videos. You will receive a JSON script object telling a true historical story.
Your job:

1. Check every historical claim carefully. Popular history is full of myths and oversimplified
   legends (e.g. "Napoleon was short", "Vikings wore horned helmets") — catch and correct these.
   If a detail is disputed among historians or unverifiable, soften it ("some accounts say...")
   or remove it rather than stating it as settled fact.
2. Verify the story still has a clear arc: hook, setup, conflict/turn, resolution, and a final
   lesson sentence. The LAST sentence must remain a genuine, non-generic lesson learned from the
   story — never drop or water it down to a plain fact restatement.
3. Tighten the wording so each sentence is speakable in 3-5 seconds.
4. Make sure the hook (first sentence) is strong and not clickbait that the rest doesn't pay off.
5. Keep the same JSON shape you were given. Do not add fields. Do not add commentary.
6. Keep "visual_keywords" aligned 1:1 with "sentences" (same length, same order).

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
