from pathlib import Path
from openai import OpenAI
from timing import timing_step

TRANSLATE_PROMPT_FILE = Path(__file__).parent / "prompts" / "translate_prompt.txt"

def load_translate_prompt():
    with open(TRANSLATE_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def translate_summary(client, english_summary, target_lang="el", model="gpt-4o"):
    """Translate an English summary to the target language."""
    prompt = load_translate_prompt()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": english_summary}
        ],
        temperature=0.2
    )

    translated = response.choices[0].message.content.strip()
    usage = response.usage
    return translated, usage
