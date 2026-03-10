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


def _find_existing_match(name, existing_by_name):
    """Find an existing topic by exact or fuzzy name match.

    Returns the existing topic's name_en key if found, None otherwise.
    """
    # Exact match
    if name in existing_by_name:
        return name

    # Fuzzy: check if one name contains the other (handles
    # "Iran-Israel Conflict" matching "Iran-Israel-US Conflict")
    name_lower = name.lower()
    for existing_name in existing_by_name:
        existing_lower = existing_name.lower()
        if name_lower in existing_lower or existing_lower in name_lower:
            print(f"📎 Fuzzy-matched detected topic '{name}' to existing '{existing_name}'")
            return existing_name

    return None


def update_topics(data, detected_topics, today):
    """Merge detected topics into the ongoing topics list.

    Returns (updated_data, topics_changed: bool)
    """
    today_str = today.isoformat()
    existing_by_name = {t["name_en"]: t for t in data["topics"]}
    topics_changed = False

    for detected in detected_topics:
        name = detected.get("name_en", "").strip()
        if not name:
            continue

        match = _find_existing_match(name, existing_by_name)
        if match:
            # Existing topic confirmed today - bump last_seen
            if existing_by_name[match]["last_seen"] != today_str:
                existing_by_name[match]["last_seen"] = today_str
                print(f"📌 Ongoing topic confirmed: {match}")
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

    return data, topics_changed


def build_ongoing_topics_section_entries(topics, lang="en"):
    """Build section list entries for ongoing topics to insert into the prompt's section list.

    Returns a string with entries like:
      - `### Iran-Israel-US Conflict` (ongoing major story — all related bullets go here)
      - `### Foot-and-Mouth Disease Outbreak` (ongoing major story — all related bullets go here)

    Returns empty string if no active topics.
    """
    if not topics:
        return ""

    name_key = f"name_{lang}" if lang != "en" else "name_en"

    lines = []
    for topic in topics:
        name = topic.get(name_key, topic["name_en"])
        desc = topic.get("description", "")
        lines.append(f"  - `### {name}` — use this EXACT header. All bullets about: {desc}")

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
