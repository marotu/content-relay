# Content-Relay

Asynchronous article relay pipeline for scraping, rewriting, and publishing content.

## Stack

- Python 3.11+
- Playwright for article scraping
- OpenAI Python SDK for rewriting and Telegram post generation
- aiogram 3.x for Telegram bot commands
- Pydantic v2 + pydantic-settings for configuration
- Loguru for structured logging
- PyYAML for prompt catalog loading

## Project layout

- `core/` — settings, domain models, exceptions, prompt catalog
- `scrapers/` — Playwright scraper implementation
- `services/` — OpenAI service and pipeline orchestration
- `handlers/` — Telegram publisher and aiogram router
- `main.py` — application entrypoint

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:

   ```bash
   playwright install
   ```

4. Copy `.env.example` to `.env` and fill in the values.

## Environment variables

The application reads configuration from `.env` via Pydantic settings.

Required variables:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional variables:

- `OPENAI_MODEL`
- `OPENAI_TEMPERATURE`
- `OPENAI_MAX_TOKENS`
- `OPENAI_REQUEST_TIMEOUT_SECONDS`
- `OPENAI_MAX_RETRIES`
- `SOURCE_URLS`
- `TELEGRAM_PARSE_MODE`
- `TELEGRAM_ADMIN_IDS`
- `POLL_INTERVAL_SECONDS`
- `SCRAPER_TIMEOUT_SECONDS`
- `SCRAPER_MAX_RETRIES`
- `BROWSER_HEADLESS`
- `BROWSER_LOCALE`
- `BROWSER_TIMEZONE`
- `BROWSER_USER_AGENT`
- `MAX_CONCURRENCY`
- `DATA_DIR`
- `LOG_DIR`

## Runtime flow

1. `main.py` loads settings and configures Loguru.
2. `services/pipeline.py` runs the scraping and publication loop.
3. `scrapers/playwright_scraper.py` extracts article metadata and body text.
4. `services/openai_service.py` loads prompts from `core/prompts.yaml`, rewrites the article, and builds the Telegram draft.
5. `handlers/publisher.py` sends the final post to the configured Telegram chat.
6. `handlers/router.py` exposes aiogram commands for manual publishing and status checks.

## Notes

- Prompts are not hardcoded; they are stored in `core/prompts.yaml`.
- The scraper uses a dedicated browser context with reduced automation fingerprints.
- OpenAI requests use retry logic for rate limits and network timeouts.
- Telegram publishing raises domain-specific exceptions for API and transport failures.
