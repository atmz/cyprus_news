import os, base64, textwrap

SOCIAL_W = 1200  # OG-friendly
SOCIAL_H = 628

# One place to tweak your house style
STYLE_SEED = (
    "Clean flat-vector editorial collage, minimalist geometric shapes, muted teal/amber palette, "
    "soft paper grain, gentle halftone, thick outlines, NO photorealism, NO text, high contrast,"
    " modern newspaper illustration, consistent visual language across days."
)

def build_image_prompt(day_str: str, headlines_md: str, lead_subject: str | None,
                       allow_faces: bool) -> str:
    # Use up to 4 concise bullet themes
    lines = [ln.strip("-• ").strip() for ln in headlines_md.splitlines() if ln.strip()]
    bullets = [ln for ln in lines][:4]
    bullets_text = "; ".join(bullets) if bullets else "Cyprus daily news topics"

    face_clause = (
        "If depicting people, use stylized caricature (exaggerated but respectful), avoid likeness-level realism. "
        if allow_faces else
        "Avoid faces; use silhouettes, hands, emblems, buildings, or symbolic objects instead. "
    )

    subject_clause = f"Lead subject: {lead_subject}. " if lead_subject else ""

    return (
        f"Create a non-photorealistic, flat-vector editorial illustration for a Cyprus news digest dated {day_str}. "
        f"{subject_clause}Focus on 3–5 symbolic elements matching: {bullets_text}. "
        f"{face_clause}"
        f"Center composition, simple geometric forms, limited palette, subtle gradients. "
        f"Aspect ratio {SOCIAL_W}:{SOCIAL_H}. {STYLE_SEED}"
    )

def generate_ai_image_from_headlines(client, day, top_stories_md, out_path,
                                     allow_faces: bool = True,
                                     lead_subject: str | None = None,
                                     model: str = "gpt-image-1"):
    """
    Returns image path on success, None on failure. No local fallback.
    """
    prompt = build_image_prompt(day.strftime("%A, %d %B %Y"), top_stories_md, lead_subject, allow_faces)

    try:
        img = client.images.generate(model=model, prompt=prompt, size="1536x1024", n=1)
        b64 = img.data[0].b64_json
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(b64))
        return out_path
    except Exception as e:
        print(f"⚠️ Image generation failed: {e}")
        return None

def make_daily_image(client, day, top_stories_md, out_dir,
                     allow_faces: bool = True, lead_subject: str | None = None):
    img_path = os.path.join(out_dir, "cover.png")
    return generate_ai_image_from_headlines(
        client, day, top_stories_md, img_path, allow_faces=allow_faces, lead_subject=lead_subject
    )

import re, base64, os

STYLE_SEED = (
    "Clean flat-vector editorial collage, minimalist geometric shapes, muted teal/amber palette, "
    "soft paper grain, gentle halftone, thick outlines, NO photorealism, NO text, high contrast, "
    "modern newspaper illustration, consistent visual language across days."
)

def extract_top_stories_from_md(markdown: str) -> str | None:
    """
    Try a few patterns to pull the 'top stories' block from your final markdown.
    Your final_output is: date_heading + \n\n + top_stories + \n\n + linked_main_summary
    So: grab the FIRST block of bullets or the first non-empty block after the heading.
    """
    # 1) Prefer a bullet list block (lines starting with -, •, or *)
    m = re.search(r"(?:^|\n)(?:- |\* |• ).+(?:\n(?:- |\* |• ).+)*", markdown)
    if m:
        return m.group(0).strip()

    # 2) Fallback: first non-empty paragraph after the date heading line
    parts = [p.strip() for p in markdown.split("\n\n") if p.strip()]
    if len(parts) >= 2:
        # parts[0] is usually the date header+disclaimer, parts[1] should be top_stories
        return parts[1]
    return None

def build_image_prompt(day_str: str, headlines_md: str, lead_subject: str | None,
                       allow_faces: bool) -> str:
    lines = [ln.strip("-•* ").strip() for ln in headlines_md.splitlines() if ln.strip()]
    bullets = lines[:4]
    bullets_text = "; ".join(bullets) if bullets else "Cyprus daily news topics"

    face_clause = (
        "If depicting people, use stylized caricature (exaggerated but respectful), avoid likeness-level realism. Note that the current president of Cyprus is Nikos Christodoulides; make sure to use his likeness and not that of previous leaders. The current leader of the TRNC is Tufan Erhürman."
        if allow_faces else
        "Avoid faces; use silhouettes, hands, emblems, buildings, or symbolic objects instead. "
    )
    subject_clause = f"Lead subject: {lead_subject}. " if lead_subject else ""

    return (
        f"Create a non-photorealistic, flat-vector editorial illustration for a Cyprus news digest. "
        f"Focus on 1–3 symbolic elements matching: {subject_clause}. "
        f"{face_clause}"
        f"Center composition, simple geometric forms, limited palette, subtle gradients. "
        f"Aspect ratio 1200:628. {STYLE_SEED}"
    )

def generate_cover_from_md(client, day, markdown: str, out_dir: str | os.PathLike,
                           allow_faces: bool = True, lead_subject: str | None = None,
                           model: str = "gpt-image-1") -> str | None:
    """
    Reads headlines from the markdown text and tries to create cover.png in out_dir.
    Returns the path on success, None on failure.
    """
    top_stories = extract_top_stories_from_md(markdown)
    if not top_stories:
        print("⚠️ Could not extract top stories from markdown; skipping image.")
        return None

    if lead_subject is None:
        # Heuristic: use first bullet/line as subject
        first_line = next((ln.strip("-•* ").strip() for ln in top_stories.splitlines() if ln.strip()), None)
        lead_subject = first_line

    prompt = build_image_prompt(day.strftime("%A, %d %B %Y"), top_stories, lead_subject, allow_faces)

    try:
        print(f"🖼️ Generating cover with prompt: {prompt}")
        img = client.images.generate(model=model, prompt=prompt, size="1536x1024", n=1)
        b64 = img.data[0].b64_json
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "cover.png")
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(b64))
        print(f"🖼️ Cover generated: {out_path}")
        return out_path
    except Exception as e:
        print(f"⚠️ Image generation failed: {e}")
        return None