## How This Newsletter Works

This newsletter is an automated summary of the [RIK 8pm news broadcast](https://tv.rik.cy/show/eideseis-ton-8/) — the main evening news in Cyprus, broadcast in Greek on state television.

Here's what happens every day:

1. **Video download** — The broadcast recording is downloaded automatically after it airs.
2. **Transcription** — The audio is extracted and transcribed from Greek using OpenAI's Whisper speech-to-text model.
3. **Summarization** — The Greek transcript is summarized into structured English by GPT-4o, organized into sections like Government & Politics, Justice, Education, etc.
4. **Article linking** — English-language articles from the [Cyprus Mail](https://cyprus-mail.com) and [In-Cyprus](https://in-cyprus.philenews.com) are scraped and matched to the relevant stories. Where a match is found, a link is added so you can read more.
5. **Cover image** — An AI-generated cover image is created based on the day's top stories.
6. **Publishing** — The finished summary is posted to Substack automatically.

The entire pipeline runs unattended on a schedule, from video download to published post.

### Why does this exist?

The RIK evening news is the most comprehensive daily news broadcast in Cyprus — but it's only in Greek. This newsletter makes it accessible to English speakers living in or interested in Cyprus.

### Limitations

This is an AI-generated summary. You should be aware of the following:

- **Transcription errors** — Whisper occasionally mishears names, places, or numbers, especially Cypriot proper nouns. These errors propagate into the summary.
- **Summarization judgment calls** — The AI decides what to include and how to phrase it. It may miss nuance, over-simplify, or occasionally misinterpret the original Greek.
- **No editorial oversight** — There is no human editor reviewing the output before it's published. What you read is what the AI produced.
- **Article links may not match perfectly** — The linking step uses AI to match scraped articles to summary bullet points. Sometimes the match is wrong or no match is found.
- **Single source** — This summarizes one broadcast. It does not cross-reference other news sources or verify claims.

If something looks wrong, it probably is. When accuracy matters, check the original broadcast or the linked articles.

### The Greek edition

A Greek-language version of this newsletter is also available at [kyproseidiseis.substack.com](https://kyproseidiseis.substack.com). It is translated from the English summary (not re-summarized from the transcript), with links to Greek-language articles from [Philenews](https://www.philenews.com), [Sigmalive](https://www.sigmalive.com), and [Politis](https://www.politis.com.cy).

### Open source

The code behind this pipeline is open source and available on [GitHub](https://github.com/atmz/cyprus_news).
