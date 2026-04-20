# job-agent

A personal career-advisor CLI agent. It reads your CV from Notion, keeps a living career profile, searches the German Federal Employment Agency (Bundesagentur für Arbeit) job board, and evaluates postings against your profile — all from a terminal chat.

The agent is powered by Claude (Anthropic) and talks to two MCP servers:

- a local **job-listings** server that queries the public Arbeitsagentur API
- the **Notion MCP server** (`@notionhq/notion-mcp-server`) that reads and writes your CV and profile pages

> The agent itself replies in **German** (its system prompt is in German), but the code and this guide are in English.

---

## Prerequisites

You'll need the following installed locally:

- **Python 3.13** (pinned via `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **Node.js 18+ and npm** (provides `npx`, which launches the Notion MCP server)
- An **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com/)
- A **Notion account** with a workspace you can create pages in

### Installing uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

More options: [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/).

### Installing Node.js (for `npx`)

Pick one of the following:

**macOS (Homebrew)**

```bash
brew install node
```

**macOS / Linux — nvm (recommended if you juggle Node versions)**

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
# restart your shell, then:
nvm install --lts
nvm use --lts
```

**Windows**

Download the LTS installer from [nodejs.org](https://nodejs.org/) and run it. `npx` ships with npm and is available automatically.

**Verify**

```bash
node --version   # should print v18.x or higher
npx --version
```

No separate install step is needed for `@notionhq/notion-mcp-server` — `npx -y` fetches it on first run.

---

## 1. Set up Notion (do this first)

### 1a. Create the pages

Inside your Notion workspace, create the following structure **before the first run** — the agent expects it to exist:

```
Job Agent           ← parent page (top-level)
└── CV              ← sub-page, must be filled with your actual CV
```

Requirements:

- The parent page must be named exactly **`Job Agent`**.
- The sub-page must be named exactly **`CV`** and contain your real CV content (work history, skills, education, etc.). **A blank CV will not work** — the agent reads it to seed your profile and to evaluate job fit.
- You do **not** need to create a `Profil` page yourself — the agent creates and maintains it on the first run.

### 1b. Create a Notion integration

1. Go to [notion.so/profile/integrations](https://www.notion.so/profile/integrations).
2. Click **New integration**, give it a name (e.g. `job-agent`), and pick the workspace that holds your `Job Agent` page.
3. Under **Capabilities**, grant at least: Read content, Update content, Insert content.
4. Copy the **Internal Integration Secret** (starts with `ntn_…`). You'll put this in `.env` as `NOTION_TOKEN`.

### 1c. Share the page with the integration

Integrations can only see pages that have been explicitly shared with them.

1. Open the `Job Agent` page in Notion.
2. Click **`…`** (top-right) → **Connections** → **Connect to** → pick your integration.
3. Sharing the parent propagates access to `CV` and to `Profil` (once created).

---

## 2. Clone and install

```bash
git clone <this-repo-url>
cd job-agent
uv sync
```

`uv sync` creates a virtualenv at `.venv/` and installs all pinned dependencies from `uv.lock`.

---

## 3. Configure environment variables

Create a `.env` file in the project root:

```bash
ANTHROPIC_API_KEY="sk-ant-..."
NOTION_TOKEN="ntn_..."
```

- `ANTHROPIC_API_KEY`: from [console.anthropic.com](https://console.anthropic.com/).
- `NOTION_TOKEN`: the integration secret from step 1b.

`.env` is gitignored — do not commit it.

---

## 4. Run

```bash
uv run python main.py
```

You'll be dropped into a chat prompt.

### Controls

- **Enter** inserts a newline (useful for pasting job descriptions).
- **Alt+Enter** (or **Esc, then Enter** on macOS) sends the message.
- **`quit`** ends the session, as does **Ctrl+D** or **Ctrl+C**.

While the agent is working, a spinner shows what it's currently doing (`Denke nach…`, `Rufe <tool> auf…`), so you can tell it hasn't hung.

### What happens on first run

1. The agent checks for a `Profil` sub-page under `Job Agent`.
2. Not finding one, it reads your `CV` and runs a short structured interview (max 5 questions per round) about desired roles, industry, work model, salary expectations, and development goals.
3. It creates the `Profil` page in Notion from your answers.
4. On subsequent runs it reads the existing profile and keeps refining it as you chat.

From there you can ask it to search for jobs, paste a posting for evaluation, or iterate on your profile.

---

## Project layout

```
agent/           # Agent class: owns the Claude API loop + tool dispatch
mcp_client/      # Thin async MCP client wrapper used by the agent
mcp_servers/     # Local MCP servers (currently: Arbeitsagentur job search)
system_prompt.py # The German system prompt that defines the agent's role
main.py          # Entry point: wires clients, starts the chat loop
```

---

## Roadmap

Planned in rough order. Each phase is independently shippable.

**Phase 1 — Polish**
- Stream Claude responses (faster feel, unlocks longer outputs)
- Prompt caching on system prompt + CV
- Persist conversations to disk
- Structured tool-call logging to a file

**Phase 2 — Jobs as first-class data**
- Promote jobs to a Notion `Jobs` database (Title, Company, RefNr, Score, Status, Notes)
- Replace the free-form `Profil` page with a structured schema (target roles, locations, salary, dealbreakers)

**Phase 3 — Richer evaluation**
- Tailored cover-letter drafting into Notion
- Gap-closing plans written as Notion tasks with deadlines

**Phase 4 — More sources & automation**
- Additional job boards as extra MCP servers (StepStone, LinkedIn, Xing)
- Scheduled runs that append high-scoring new matches to Notion
- Notifications (Slack / Telegram / email) on new matches

**Phase 5 — Surface**
- Textual TUI or lightweight FastAPI web UI
- Dockerized deploy

---

## Troubleshooting

- **`ValueError: Streaming is required…`** — `max_tokens` in [agent/agent.py](agent/agent.py) is too high for non-streaming. Keep it at `8192` or switch the API call to streaming.
- **`NOTION_TOKEN` KeyError on startup** — `.env` is missing or not being loaded. Confirm it's in the project root.
- **Notion tool calls fail with "unauthorized"** — the integration wasn't connected to the `Job Agent` page (step 1c).
- **`npx: command not found`** — Node.js isn't installed or not on your `PATH`. See the Node install section above.
- **Agent can't find the CV** — make sure the page is named exactly `CV`, nested directly under `Job Agent`, and has content.
