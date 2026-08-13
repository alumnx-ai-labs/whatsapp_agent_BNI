# Contributing — fork, clone, branch, PR

This repo is small and everyone is working the same day, so keep this
mechanical: one person, one module, one branch, one PR into `main`.

## One-time setup (each person)

1. Fork `alumnx-ai-labs/whatsapp_agent_BNI` on GitHub (button, top right).
2. Clone **your fork**, not the upstream repo:
   ```bash
   git clone https://github.com/<your-username>/whatsapp_agent_BNI.git
   cd whatsapp_agent_BNI
   git remote add upstream https://github.com/alumnx-ai-labs/whatsapp_agent_BNI.git
   ```
3. Create your branch off `main`, named after your module (see the table in
   `README.md` / `CODEOWNERS`):
   ```bash
   git checkout -b tool/lookup-customer      # example — use your own module name
   ```

## While working

- Touch **only** the file(s) listed for your module in `CODEOWNERS`. If you
  think you need to change something outside your lane (a tool signature in
  `tools.py`, a state name in `flow.py`, the `schema.sql`), ping the lead
  first — those are frozen contracts for today.
- Test locally without waiting on real infra: the direct-API sibling
  projects under `docs/reference/` show the pattern of mocking the LLM and
  using a fake in-memory Supabase client — do the same here so you're not
  blocked on a shared Supabase project or spending real API calls.
- Commit small, with clear messages.

## Opening the PR

```bash
git push origin tool/lookup-customer
```
Then open a PR **from your fork's branch into `alumnx-ai-labs/whatsapp_agent_BNI:main`**.
Title it `[module] short description`, e.g. `[crm-lookup] verify against real Supabase table`.
Tag the lead as reviewer.

## Keeping your branch current

If `main` moves while you're working:
```bash
git fetch upstream
git rebase upstream/main
```

## Merge order (handled by the lead)

Tool/module PRs merge independently, in any order — each owns a distinct
file. The lead does one final integration pass after all of them are in:
wiring `flow.py` end-to-end against the real Supabase project and a live
WhatsApp sandbox number, before anything ships.
