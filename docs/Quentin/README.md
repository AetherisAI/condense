# docs/ — how this folder works

The Dev B documentation system. Rules live in [`../CLAUDE.md`](../CLAUDE.md) §6; this is the map.

## Layout
| Path | What | Lifecycle |
|------|------|-----------|
| [`ROADMAP.md`](./ROADMAP.md) / [`ROADMAP.human.md`](./ROADMAP.human.md) | Master plan: all work packages WP0–WP9. Machine + ≤500w human. | Living — not archived |
| [`active/`](./active/) | The **current** work package only: `machine.md` (full plan) + `human.md` (≤500w). | Reset each WP |
| `archive/` | Merged work packages, one folder per version: `v0.<n>.0-<slice>/`. | Frozen on merge |
| [`DECISIONS.md`](./DECISIONS.md) | Global, append-only decision log (Decision · Why · Alternatives · Basis). | Never archived |
| [`templates/`](./templates/) | `human.template.md` + `machine.template.md` — copied into `active/` per new WP. | Stable |
| `specs/` | Optional superpowers design specs for larger features. | As needed |

## The loop (per work package)
1. **Branch** `feat/<slice>`; copy templates into `active/`.
2. **Plan** (superpowers brainstorming → writing-plans) → fill `active/machine.md`; write `active/human.md` **alongside** it (never one without the other).
3. **Implement** task-by-task (subagent-driven), TDD, commit per task; log every fork in `DECISIONS.md`; keep both docs current in the *same commits* as the code.
4. **On merge:** bump version → move `active/*` → `archive/v0.<n>.0-<slice>/` → reset `active/` from `templates/` → tag `v0.<n>.0` if deployable.

## Start here
New session or onboarding? Read `../CLAUDE.md` → `ROADMAP.human.md` → `active/human.md`. That's the whole picture in ~5 minutes.
