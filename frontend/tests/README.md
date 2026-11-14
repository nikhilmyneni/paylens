# Browser checks

Run from the repository root with the frontend on port 5173 and the seeded API on port 8000:

```powershell
python -m pip install playwright
python -m playwright install chromium
python frontend/tests/smoke.py
python frontend/tests/loading.py
python frontend/tests/theme.py
python frontend/tests/content_audit.py
python frontend/tests/compensation_slider.py
```

`smoke.py` checks desktop, tablet and phone layouts, queue wheel scrolling, report loading, horizontal overflow and browser errors. `loading.py` delays API responses to verify skeletons, checks reduced-motion behavior, and injects a timeline failure to verify the error state. `theme.py` checks system defaults, OS theme changes, manual overrides, persistence and reduced motion. They read the demo data without changing proposals. Screenshots are written to `frontend/.preview/`.

The backend suite separately checks approval transitions, optimistic concurrency, effective-date application, migrations, validation and reporting. A complete browser approval flow was also verified against an isolated copy of the local SQLite database, keeping preview data intact.

`content_audit.py` checks that unsupported live/sealed claims are absent, missing-band records do not claim successful matching or allow an adjustment, unknown currency does not crash rendering, and 1% coverage renders as 1.0%.

`compensation_slider.py` checks keyboard and pointer adjustment, exact values, out-of-range entry, mobile layout and submitted amounts. Proposal requests are intercepted, so this test does not write to the database.
