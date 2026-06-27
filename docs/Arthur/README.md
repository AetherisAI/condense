# docs/Arthur — Engine docs (how this folder works)

Dev A's documentation system (ingest + storage). Mirrors [`../Quentin/`](../Quentin/) so both halves
stay visibly aligned. Shared rules: [`../../CLAUDE.md`](../../CLAUDE.md). Shared contracts:
[`../api-schema.md`](../api-schema.md) · [`../dev-split.md`](../dev-split.md) ·
[`../foundation.md`](../foundation.md).

## Layout
| Path | What | Lifecycle |
|------|------|-----------|
| [`ROADMAP.md`](./ROADMAP.md) / [`ROADMAP.human.md`](./ROADMAP.human.md) | Master plan: engine work packages A0–A6. Machine + ≤500w human. | Living |
| [`active/`](./active/) | The **current** work package: `machine.md` (full) + `human.md` (≤500w). | Reset each WP |
| `archive/` | Merged work packages, one folder per version (`v0.<n>.0-<slice>/`). | Frozen on merge |
| [`DECISIONS.md`](./DECISIONS.md) | Append-only Dev A decision log (Decision · Why · Alternatives · Basis). | Never archived |
| [`templates/`](./templates/) | `human.template.md` + `machine.template.md`, copied into `active/` per WP. | Stable |

## The loop (per work package)
1. **Branch** `feat/<slice>`; copy templates into `active/`.
2. **Plan** → fill `active/machine.md`; write `active/human.md` alongside it (never one without the other).
3. **Implement** task-by-task (subagent-driven), tests-first, commit per task; log forks in `DECISIONS.md`; docs ship in the same commits as the code.
4. **On merge:** move `active/*` → `archive/v0.<n>.0-<slice>/`, reset `active/` from `templates/`.

## Start here
Read [`../../CLAUDE.md`](../../CLAUDE.md) → [`ROADMAP.human.md`](./ROADMAP.human.md) →
[`active/human.md`](./active/human.md). ~5 minutes to the whole engine picture.
