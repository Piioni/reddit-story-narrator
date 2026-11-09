# Reddit Story Narrator

[![Tests](https://github.com/Piioni/reddit-story-narrator/actions/workflows/tests.yml/badge.svg)](https://github.com/Piioni/reddit-story-narrator/actions/workflows/tests.yml)

Scrapes story-style Reddit posts, prepares the text for text-to-speech, and narrates it with Azure Speech.

> **Status:** the scraping, storage, narration script, and voice synthesis work. Video composition (subtitles and backgrounds) is **not implemented**. This is a personal project with low maintenance.

## How it works

```text
Reddit (PRAW)
   -> RedditScraper        finds posts, author updates and top comments, removes duplicates
   -> PostgreSQL           one database per category
   -> ContentRetriever     takes unprocessed posts
   -> NarrativeBuilder     builds the script: title, post, updates, comments
   -> TextOptimizer        rewrites text so a voice reads it well
   -> VoiceSynthesizer     Azure Speech -> full_audio.wav + audio_metadata.json
```

- **Updates.** Stories often continue in later posts. The scraper looks for the author's updates in the post's comments, in the subreddit, and in the author's profile, and drops duplicates by hashing the normalized text.
- **Categories.** Subreddits are grouped into categories, each with its own database. The defaults are `aita`, `relationship`, `legal`, `work`, `tech`, and `creepypastas`, defined in `src/database_scripts/migrate_db.py`.
- **Text for voices.** `TextOptimizer` expands Reddit abbreviations (`AITA`, `BF`, `MIL`), spells out money and numbers, expands contractions, adds pauses after introductory phrases, and censors profanity.
- **Timings.** The audio comes with per-word timestamps in `audio_metadata.json`, which is what subtitles would be built from.

## Setup

You need Python 3.12 or newer (what the tests run on), Docker, a [Reddit API app](https://www.reddit.com/prefs/apps) (type "script"), and an Azure Speech resource if you want audio.

```bash
git clone https://github.com/Piioni/reddit-story-narrator.git
cd reddit-story-narrator

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env              # then fill in the values

docker compose up -d --wait       # PostgreSQL, bound to localhost
python src/database_scripts/migrate_db.py --init   # first run: admin database, schema and categories
```

Later runs of `migrate_db.py` without `--init` only add categories that are missing.

### Configuration

| Variable | Purpose |
| --- | --- |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB` | Database connection |
| `POSTGRES_PASSWORD` | Required. There is no default |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | Reddit API credentials |
| `POST_TYPE` | `hot` (default), `top`, `rising` or `controversial` |
| `TIME_FILTER` | Time window for `top`: `hour`, `day`, `week`, `month`, `year` or `all` |
| `LIMIT` | Posts to keep per subreddit |
| `MIN_UPVOTES`, `MIN_COMMENT_UPVOTES` | Score thresholds for posts and comments |
| `COMMENT_LIMIT`, `MAX_COMMENT_LENGTH` | How many comments to keep and how long they can be |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `AZURE_VOICE_NAME` | Azure Speech |

## Usage

**Scrape.** `main.py` is an interactive menu, in Spanish, to pick a category, run the scraper, and see statistics:

```bash
python src/main.py
```

**Narrate.** This step is not wired into `main.py` yet. Two helper scripts run it by hand on one unprocessed post:

```bash
PYTHONPATH=src python scripts/text_pipeline_preview.py   # prints the script before and after optimization
PYTHONPATH=src python scripts/azure_speech_check.py      # writes audio to test_audio/<post_id>/
```

`azure_speech_check.py` reads one post from the `aita` category and needs the Azure variables.

## Tests

The tests cover the pure logic (text optimization, script building, and update deduplication) and need no network, database, or Azure account.

```bash
pip install pytest
pytest
```

## Responsible use

Reddit posts belong to their authors and are covered by Reddit's [Data API Terms](https://www.redditinc.com/policies/data-api-terms) and User Agreement. Use your own API credentials, respect the rate limits, and check those terms, and the policies of wherever you publish, before reusing or republishing anyone's content. This project does not do that for you.

## Known limitations

- No video composition: `VoiceSynthesizer` is the end of the pipeline.
- The narration step is run by hand and is not part of `main.py`.
- Log messages and the menu are in Spanish.
- `TextOptimizer` is tuned for English-language subreddits.

## License

[MIT](LICENSE)
