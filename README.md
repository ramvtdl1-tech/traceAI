# TRACE AI

A Streamlit hackathon demo for chat, problem solving, and memory you control.

Each browser session owns its conversations and memories. Select **Find memories**
to extract suggestions from your own messages, then **Approve** the facts you want
TRACE to recall. **New conversation** clears chat and keeps that session's memories.
Remove individual memories or use **Forget all memories** at any time.

Session data is temporary: refreshing, closing the browser, or restarting the
server may reset it. This release does not provide account-based long-term
storage. Existing `trace_history.json` and SQLite data are never loaded by the app.
Messages and memory-extraction requests are sent to Nebius.

## Run locally

Use Python 3.11. From the project folder:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `.env` does not already exist, copy `.env.example` to `.env`. Set these values
without committing the file:

```dotenv
NEBIUS_API_KEY=your_real_key
NEBIUS_MODEL=an_available_chat_model_id_from_your_nebius_catalog
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
DEMO_ACCESS_CODE=
```

Set `DEMO_ACCESS_CODE` to a private code if you want only judges or invited viewers
to access the demo. Leave it empty for public access.

```bash
python -m streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Upload the source files to [ramvtdl1-tech/traceAI](https://github.com/ramvtdl1-tech/traceAI),
   or run the commands below from this folder:

   ```bash
   git init
   git branch -M main
   git add .gitignore .env.example .streamlit/config.toml app.py demo_support.py requirements.txt README.md database/__init__.py database/memory_extractor.py tests scripts
   git diff --cached --name-only
   git commit -m "Prepare TRACE AI hackathon demo"
   git remote add origin https://github.com/ramvtdl1-tech/traceAI.git
   git push -u origin main
   ```

   Review the staged filenames before committing. `.env`, `data/`,
   `trace_history.json`, and `.streamlit/secrets.toml` must be absent.

2. Sign in at [share.streamlit.io](https://share.streamlit.io/), choose **Create app**,
   select the repository and `main` branch, and set the main file path to `app.py`.
3. In **Advanced settings**, select **Python 3.11**. Paste these root-level TOML
   entries into **Secrets**, substituting real values:

   ```toml
   NEBIUS_API_KEY = "YOUR_REAL_KEY"
   NEBIUS_MODEL = "YOUR_AVAILABLE_CHAT_MODEL_ID"
   NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
   DEMO_ACCESS_CODE = "YOUR_OPTIONAL_JUDGE_ACCESS_CODE"
   ```

   Omit `DEMO_ACCESS_CODE` for a public demo. Do not add a TOML section header.
   Root secrets work with the app's configuration reader. No `.env` upload is needed.
4. Deploy. Open the assigned `streamlit.app` URL and send a test message.
5. In a separate private browser window, verify it starts with empty chat and
   memory. Test the memory demonstration below, then share the URL with judges.

[Official deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
· [Secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)

## A short memory demonstration

1. Say: “I am building a Python project and prefer short explanations.”
2. Wait for the reply, then select **Find memories** in the sidebar.
3. Approve a suggested fact. Pending suggestions are excluded from chat context.
4. Select **New conversation**, then ask “What do you remember about my project?”
5. Remove the memory and start another conversation to demonstrate forgetting.

Memory extraction is explicit and uses an additional provider request. Suggestions
marked sensitive are discarded. Approval is still required for every other fact;
review suggestions before accepting them. Removing a memory removes it from future
memory context; text already present in the current chat remains until you start a
new conversation.

## Checks and demo limits

```bash
python -m pip check
python -m unittest discover -s tests -v
```

The regression suite uses fake credentials and a mocked provider. To verify real
Nebius authentication and completion support (uses a small amount of API credit):

```bash
python scripts/check_nebius.py
```

The app limits each prompt to 4,000 characters and outgoing chat history to 40
messages / 24,000 characters, plus up to 30 approved memories of 500 characters.
A session can make 40 AI requests, at least two seconds apart. All sessions in one
server process share a 200-request sliding hourly limit. Failed requests count
against limits. New conversation and forgetting memories do not reset quotas.
Automatic provider retries are disabled; individual requests time out after 45
seconds. Errors shown to visitors exclude raw provider details and credentials.

The shared quota is per server process and resets when that process restarts. It
is a demo guard, not a provider spending cap or a distributed rate limiter. Set
provider spending limits where available, and use the optional access code for a
controlled presentation. Durable account-based memory and multiple-server use
require authenticated ownership and an external database.

The root `test_*.py` files and unused SQLite modules are earlier development
scripts. Use the `tests/` command above for the current demo; some older scripts
write to SQLite or call the live API.

## Clean deployment archive

```bash
python scripts/package_release.py
```

This creates `dist/trace-ai-deploy.zip` from an explicit source allowlist. It omits
credentials, existing conversations, databases, caches, and legacy demo scripts.
Extract it before uploading its contents to GitHub; Community Cloud needs source
files in the repository, rather than the zip itself.
