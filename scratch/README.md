# scratch/ — disposable spikes & experiments

Throwaway code that answers a **one-time question** — "what does this payload look like?", "does this endpoint work?", "what fields come back?".

- Everything here is **git-ignored and disposable.** Delete anything, anytime, no ceremony.
- **Never** put permanent code here, and **never** import `scratch/` from `src/`.
- When a spike proves something, **extract** the reusable part into a proper `src/` module and **delete** the spike. The spike's job was to birth the module; once born, the spike is trash.
- If you keep re-running a spike, it wants to **graduate** into a real `src/` command.

See `CLAUDE.md` → "Scratch vs permanent — keep or kill" for the full rule.
