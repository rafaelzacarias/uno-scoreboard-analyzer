# uno-scoreboard-analyzer

Real-time handball game analyzer that monitors a [overlays.uno](https://app.overlays.uno) scoreboard output URL, detects score and time changes, and uses an LLM (OpenAI or Azure OpenAI) to deliver live commentary and insights.

## Deploy to Azure (one click)

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Frafaelzacarias%2Funo-scoreboard-analyzer%2Fmain%2Fazuredeploy.json)

> **What gets deployed:**
>
> | Resource | Purpose |
> |----------|---------|
> | **Azure OpenAI** (Cognitive Services) | Hosts a `gpt-4o-mini` model deployment so you don't need an external OpenAI key |
> | **Azure Container Instance** | Runs the scoreboard analyzer + live web dashboard on port 8080 |
>
> **Parameters you need to set:**
>
> | Parameter | Description |
> |-----------|-------------|
> | `scoreboardUrl` | Your overlays.uno scoreboard output URL |
> | `openaiApiKey` | *(optional)* Your own OpenAI API key. Leave blank to use the Azure OpenAI resource created by the template |
>
> The default region is **West US 2** (near Redmond, WA). After deployment, the output `dashboardUrl` gives you the live web dashboard.

## Features

- 📡 **Real-time monitoring** – polls the scoreboard URL at a configurable interval
- 🔍 **Change detection** – only acts when the score, clock, or team names change
- 💡 **LLM insights** – calls OpenAI / Azure OpenAI to generate concise, broadcast-style handball commentary
- 🔄 **Multi-game support** – automatically detects scoreboard resets and starts a new game log
- 🌐 **Live web dashboard** – auto-refreshing browser page showing all events, filterable by type or game
- ☁️ **One-click Azure deploy** – ARM template provisions everything (Azure OpenAI model + container)
- 🕹️ **Simple CLI** – one command to start, `Ctrl+C` to stop

## Requirements

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys) **or** Azure OpenAI credentials

## Quick start (local)

```bash
# 1. Clone the repository
git clone https://github.com/rafaelzacarias/uno-scoreboard-analyzer.git
cd uno-scoreboard-analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env – set SCOREBOARD_URL and OPENAI_API_KEY (or Azure OpenAI vars)
```

### CLI mode (stdout only)

```bash
python main.py <scoreboard_url>
```

### Web dashboard mode

```bash
python app.py
# or
SCOREBOARD_URL=https://app.overlays.uno/output/abc123 python app.py
```

Open `http://localhost:8080` to see the live dashboard.

### Docker

```bash
docker build -t uno-analyzer .
docker run -p 8080:8080 \
  -e SCOREBOARD_URL=https://app.overlays.uno/output/abc123 \
  -e OPENAI_API_KEY=sk-... \
  uno-analyzer
```

## Configuration

All options can be set in a `.env` file (copy from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SCOREBOARD_URL` | *(required for `app.py`)* | overlays.uno output URL |
| `OPENAI_API_KEY` | | Your OpenAI API key (option A) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model used for generating insights |
| `AZURE_OPENAI_ENDPOINT` | | Azure OpenAI endpoint (option B – takes priority) |
| `AZURE_OPENAI_KEY` | | Azure OpenAI key |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o-mini` | Azure OpenAI deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` | Azure OpenAI API version |
| `POLL_INTERVAL` | `10` | Seconds between scoreboard checks |
| `REQUEST_TIMEOUT` | `15` | HTTP request timeout in seconds |
| `WEB_PORT` | `8080` | Port for the web dashboard |

## Project structure

```
uno-scoreboard-analyzer/
├── app.py             # Combined entry point (analyzer loop + web server)
├── main.py            # CLI-only entry point
├── scraper.py         # Fetches & parses the overlay page
├── analyzer.py        # Builds prompts and calls the OpenAI API
├── game_log.py        # Thread-safe in-memory event log
├── web_app.py         # Flask web dashboard
├── templates/
│   └── index.html     # Live dashboard page
├── Dockerfile
├── azuredeploy.json   # Azure ARM template (one-click deploy)
├── requirements.txt
├── .env.example
└── tests/
    ├── test_scraper.py
    ├── test_analyzer.py
    ├── test_game_log.py
    ├── test_app.py
    └── test_web_app.py
```

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## How it works

1. **Fetch** – `scraper.fetch_scoreboard()` downloads the overlay page HTML and extracts home/away team names, scores, and the game clock using CSS selectors.
2. **Detect** – `scraper.detect_changes()` compares the new state against the previous one and produces a list of human-readable change descriptions.
3. **Reset detection** – when both scores drop to zero after a game was in progress, the analyzer starts a new game in the log.
4. **Analyse** – `analyzer.get_insight()` sends the current state and changes to OpenAI (or Azure OpenAI), which responds with short handball commentary.
5. **Log** – every event is stored in a thread-safe `GameLog` with timestamps, event types, and game numbers.
6. **Dashboard** – a Flask web server exposes the log via a REST API and an auto-refreshing HTML page.
7. **Loop** – steps 1–6 repeat every `POLL_INTERVAL` seconds.
