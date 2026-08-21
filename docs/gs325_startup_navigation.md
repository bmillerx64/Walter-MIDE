# GS325 startup navigation guard

A browser-side voice preference discovery helper currently uses `window.parent.location.replace(...)` to persist URL query parameters during initial page render. In Streamlit that is a full navigation: it tears down the active websocket/session and forces `app.py` to start again.

GS325 replaces that navigation with `window.parent.history.replaceState(...)` so the URL can be updated without creating a new browser/server session. No scanning, discovery, ranking, readiness, scoring, execution, news, or evidence semantics are changed.
