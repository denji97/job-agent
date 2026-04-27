# job-agent

A personal career-advisor CLI agent. It reads your CV from Notion, keeps a living career profile, searches the German Federal Employment Agency (Bundesagentur für Arbeit) job board, and evaluates postings against your profile — all from a terminal chat.

The agent runs against a **local LLM via [Ollama](https://ollama.com)** and talks to two MCP servers:

- a local **job-listings** server that queries the public Arbeitsagentur API
- the **Notion MCP server** (`@notionhq/notion-mcp-server`) that reads and writes your CV and profile pages

> The agent itself replies in **German** (its system prompt is in German), but the code and this guide are in English.

You can run the agent two ways: **directly with `uv`** (fewest moving parts, native performance) or **via Docker** (containerized, reproducible). Both share the same `.env` and rely on Ollama running on your host.

---

## Prerequisites

- **[Ollama](https://ollama.com)** — runs the LLM with native GPU acceleration where available (Metal on Apple Silicon, CUDA on NVIDIA, ROCm on AMD).
- A **Notion account** with a workspace you can create pages in.

For the **uv** workflow, also install:

- **Python 3.13** (pinned via `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **Node.js 18+ and npm** (provides `npx`, which launches the Notion MCP server)

For the **Docker** workflow, only **Docker** (Desktop, Engine, or any compatible runtime) is required — Python, Node, and `npx` are baked into the image.

### Installing Ollama and a model

Install Ollama from [ollama.com](https://ollama.com) (one-click installers for macOS, Windows, and Linux), then pull a model that supports tool calling:

```bash
ollama pull gemma4:e4b      # ~5 GB, runs comfortably on 16 GB RAM
ollama pull gemma4:26b      # ~17 GB, much smarter
ollama pull qwen2.5:14b     # alternative, strong tool-calling
```

Make sure Ollama is running (`ollama serve` from a terminal, or just leave the system-tray app open) — the agent talks to it on `http://localhost:11434`.

### Installing uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

More options: [docs.astral.sh/uv/getting-started/installation](https://docs.astral.sh/uv/getting-started/installation/).

### Installing Node.js (for the uv workflow)

Pick one:

- **Official installer** — [nodejs.org](https://nodejs.org/) (Windows, macOS, Linux).
- **Package manager** — `brew install node` (macOS), `apt install nodejs npm` (Debian/Ubuntu), `dnf install nodejs npm` (Fedora), `pacman -S nodejs npm` (Arch).
- **nvm** — `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash`, then `nvm install --lts`.

Verify:

```bash
node --version   # v18.x or higher
npx --version
```

`npx -y @notionhq/notion-mcp-server` fetches the MCP server on first run — no separate install.

---

## 1. Set up Notion (do this first, regardless of how you run the agent)

### 1a. Create the pages

```
Job Agent           ← parent page (top-level)
└── CV              ← sub-page, must be filled with your actual CV
```

- The parent must be named exactly **`Job Agent`**.
- The `CV` sub-page must contain your real CV content. **A blank CV will not work** — the agent reads it to seed your profile and to evaluate job fit.
- Do **not** create a `Profil` page yourself — the agent creates and maintains it on the first run.

### 1b. Create a Notion integration

1. Go to [notion.so/profile/integrations](https://www.notion.so/profile/integrations).
2. Click **New integration**, name it (e.g. `job-agent`), pick the workspace with your `Job Agent` page.
3. Under **Capabilities**, grant at least: Read content, Update content, Insert content.
4. Copy the **Internal Integration Secret** (starts with `ntn_…`). You'll put this in `.env` as `NOTION_TOKEN`.

### 1c. Share the page with the integration

1. Open the `Job Agent` page in Notion.
2. Click **`…`** (top-right) → **Connections** → **Connect to** → pick your integration.
3. Sharing the parent propagates access to `CV` and to `Profil` (once created).

---

## 2. Configure `.env`

Create a `.env` file in the project root. Copy from `.env.example`:

```bash
NOTION_TOKEN=ntn_...
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=gemma4:e4b
SYSTEM_PROMPT=implicit
```

**Variable reference:**

| Variable          | Required | Default                     | Description                                                                                                  |
| ----------------- | -------- | --------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `NOTION_TOKEN`    | yes      | —                           | Internal Integration Secret from Notion (step 1b).                                                           |
| `OLLAMA_BASE_URL` | no       | `http://localhost:11434/v1` | Where Ollama is reachable. See the Docker section for the value to use when running in a container.          |
| `OLLAMA_MODEL`    | no       | `gemma4:e4b`                | Which Ollama model to use. Must already be `ollama pull`ed on the host.                                      |
| `SYSTEM_PROMPT`   | no       | `implicit`                  | Which prompt variant. See [Choosing a system prompt](#choosing-a-system-prompt) below.                       |

> **Important:** No quotes around values in `.env`. Docker's `--env-file` passes quotes through literally and breaks parsing.
>
> **Never commit `.env`.** It's gitignored.

---

## Choosing a system prompt

The repo ships **two prompt variants**. They give the agent the same persona, but differ in *how much detail they give the model about tool use*. Picking the right one matters more than picking the right model.

### `implicit` (default)

A short prompt. Tells the model what its role is, what tools exist conceptually, and what the workflows look like — but **does not** spell out which Notion API call to make for each step. The model is expected to figure out the multi-step pattern (search a page → grab its ID → fetch its blocks) on its own.

**Use this when:** you're running a capable model (≥14B parameters, well-trained on tool use) like `gemma4:26b`, `qwen2.5:14b`, or anything Sonnet-class. Output is shorter and more natural; the model decides when to call tools instead of running through a checklist.

### `explicit`

The same prompt **plus a hard-coded Notion playbook** that names exact tool calls and their parameter shapes. It tells the model: "to read page X, call `API-post-search` with this body, then `API-get-block-children` with the resulting `id`. Do not invent steps."

**Use this when:** you're running a smaller model (`gemma4:e4b`, anything ≤ ~8B) that struggles with multi-step tool planning. Without the playbook, smaller models often:
- Answer from prior context instead of reading Notion ("hallucinate" who you are).
- Call only the first search step and never drill into the page.
- Pass malformed parameters (e.g. `filter` without `property`) and get 400s.

The explicit prompt also tells the model to **omit the optional Notion search `filter`** entirely — small models tend to half-fill it, which Notion rejects.

### Quick guide

| Model                                | Recommended prompt                                  | Why                                                              |
| ------------------------------------ | --------------------------------------------------- | ---------------------------------------------------------------- |
| `gemma4:e4b` (~8B effective)         | **`explicit`**                                      | Needs the playbook, often skips multi-step tool calls otherwise. |
| `qwen2.5:7b` / `llama3.1:8b`         | **`explicit`** to start; try `implicit` if it works | Borderline; depends on the task.                                 |
| `gemma4:26b` / `qwen2.5:14b` (or up) | **`implicit`**                                      | Capable enough to plan from short instructions.                  |
| Anything Sonnet-/GPT-4-class         | `implicit`                                          | The playbook is unnecessary here.                                |

You can switch between them at runtime — see the run sections below.

---

## 3a. Run with uv

```bash
uv sync                 # one-time: install Python deps
uv run main.py
```

You'll be dropped into a chat prompt. The startup banner shows the resolved model and prompt variant:

```
Modell: gemma4:e4b  |  System-Prompt: implicit
```

### Switching models or prompts at runtime

Either edit `.env` and re-run, or set vars inline for one run:

```bash
# Big model with the short prompt
OLLAMA_MODEL=gemma4:26b SYSTEM_PROMPT=implicit uv run main.py

# Same small model but with the Notion playbook
OLLAMA_MODEL=gemma4:e4b SYSTEM_PROMPT=explicit uv run main.py
```

(Windows PowerShell: `$env:OLLAMA_MODEL="gemma4:26b"; uv run main.py`.)

---

## 3b. Run with Docker

The Docker workflow has **two phases**: build once (slow), run as often as you want (fast). The image contains all of Python, Node.js, your code, and your dependencies — but **no secrets and no config**. Tokens, the Ollama URL, the model name, and the prompt variant are all injected at runtime via `.env` / `-e` flags. That means **the same image runs against any model and either prompt** — no rebuild needed to switch.

### Build the image

```bash
docker build -t job-agent .
```

- `-t job-agent` tags the image as `job-agent:latest`.
- The `.` is the build context — Docker reads the `Dockerfile` from your current directory.

You only need to rebuild when **code or dependencies change**. Changing the model, prompt, or token does **not** require a rebuild.

### Point the container at your host's Ollama

Inside a container, `localhost` refers to the container itself — not your host machine. How you reach the host depends on your Docker runtime:

| Runtime                         | `OLLAMA_BASE_URL` value                | Extra `docker run` flag                        |
| ------------------------------- | -------------------------------------- | ---------------------------------------------- |
| Docker Desktop (macOS, Windows) | `http://host.docker.internal:11434/v1` | none                                           |
| Docker Engine on Linux          | `http://host.docker.internal:11434/v1` | `--add-host=host.docker.internal:host-gateway` |
| Linux, simplest alternative     | `http://localhost:11434/v1`            | `--network=host` (container shares host net)   |

Put the URL in `.env` (or pass with `-e`). Without one of these setups the agent will try to reach Ollama inside the container and fail.

### Run the container

```bash
docker run --rm -it --env-file .env job-agent
```

(Linux Docker Engine: append `--add-host=host.docker.internal:host-gateway` if you used that URL.)

Flag breakdown:

- `--rm` — remove the container when it exits (no leftover stopped containers).
- `-it` — **both** required. `-i` keeps stdin attached, `-t` allocates a pseudo-TTY. Without both, `prompt_toolkit` exits immediately with `Input is not a terminal`.
- `--env-file .env` — inject your tokens and config into the container's environment.

The agent's startup banner confirms what loaded:

```
Modell: gemma4:e4b  |  System-Prompt: implicit
```

### Switching models or prompts without rebuilding

Three ways, in increasing order of permanence:

**1. Per-run override** — for a single experiment, doesn't touch any file:

```bash
docker run --rm -it --env-file .env \
  -e OLLAMA_MODEL=gemma4:26b \
  -e SYSTEM_PROMPT=implicit \
  job-agent
```

`-e VAR=value` overrides whatever's in `--env-file`.

**2. Edit `.env` and re-run** — for a persistent project default. No rebuild, just restart the container:

```
OLLAMA_MODEL=gemma4:26b
SYSTEM_PROMPT=implicit
```

**3. Inherit from your shell** — useful when cycling through models:

```bash
export OLLAMA_MODEL=qwen2.5:14b
docker run --rm -it --env-file .env -e OLLAMA_MODEL job-agent
```

`-e OLLAMA_MODEL` (no `=value`) tells Docker "pass through whatever value my shell has."

### Common combinations

| Goal                                                                 | Command                                                                                              |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Default — small model + short prompt                                 | `docker run --rm -it --env-file .env job-agent`                                                      |
| Small model + Notion playbook (most reliable for `gemma4:e4b`)       | `docker run --rm -it --env-file .env -e SYSTEM_PROMPT=explicit job-agent`                            |
| Big model + short prompt (best output quality, needs ≥32 GB RAM)     | `docker run --rm -it --env-file .env -e OLLAMA_MODEL=gemma4:26b -e SYSTEM_PROMPT=implicit job-agent` |
| Try a different model entirely                                       | `docker run --rm -it --env-file .env -e OLLAMA_MODEL=qwen2.5:14b job-agent`                          |
| Big model with explicit playbook (rarely needed; useful for testing) | `docker run --rm -it --env-file .env -e OLLAMA_MODEL=gemma4:26b -e SYSTEM_PROMPT=explicit job-agent` |

> Whatever model you set in `OLLAMA_MODEL` must already be pulled on your **host** (`ollama pull <model>`). The container queries Ollama by name; it doesn't download.

### Inspecting the image (without running the agent)

Open a shell inside the container — handy for debugging dependencies, paths, or env vars:

```bash
docker run --rm -it --env-file .env job-agent bash
```

You can also confirm exactly what env the container received:

```bash
docker run --rm --env-file .env job-agent printenv OLLAMA_BASE_URL
docker run --rm --env-file .env job-agent printenv OLLAMA_MODEL
```

### Rebuilding after code changes

```bash
docker build -t job-agent .
```

The `Dockerfile` is layered so that:
- changing **code** (`agent/`, `mcp_servers/`, `main.py`) → only the final `COPY` layer rebuilds (seconds).
- changing **deps** (`pyproject.toml`, `uv.lock`) → `uv sync` re-runs (longer).
- changing **system packages** (apt installs in the Dockerfile) → full rebuild.

---

## Controls (chat prompt)

- **Enter** — inserts a newline (useful for pasting job descriptions).
- **Alt+Enter** (or **Esc, then Enter**) — sends the message.
- **`quit`**, **Ctrl+D**, **Ctrl+C** — ends the session.

While the agent works, a spinner shows what it's doing (`Denke nach…`, `Rufe <tool> auf…`).

### What happens on first run

1. The agent checks for a `Profil` sub-page under `Job Agent`.
2. Not finding one, it reads your `CV` and runs a short structured interview (max 5 questions per round) about desired roles, industry, work model, salary expectations, and development goals.
3. It creates the `Profil` page in Notion from your answers.
4. On subsequent runs it reads the existing profile and keeps refining it as you chat.

---

## Project layout

```
agent/             # Agent class: owns the LLM loop + tool dispatch
mcp_client/        # Thin async MCP client wrapper
mcp_servers/       # Local MCP servers (currently: Arbeitsagentur job search)
system_prompt.py   # German system prompts (implicit + explicit variants)
main.py            # Entry point: wires clients, starts the chat loop
Dockerfile         # Recipe for the containerized agent
.dockerignore      # What not to ship into the image
.env.example       # Template for required runtime config
```

---

## Roadmap

Planned in rough order. Each phase is independently shippable.

**Phase 1 — Polish**
- Stream LLM responses (faster feel, unlocks longer outputs)
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
- Publish a versioned Docker image to a registry

---

## Troubleshooting

- **`Warning: Input is not a terminal (fd=0)` then immediate exit (Docker)** — you forgot `-it`. Both flags are required.
- **`httpx.UnsupportedProtocol: Request URL is missing an 'http://' or 'https://' protocol.`** — `OLLAMA_BASE_URL` is malformed. Most often: quotes around the value in `.env`. Unquote it.
- **`openai.APIConnectionError: Connection error`** — Ollama isn't reachable. Check it's running on the host and that `OLLAMA_BASE_URL` matches your runtime (see the Docker → "Point the container at your host's Ollama" table).
- **`401 Unauthorized` from Notion** — token is invalid (typo / quotes / wrong value), or you created a new integration and forgot to share the `Job Agent` page with it (step 1c).
- **`SYSTEM_PROMPT must be one of [...]`** — typo in the variant. Valid values: `implicit`, `explicit`.
- **Notion tool calls fail with `body.filter.property should be defined`** — happens with smaller models that mis-fill the search filter. Switch to `SYSTEM_PROMPT=explicit`, which tells the model to omit the filter.
- **Agent calls you the wrong name / answers without consulting Notion** — small model + `implicit` prompt is the usual cause. Switch to `SYSTEM_PROMPT=explicit`.
- **Agent can't find the CV** — page must be named exactly `CV`, nested directly under `Job Agent`, with non-empty content.
- **Inference is very slow** — make sure Ollama runs **on your host**, where it can use the GPU. Running Ollama inside a container drops it to CPU-only on macOS (no Metal access) and Windows; on Linux you'd need explicit `--gpus all` plus an NVIDIA setup. Keeping Ollama on the host is the simplest path to native performance everywhere.
