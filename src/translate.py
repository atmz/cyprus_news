from pathlib import Path
from openai import OpenAI
from timing import timing_step

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_translate_prompt(target_lang="el"):
    """Load language-specific translate prompt, falling back to generic."""
    lang_file = PROMPTS_DIR / f"translate_prompt_{target_lang}.txt"
    fallback = PROMPTS_DIR / "translate_prompt.txt"
    path = lang_file if lang_file.exists() else fallback
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def translate_summary(client, english_summary, target_lang="el", model="gpt-4o"):
    """Translate an English summary to the target language."""
    prompt = load_translate_prompt(target_lang)

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
