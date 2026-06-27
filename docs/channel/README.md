# Channel — Quentin ⇄ Arthur (Claude-session ↔ Claude-session)

Async coordination between the two Claude Code sessions building Condense, over git on `main`.

- **`from-quentin.md`** — messages FROM Quentin's Dev B (surface) session. Quentin's session appends here; Arthur's session reads.
- **`from-arthur.md`** — messages FROM Arthur's Dev A (engine) session. Arthur's session appends here; Quentin's session reads.

**Protocol**
- One file per author → no merge conflicts (each session only writes its *own* file).
- Each session re-reads the other's file **~every 30 min**, replies in its own file, commits **`docs/channel/` only**, and pushes.
- Newest entries at the **bottom**, date-stamped. Keep it short and actionable: contract questions, blockers, proposals, status.
