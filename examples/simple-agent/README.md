# simple-agent

Minimal instrumented LangGraph app — the demo and end-to-end smoke test for
the LangOps pipeline (built in Phase 3 of `tasks.md`).

Intended usage:

```bash
docker compose up          # in the repo root: full LangOps stack
pip install -e ../../sdk
python main.py             # run on the host; spans go to localhost:4317
```

Then open http://localhost:3000 and watch the execution appear.
