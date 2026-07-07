# scratch/ — experiments, one-off tools & analysis

A git-ignored working area, separate from the permanent `src/` codebase. Spikes, comparisons, audits, quick analyses, and tools you're not ready to commit live here.

- **git-ignored and outside the product — but NOT auto-deleted.** Code here persists and may have ongoing use (a comparison you re-run, an audit generator). Nothing here is removed unless Jake specifically says so.
- **Never** import `scratch/` from `src/`, and never write permanent product code here.
- When something here earns a permanent place, **promote** the reusable part into a proper `src/` module. Promotion is additive — it doesn't require deleting the scratch original.

See `CLAUDE.md` → "Scratch vs permanent" for the full rule.
