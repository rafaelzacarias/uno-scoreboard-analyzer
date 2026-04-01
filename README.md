# uno-scoreboard-analyzer

Real-time handball game analyzer that monitors a [overlays.uno](https://app.overlays.uno) scoreboard output URL, detects score and time changes, and uses an LLM (OpenAI) to deliver live commentary and insights.

## Features

- 📡 **Real-time monitoring** – polls the scoreboard URL at a configurable interval
- 🔍 **Change detection** – only acts when the score, clock, or team names change
- 💡 **LLM insights** – calls OpenAI ChatGPT to generate concise, broadcast-style handball commentary
- 🕹️ **Simple CLI** – one command to start, `Ctrl+C` to stop

## Requirements

- Python 3.10+
- An [OpenAI API key](https://platform.openai.com/api-keys)

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/rafaelzacarias/uno-scoreboard-analyzer.git
cd uno-scoreboard-analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure your API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Usage

```bash
python main.py <scoreboard_url>
```

**Example:**

```bash
python main.py https://app.overlays.uno/output/0ZtIYoE5lp1X1rceb5MV5s
```

**Sample output:**

```
🏁 Monitoring scoreboard: https://app.overlays.uno/output/0ZtIYoE5lp1X1rceb5MV5s
   Poll interval : 10s
   Model         : gpt-4o-mini
   Press Ctrl+C to stop.

[14:32:05] 📊 Lions 0 x 0 Eagles | Time: 00:00
   ↳ Initial scoreboard: Lions 0 x 0 Eagles | Time: 00:00

💡 Insight: The match is just getting underway between Lions and Eagles with the
   score tied at 0-0. Both teams will be looking to establish dominance in the
   opening minutes.

[14:35:12] 📊 Lions 1 x 0 Eagles | Time: 05:10
   ↳ Score update: Lions 1 x 0 Eagles (was 0 x 0)

💡 Insight: Lions break the deadlock early! A 1-0 lead at the five-minute mark
   gives them a psychological edge, but it's far too early to call this one.
```

## Configuration

All options can be set in a `.env` file (copy from `.env.example`):

| Variable         | Default      | Description                              |
|------------------|--------------|------------------------------------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key                      |
| `OPENAI_MODEL`   | `gpt-4o-mini`| Model used for generating insights       |
| `POLL_INTERVAL`  | `10`         | Seconds between scoreboard checks        |
| `REQUEST_TIMEOUT`| `15`         | HTTP request timeout in seconds          |

## Project structure

```
uno-scoreboard-analyzer/
├── main.py          # Entry point & monitoring loop
├── scraper.py       # Fetches & parses the overlay page
├── analyzer.py      # Builds prompts and calls the OpenAI API
├── requirements.txt
├── .env.example
└── tests/
    ├── test_scraper.py
    └── test_analyzer.py
```

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## How it works

1. **Fetch** – `scraper.fetch_scoreboard()` downloads the overlay page HTML and extracts home/away team names, scores, and the game clock using CSS selectors.
2. **Detect** – `scraper.detect_changes()` compares the new state against the previous one and produces a list of human-readable change descriptions.
3. **Analyse** – `analyzer.get_insight()` sends the current state and changes to the OpenAI Chat API, which responds with short handball commentary.
4. **Loop** – steps 1–3 repeat every `POLL_INTERVAL` seconds until the user presses `Ctrl+C`.
