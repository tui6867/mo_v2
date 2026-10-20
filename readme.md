# Mass Outreach

Invite-only Python/Streamlit job outreach. Supabase handles verified magic-link
authentication, invitations, durable records and quotas. Sending uses a
provider-independent SMTP adapter; fake test mode is the default.

## First Streamlit Community Cloud launch

Deploy repository **tui6867/mass-outreach-branch**, branch **main**, entrypoint
**app.py**, Python **3.12**. Community Cloud supports the existing **uv.lock**;
do not add a second requirements file or run the historical package patch script.

Follow **[STREAMLIT_LAUNCH.md](STREAMLIT_LAUNCH.md)** for deployment, secrets,
Supabase setup and activation gates. The safe secrets template is
`.streamlit/secrets.toml.example`. Missing settings keep access/sending blocked.
This repo does not contain credentials or a Community Cloud deployment API.

## Development
```sh
uv sync --locked
uv run streamlit run app.py
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

`app.py` composes Streamlit pages; `outreach/domain` is pure business logic;
`outreach/services` holds auth/persistence/SMTP boundaries. A session-scoped
`st.connection` adapter in `outreach/connections.py` reuses HTTP transport without
caching user tokens, authorization or database results. `outreach/streamlit_settings.py`
maps `st.secrets` and explicit environment overrides into pure service configuration.

See [SETUP.md](SETUP.md) for product/backend details and
[HANDOFF_STATUS.md](HANDOFF_STATUS.md) for checks and remaining release gates.
