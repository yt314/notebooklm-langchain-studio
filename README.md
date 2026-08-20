# NotebookLM (in miniature) — a LangChain learning project

A NotebookLM-style **grounded research assistant**: upload documents, chat with an agent that
retrieves relevant passages via semantic search and answers with citations, all with short-term
memory across turns. Built as a staged learning project for **LangChain v1** / **LangGraph**.

## What it does

- **Sources** — add documents by pasting text, uploading `.md`/`.txt` files, or having an agent
  research a topic on the web (search → pick promising results → scrape → index). Toggle which
  sources are *active*; only active sources are searched.
- **Chat** — ask questions about your active sources. The agent decides on its own whether to
  search the corpus, list the available sources, or fetch a source's full text, then answers
  grounded in what it found, with a citation for each source it used. Conversation memory is kept
  per browser tab (a fresh "New chat" starts a new thread).
- **Studio / Notes** — save any answer as a note; artifact generation (infographic, PowerPoint,
  summary, FAQ) is scaffolded in the UI but not implemented yet.

## Stack

- **Agent framework:** [LangChain](https://python.langchain.com/) v1 (`create_agent`) +
  [LangGraph](https://langchain-ai.github.io/langgraph/) (checkpointer for memory)
- **Chat model:** Google Gemini (`google_genai:gemini-flash-latest` by default)
- **Embeddings:** Cohere (`embed-multilingual-v3.0` by default)
- **Vector store:** LangChain's `InMemoryVectorStore`
- **Web research:** [Firecrawl](https://www.firecrawl.dev/) (search + scrape) for adding sources
  from the web
- **Backend:** FastAPI · **Client:** static HTML/JS/CSS, no build step

Everything is configurable via env vars — see [`.env.example`](.env.example).

### TED pipeline

The TED graph is available through the checkpointed job API:

```text
POST /api/ted/jobs                 start a job and receive the approval payload
POST /api/ted/jobs/{id}/resume     approve or request a revision
GET  /api/ted/jobs/{id}            read the persisted job state
POST /api/podcast/jobs             start a podcast job and receive the approval payload
POST /api/podcast/jobs/{id}/resume approve or request a revision
GET  /api/podcast/jobs/{id}        read the persisted podcast state
```

After approval, `synthesize_audio` renders the Hebrew script through the selected
provider (`elevenlabs` by default, or `cloudrun`). Audio is written to
`data/ted_audio/{job_id}.mp3`; Cloud Run jobs expose a `.url` sidecar instead.
The checkpoint and output path make retrying a failed resume idempotent.

The podcast pipeline uses `Send` fan-out for per-segment research and writing,
then critiques the assembled episode. Its separate `audio_graph.py` asks for
audio approval before rendering alternating host/guest lines through the shared
TTS provider.

To open the graph in LangGraph Studio, install the LangGraph CLI and run it from
the project root; the graph is declared in `langgraph.json` as `ted`.

## Project structure

```
client/                 web client — single-page HTML/JS/CSS, served as static files at "/"
src/
  agents/
    chat.py             the conversational agent: tools + system prompt + memory
    research.py         the deep-research agent: web search + scrape + save as sources
  core/
    store.py            SourceStore — in-memory corpus + semantic vector index
    sources.py          chunking (RecursiveCharacterTextSplitter) + doc formatting for the LLM
  api/
    app.py               FastAPI endpoints (sources, chat, studio, notes)
    services.py           glue between the API contract and the agent/store
    schemas.py             Pydantic request/response models
    serve.py                entry point for `uv run notebooklm-serve`
  app.py                CLI entry point for exercising the agent directly (`uv run notebooklm`)
```

## Quick start

```bash
uv sync
cp .env.example .env         # fill in GOOGLE_API_KEY and COHERE_API_KEY
uv run notebooklm-serve
```

Then open **http://127.0.0.1:4040** in a browser.

Get API keys at [Google AI Studio](https://aistudio.google.com/apikey), the
[Cohere dashboard](https://dashboard.cohere.com/api-keys), and
[Firecrawl](https://www.firecrawl.dev/app/api-keys) (all have a free tier).

> **Troubleshooting: `uv run` fails downloading a Python build (TLS/certificate error).**
> This usually means a network content filter is intercepting HTTPS. If a working `.venv`
> already exists, run the server directly instead: `./.venv/Scripts/notebooklm-serve.exe` (Windows)
> or `./.venv/bin/notebooklm-serve` (macOS/Linux).

> **Troubleshooting: web search / chat fails with `429 RESOURCE_EXHAUSTED`.**
> Gemini's free tier caps requests per model per day (20/day at the time of writing). A single
> "research the web" call alone can use most of that, since the agent makes several LLM calls per
> run (query planning, judging each result, saving sources). If you hit this, either wait for the
> daily quota to reset or enable billing on your Google AI Studio project for a much higher limit.

### CLI (no server, no browser)

```bash
uv run notebooklm "What is FleetOS?"     # one-off question
uv run notebooklm                        # interactive loop
```

Useful for checking that the agent talks to the LLM correctly, independent of the web client.

## How to use it

1. **Add a source** — click **+ Add** in the left panel, then either paste text, upload a
   `.md`/`.txt` file, or type a topic under "or research the web" and click **🌐 Search** to have
   an agent search, scrape, and index a handful of good sources on that topic automatically.
2. **Toggle sources active/inactive** — the checkbox next to each source controls whether it's
   included in semantic search. "Select all" toggles every source at once.
3. **Ask a question** in the chat panel. The agent grounds its answer in the active sources and
   shows which source(s) it cited underneath the reply.
4. **Save an answer** as a note with "+ Save to note" (right panel), or view/delete a source or
   note from its list.
5. **New chat** resets the conversation thread (fresh short-term memory) without touching your
   sources.

## Feature roadmap

| Feature | Status |
|---------|--------|
| Retrieval (grounded Q&A, semantic search) | ✅ done — `core/store.py`, `core/sources.py` |
| Agent + tools (`search_sources`, `list_sources`, `get_source`) | ✅ done — `agents/chat.py` |
| Short-term memory (checkpointer + `thread_id`) | ✅ done |
| Web search sources (Firecrawl: search + scrape + crawl tools, deep research) | ✅ done — `agents/research.py` |
| Structured output (Studio artifacts) | ⏳ planned |
| Event streaming | ⏳ planned |
| Human in the loop | ⏳ planned |

## Learning goals

This project was built to practice:
- Building an agent with LangChain's `create_agent`
- Running a RAG pipeline with semantic search in LangChain
- Wiring tools to an agent, with docstrings the LLM uses to decide when to call each one
- Adding conversation memory with a `Checkpointer`
- Giving an agent autonomy over a multi-step web research process (search → scrape → index) with
  the [Firecrawl](https://www.firecrawl.dev/) API
