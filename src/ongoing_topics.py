# ongoing_topics.py – Persistent top-level sections for major ongoing stories

import json
import os
from datetime import date

TOPICS_FILE = "data/ongoing_topics.json"
DETECT_PROMPT_FILE = "src/prompts/detect_topics_prompt.txt"
RESTRUCTURE_PROMPT_FILE = "src/prompts/restructure_summary_prompt.txt"
DETECT_MODEL = "gpt-4.1-mini"
RESTRUCTURE_MODEL = "gpt-4.1-mini"


def load_ongoing_topics():
    """Load ongoing_topics.json. Returns empty structure if file doesn't exist."""
    if not os.path.exists(TOPICS_FILE):
        return {"topics": [], "config": {"expiry_days": 7}}
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_ongoing_topics(data):
    """Save ongoing_topics.json with pretty formatting for human editability."""
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def expire_topics(data, today):
    """Remove topics that haven't appeared for more than expiry_days."""
    expiry_days = data.get("config", {}).get("expiry_days", 7)
    active = []
    for topic in data["topics"]:
        last_seen = date.fromisoformat(topic["last_seen"])
        days_stale = (today - last_seen).days
        if days_stale <= expiry_days:
            active.append(topic)
        else:
            print(f"📤 Expiring ongoing topic: {topic['name_en']} (last seen {topic['last_seen']}, {days_stale} days ago)")
    data["topics"] = active
    return data


def detect_ongoing_topics(client, summary_text, existing_topics, today):
    """Use LLM to detect ongoing topics from today's summary.

    Returns a list of detected topic dicts with keys:
      name_en, name_el, description, is_new (bool)
    """
    with open(DETECT_PROMPT_FILE, "r", encoding="utf-8") as f:
        detect_prompt = f.read().strip()

    existing_list = ""
    if existing_topics:
        for t in existing_topics:
            existing_list += f"- {t['name_en']}: {t['description']}\n"
    else:
        existing_list = "(none)"

    prompt = detect_prompt.replace("[EXISTING_TOPICS]", existing_list).replace("[TODAY]", today.isoformat())

    response = client.chat.completions.create(
        model=DETECT_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": summary_text},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    print(f"🔍 Topic detection response: {raw}")

    try:
        result = json.loads(raw)
        return result.get("topics", [])
    except json.JSONDecodeError:
        print("⚠️ Failed to parse topic detection response as JSON")
        return []


def update_topics(data, detected_topics, today):
    """Merge detected topics into the ongoing topics list.

    Returns (updated_data, topics_changed: bool)
    """
    today_str = today.isoformat()
    existing_by_name = {t["name_en"]: t for t in data["topics"]}
    topics_changed = False

    confirmed_names = set()

    for detected in detected_topics:
        name = detected.get("name_en", "").strip()
        if not name:
            continue

        if name in existing_by_name:
            # Existing topic confirmed today - bump last_seen
            if existing_by_name[name]["last_seen"] != today_str:
                existing_by_name[name]["last_seen"] = today_str
                print(f"📌 Ongoing topic confirmed: {name}")
            confirmed_names.add(name)
        else:
            # New topic detected
            new_topic = {
                "name_en": name,
                "name_el": detected.get("name_el", name),
                "description": detected.get("description", ""),
                "first_seen": today_str,
                "last_seen": today_str,
            }
            data["topics"].append(new_topic)
            topics_changed = True
            print(f"🆕 New ongoing topic detected: {name}")

    # Check if any new topics were added
    if topics_changed:
        return data, True

    return data, False


def build_ongoing_topics_prompt_section(topics, lang="en"):
    """Build the prompt injection text for ongoing topics.

    Returns empty string if no active topics.
    """
    if not topics:
        return ""

    name_key = f"name_{lang}" if lang != "en" else "name_en"

    lines = [
        "",
        "ONGOING MAJOR STORIES:",
        "The following are major ongoing stories. If today's news contains information "
        "about any of these topics, create a dedicated ### section for it (using the "
        "exact name provided) and place all related bullets there instead of in the "
        "regular sections. Place these sections immediately after ### Top stories "
        "(or ### Κύριες Ειδήσεις for Greek).",
        "",
    ]
    for topic in topics:
        name = topic.get(name_key, topic["name_en"])
        desc = topic.get("description", "")
        lines.append(f"- {name}: {desc}")

    lines.append("")
    lines.append("If a topic has no news today, do not create a section for it.")
    lines.append("")

    return "\n".join(lines)


def restructure_summary_with_topics(client, summary_text, detected_topics, lang="en"):
    """Use LLM to move bullets related to ongoing topics into dedicated sections.

    Only called when new topics were detected (topics_changed=True).
    Returns the restructured summary text.
    """
    name_key = f"name_{lang}" if lang != "en" else "name_en"

    topic_descriptions = []
    for t in detected_topics:
        name = t.get(name_key, t["name_en"])
        desc = t.get("description", "")
        topic_descriptions.append(f"- {name}: {desc}")

    with open(RESTRUCTURE_PROMPT_FILE, "r", encoding="utf-8") as f:
        restructure_prompt = f.read().strip()

    prompt = restructure_prompt.replace("[TOPIC_LIST]", "\n".join(topic_descriptions))

    response = client.chat.completions.create(
        model=RESTRUCTURE_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": summary_text},
        ],
        temperature=0.0,
    )

    result = response.choices[0].message.content.strip()
    print(f"🔄 Summary restructured with ongoing topic sections")
    return result
