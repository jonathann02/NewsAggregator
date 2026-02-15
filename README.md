# AI News Aggregator

## Overview
Build a Python backend that aggregates AI-related news from multiple sources (YouTube channels via RSS feeds and blog URLs via scraping), stores structured data in PostgreSQL, and generates a daily digest. The digest uses an LLM to produce short, insight-aware summaries and emails the result with links back to original sources.

## Goals
- Ingest from multiple source types:
  - YouTube channels (via RSS feeds)
  - Blog URLs (scraped)
- Store data in PostgreSQL with clear structure for sources and articles.
- Generate a daily digest every 24 hours using OpenAI and a configurable agent system prompt file.
- Email the daily digest to a specified recipient using a free, easy-to-integrate provider (Gmail SMTP by default).
- Keep the design deployable to Render with a simple schedule.

## Tech Stack
- Python backend
- PostgreSQL
- SQLAlchemy for models and table creation
- OpenAI API for LLM summaries
- Scheduler for daily runs
- Email delivery via SMTP (Gmail SMTP by default)

## High-Level Architecture
1. Ingestion
   - YouTube: Fetch latest videos from channel RSS feeds.
   - Blogs: Scrape configured URLs and extract full article content (not just metadata).
2. Storage
   - Normalize into Source and Article records.
   - Keep raw metadata and canonical URLs.
3. Summarization
   - Collect new articles for the last 24 hours.
   - Use OpenAI with an agent system prompt to create short, insight-guided summaries.
4. Digest
   - Produce a compact list of snippets with links to originals.
5. Delivery
   - Email digest to a configured address.

## Data Model (Current)
- YoutubeChannel
  - id
  - channel_input (unique)
  - active
  - created_at
  - updated_at
- Article
  - id
  - source_type (`youtube`, `openai`, `anthropic`)
  - source
  - title
  - url (unique)
  - video_id (unique with `source_type` for YouTube)
  - published_at
  - summary
  - raw_content (markdown or transcript)
  - content_type (`markdown` or `transcript`)
  - content_fetched_at
  - content_error
  - created_at
- DigestItem
  - id
  - article_id (foreign key to `articles.id`, unique)
  - article_url
  - digest_title
  - digest_summary (2-3 sentences)
  - model
  - created_at
  - updated_at

## Project Structure
- app/
  - __init__.py
  - agent/
    - __init__.py
    - digest_instructions.txt
  - db/
    - __init__.py
    - base.py
    - models.py
    - crud.py
    - create_tables.py
  - models.py
  - digest/
    - __init__.py
    - process.py
  - ingest/
    - youtube.py
    - openai.py
    - anthropic.py
    - pipeline.py
    - enrich.py
  - summarize/
    - llm.py
  - scheduler/
    - daily.py
- scripts/
  - run_ingest.py
  - run_openai_surface.py
  - run_anthropic_surface.py
  - run_youtube_surface.py
  - run_enrich.py
  - run_process_digest.py
- docker/
  - docker-compose.yml
  - example.environment.env
- README.md

## Environment Variables
- DATABASE_URL
- OPENAI_API_KEY
- LLM_MODEL
- AGENT_PROMPT_PATH
- EMAIL_HOST
- EMAIL_PORT
- EMAIL_USERNAME
- EMAIL_PASSWORD
- EMAIL_FROM
- DIGEST_RECIPIENT
- TIMEZONE

Practical note:
- Python scripts in this project currently read env vars from the active shell.
- If you keep keys in `.env`, load them into your shell/session before running scripts.

## Local Database Setup
Start Postgres with Docker:
```bash
docker compose -f docker/docker-compose.yml up -d
```

Example env values (see `docker/example.environment.env`):
```bash
POSTGRES_USER=news_user
POSTGRES_PASSWORD=news_pass
POSTGRES_DB=news_aggregator
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg2://news_user:news_pass@localhost:5432/news_aggregator
```

Create tables:
```bash
uv run python -m app.db.create_tables
```

Beekeeper Studio connection values:
- Type: PostgreSQL
- Host: `localhost`
- Port: `5432`
- Database: `news_aggregator`
- Username: `news_user`
- Password: `news_pass`
- SSL: Off for local dev

Important:
- In Beekeeper, do not put `postgresql+psycopg2://...` in the database field.
- If using URL mode in Beekeeper, use `postgresql://...` (without `+psycopg2`).

## YouTube Surface Prototype
- Script: `scripts/run_youtube_surface.py`
- Core module: `app/ingest/youtube.py`
- Channel list file: `app/ingest/channels.txt`
- Supported channel inputs:
  - Channel ID (`UC...`)
  - Channel URL (`https://www.youtube.com/channel/UC...`)
  - Handle URL (`https://www.youtube.com/@handle`)
  - Handle (`@handle`)
- Core behavior:
  - Resolves channel ID from provided input.
  - Reads channel RSS feed.
  - Filters videos by lookback window (default 24 hours).
  - Optionally fetches transcript text per video.

Example run:
```bash
uv run python scripts/run_youtube_surface.py --channels "@OpenAI" --hours 24
```

If transcripts are enabled, install:
```bash
uv pip install youtube-transcript-api
```

## Example Sources (Testing)
- `https://openai.com/news/`
- `https://www.anthropic.com/engineering`
- `https://www.anthropic.com/research`

## OpenAI News RSS Prototype
- Script: `scripts/run_openai_surface.py`
- Core module: `app/ingest/openai.py`
- Default RSS: `https://openai.com/news/rss.xml`
- Core behavior:
  - Parses OpenAI RSS entries into a Pydantic model.
  - Returns structured articles and filters by publish time window.
  - Supports optional max article cap.

Example run:
```bash
uv run python scripts/run_openai_surface.py --hours 48 --max-articles 10
```

## Anthropic RSS Prototype
- Script: `scripts/run_anthropic_surface.py`
- Core module: `app/ingest/anthropic.py`
- Feeds:
  - `https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml`
  - `https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml`
  - `https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml`
- Core behavior:
  - Parses all three feeds into a Pydantic model.
  - Returns structured articles and filters by publish time window.
  - Supports optional per-feed max cap.

Example run:
```bash
uv run python scripts/run_anthropic_surface.py --hours 240 --max-per-feed 5
```

## Ingestion Pipeline
- Runner: `scripts/run_ingest.py`
- Orchestrates:
  - YouTube (from `youtube_channels` table)
  - OpenAI RSS
  - Anthropic RSS
- Stores all items in PostgreSQL tables (`youtube_channels`, `articles`).

Example run:
```bash
uv run python scripts/run_ingest.py --hours 24
```

Optional full content fetch:
```bash
uv run python scripts/run_ingest.py --hours 24 --fetch-markdown
```

Seed a YouTube channel:
```sql
INSERT INTO youtube_channels (channel_input, active)
VALUES ('@OpenAI', true);
```

If you created tables before adding YouTube video IDs, apply this once:
```sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS video_id VARCHAR(32);
CREATE UNIQUE INDEX IF NOT EXISTS uq_articles_source_video
  ON articles (source_type, video_id);
```

## Stage 2 Enrichment
Backfill missing content into `articles.raw_content`:
```bash
uv run python scripts/run_enrich.py --hours 240 --max-items 50
```

Apply schema changes (if tables already exist):
```sql
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_type VARCHAR(32);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_fetched_at TIMESTAMPTZ;
ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_error TEXT;
```

Notes:
- OpenAI + Anthropic use Docling to export markdown.
- YouTube uses the transcript API and stores the transcript in `raw_content`.
- `content_error` and `content_fetched_at` track failures and attempts.

YouTube rate limiting safeguards:
- Small delay and jitter between transcript requests.
- Detects IP blocks and pauses YouTube enrichment for 6 hours.
- Requires a small state table:
```sql
CREATE TABLE IF NOT EXISTS pipeline_state (
  key VARCHAR(100) PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

TODO (later):
- Add Webshare proxy support for YouTube transcript requests to reduce IP-block/rate-limit failures during enrichment.

## Stage 3 Digest Processing
Generate digest items from all articles that do not yet have a digest row:
```bash
uv run python scripts/run_process_digest.py --max-items 100
```

Model and API:
- Uses OpenAI Responses API.
- Default model: `gpt-5.1-instant`.
- Uses structured text output (`json_schema`) with fields:
  - `digest_title`
  - `digest_summary`

Agent prompt:
- File: `app/agent/digest_instructions.txt`
- Defines role/context and output quality rules for digest generation.

Digest table creation (if table is missing in an already-running database):
```sql
CREATE TABLE IF NOT EXISTS digest_items (
  id SERIAL PRIMARY KEY,
  article_id INTEGER NOT NULL UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
  article_url VARCHAR(1024) NOT NULL,
  digest_title VARCHAR(512) NOT NULL,
  digest_summary TEXT NOT NULL,
  model VARCHAR(100) NOT NULL DEFAULT 'gpt-5.1-instant',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Verification:
- The digest table name is `digest_items` (not `digests`).

## Scheduling
- Run ingestion + digest every 24 hours.
- In production on Render, use a scheduled job (cron) to execute the daily pipeline.
- TODO (later): add an explicit cron job configuration for `run_ingest.py`, `run_enrich.py`, and `run_process_digest.py`.

## Deployment Notes (Render)
- Use a single web service or worker depending on architecture.
- Keep configuration in environment variables.
- Use a scheduled job for the daily digest run.
- Docker setup should include a local PostgreSQL container (no external DB dependency).

## Next Milestones
1. Create SQLAlchemy models and initial DB bootstrap.
2. Implement RSS ingestion for YouTube channels.
3. Implement blog scraping ingestion.
4. Add LLM summary and digest formatting.
5. Add email delivery.
6. Add scheduler entrypoint for daily runs.
