# AI News Aggregator

A Python backend application that collects AI-related news from RSS feeds, YouTube channels, and AI company blogs. The system stores structured content in PostgreSQL, generates LLM-based summaries, ranks the most relevant items, and sends a daily email digest.

<img width="581" height="816" alt="image" src="https://github.com/user-attachments/assets/99bd9c72-1563-4e4f-8999-4ca814a96343" />



## Why I Built This

The goal was to build an automated backend pipeline that monitors several AI-related sources, extracts useful information, summarizes it with an LLM, and delivers a concise daily digest.

This project focuses on backend architecture, data modeling, automation, structured LLM output, and reliable processing of external content sources.

## Features

- Ingests YouTube channel updates via RSS
- Parses OpenAI and Anthropic news/research feeds
- Stores normalized article data in PostgreSQL
- Enriches articles with markdown content or YouTube transcripts
- Generates short summaries using the OpenAI API
- Ranks digest items based on relevance
- Sends a daily digest via SMTP email
- Designed to run as a scheduled backend job

## Tech Stack

- Python
- PostgreSQL
- SQLAlchemy
- Pydantic
- OpenAI API
- SMTP email delivery
- Docker for local PostgreSQL
- Scheduled job architecture

## Architecture

```txt
Sources
  ├── YouTube RSS
  ├── OpenAI RSS
  └── Anthropic RSS
        ↓
Ingestion Pipeline
        ↓
PostgreSQL
        ↓
Content Enrichment
        ↓
LLM Summarization
        ↓
Ranking
        ↓
Email Digest

