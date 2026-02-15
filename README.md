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
    - assignment_editor_instructions.txt
    - email_editor_instructions.txt
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
    - rank.py
    - email.py
  - email/
    - __init__.py
    - render.py
    - send.py
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
  - run_rank_digest.py
  - run_email_digest.py
  - run_send_digest_email.py
  - run_daily_pipeline.py
- docker/
  - docker-compose.yml
  - example.environment.env
- render.yaml
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
- EMAIL_USE_TLS
- DIGEST_RECIPIENT
- DIGEST_RECIPIENT_NAME
- DIGEST_MODEL
- RANK_MODEL
- EMAIL_MODEL
- TIMEZONE

Practical note:
- Python scripts in this project currently read env vars from the active shell.
- If you keep keys in `.env`, load them into your shell/session before running scripts.
- With `uv`, use `--env-file .env` to load both `DATABASE_URL` and `OPENAI_API_KEY`.

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

Recommended run command with `.env` loading:
```bash
uv run --env-file .env python scripts/run_process_digest.py --max-items 100
```

Model and API:
- Uses OpenAI Responses API.
- Default model: `gpt-5.1` (override via `--model` or `DIGEST_MODEL` env var).
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
  model VARCHAR(100) NOT NULL DEFAULT 'gpt-5.1',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

Verification:
- The digest table name is `digest_items` (not `digests`).
- If Beekeeper table view looks stale, run:
```sql
SELECT COUNT(*) FROM public.digest_items;
SELECT id, article_id, digest_title, created_at
FROM public.digest_items
ORDER BY created_at DESC
LIMIT 20;
```

Common digest processing errors:
- `model_not_found`: use `--model gpt-5.1` (or another model available to your account).
- `insufficient_quota`: add billing/quota in OpenAI before re-running.

## Stage 4 Digest Ranking (Aggregator)
Ranking agent name:
- `Assignment Editor` (news-desk style ranking/orchestration role).

What it does:
- Takes digest items from the last 24 hours.
- Uses a default user profile (`AI Product and Engineering Lead`) with role, interests, and priorities.
- Calls OpenAI Responses API to score and rank items.
- Returns a strongly-typed ranked list via Pydantic models.

Runner:
```bash
uv run --env-file .env python scripts/run_rank_digest.py --hours 24 --max-items 100
```

Output model:
- `DigestRankingResultModel`
  - `profile_name`
  - `model`
  - `generated_at`
  - `ranked_items[]`

Each ranked item includes:
- `rank`
- `digest_item_id`
- `article_id`
- `article_url`
- `source_type`
- `digest_title`
- `digest_summary`
- `score` (0-100)
- `reason`

Agent prompt file:
- `app/agent/assignment_editor_instructions.txt`

## Stage 5 Email Composition and Delivery
This stage converts ranked digest results into a normal email (not JSON) and sends it via SMTP.

Email composition runner (builds subject + greeting + introduction + top items, returns JSON payload):
```bash
uv run --env-file .env python scripts/run_email_digest.py --hours 24 --max-items 100 --top-n 10 --recipient-name Dave
```

Email send runner (builds + sends human-readable email):
```bash
uv run --env-file .env python scripts/run_send_digest_email.py --hours 24 --max-items 100 --top-n 10 --recipient-name Dave
```

Dry run (preview subject/body without sending):
```bash
uv run --env-file .env python scripts/run_send_digest_email.py --dry-run --top-n 10 --recipient-name Dave
```

SMTP settings used:
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USERNAME`
- `EMAIL_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_USE_TLS`
- `DIGEST_RECIPIENT`

Notes:
- Email payload is typed via Pydantic (`DailyDigestEmailModel`) and includes `subject`, `greeting`, `introduction`, and ranked items.
- Plain text body is rendered as markdown with sections/headers; HTML alternative is attached by default.
- Use `--text-only` to send plain text only.

## Daily End-to-End Runner
Single command that runs all stages in order:
1. ingest
2. enrich
3. digest processing
4. build + send newsletter email

Run locally:
```bash
uv run --env-file .env python scripts/run_daily_pipeline.py --hours 24 --max-items 100 --top-n 10
```

Useful args:
- `--hours` (default `24`)
- `--max-items` (default `100`)
- `--top-n` (default `10`)
- `--recipient-name` (default from `DIGEST_RECIPIENT_NAME`, else `Dave`)

## Scheduling
- Run the daily pipeline every 24 hours using `scripts/run_daily_pipeline.py`.
- In production, Render Cron triggers this command once daily with `--hours 24`.

## Deployment Notes (Render)
- This repository includes a Render Blueprint file: `render.yaml`.
- Production setup uses:
  - Render Managed Postgres (`news-aggregator-db`)
  - Render Cron Job (`news-aggregator-daily`)
- Cron command:
  - `python scripts/run_daily_pipeline.py --hours 24 --max-items 100 --top-n 10`
- Schedule in blueprint:
  - `0 08 * * *` (UTC, once daily)

### Deploy Steps (Render)
1. Push branch to GitHub.
2. In Render, create a Blueprint service from this repo (`render.yaml`).
3. Set secret env vars in Render for:
   - `OPENAI_API_KEY`
   - `EMAIL_HOST`
   - `EMAIL_USERNAME`
   - `EMAIL_PASSWORD`
   - `EMAIL_FROM`
   - `DIGEST_RECIPIENT`
4. Verify non-secret defaults:
   - `EMAIL_PORT=587`
   - `EMAIL_USE_TLS=true`
   - `DIGEST_RECIPIENT_NAME=Dave` (or your preferred name)
   - `DIGEST_MODEL=gpt-5.1`
   - `RANK_MODEL=gpt-5.1`
   - `EMAIL_MODEL=gpt-5.1`

### First-Run Bootstrap
1. Trigger the cron job manually once from Render.
   - `init_db()` in the pipeline will create tables if they do not exist.
2. Seed at least one YouTube channel in production DB:
```sql
INSERT INTO youtube_channels (channel_input, active)
VALUES ('UCawZsQWqfGSbCI5yjkdVkTA', true);
```
3. Trigger the cron job again and verify:
   - new/updated rows in `articles`
   - rows in `digest_items`
   - digest email received by `DIGEST_RECIPIENT`

## Next Milestones
1. Create SQLAlchemy models and initial DB bootstrap.
2. Implement RSS ingestion for YouTube channels.
3. Implement blog scraping ingestion.
4. Add LLM summary and digest formatting.
5. Add email delivery.
6. Add scheduler entrypoint for daily runs.
