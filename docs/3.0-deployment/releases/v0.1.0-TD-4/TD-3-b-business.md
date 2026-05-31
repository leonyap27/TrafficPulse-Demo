# TD-3 — Recent traffic incident dashboard

Operations users can now view recent traffic incidents from a single dashboard page that opens in any browser — no install, no login, no server required.

## What's new for users

- **At-a-glance counts** — a row of headline cards shows the total number of recent incidents, how many are high severity, and a breakdown by incident type (Accidents, Congestion, Roadworks, Breakdowns).
- **Searchable incident list** — a table lists every recent incident with its road, location, type, severity, and current status. Users can type any road name or location keyword to narrow the list to just the incidents that matter.
- **Severity filter** — a dropdown lets the user focus on High, Medium, or Low severity only.
- **Latest update time** — the header always shows the timestamp of the most recent incident in the feed, so users immediately know how fresh the picture is.
- **Clear "nothing to show" message** — if the filters return no matches, the page tells the user that plainly instead of leaving an empty table.

## Outcome

An operations user opening the dashboard during the morning peak can spot how many active incidents exist, see how many are serious, locate ones on the road they care about, and get a sense of when the data was last refreshed — all without leaving the page.

The dashboard runs entirely off a small reference dataset bundled with the page, so it can be used in demos, training, and walkthroughs without depending on production traffic systems.
