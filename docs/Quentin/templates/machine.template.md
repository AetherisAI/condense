# <Slice> — Machine Doc

> Full design + plan + implementation record. Paired with `human.md` (never one without the other).

**Status:** planned | in-progress | merged `v0.<n>.0` &nbsp;·&nbsp; **Branch:** `feat/<slice>` &nbsp;·&nbsp; **Updated:** YYYY-MM-DD

## 1. Overview
<What this slice is, its single responsibility, and where it sits in the lego.>

## 2. Design
- **Port(s) implemented / consumed:** <exact signatures>
- **Adapter(s) produced:** <files>
- **Data flow:** <inputs → transforms → outputs>
- **Config keys used:** <env keys from config.py>
- **Dependency rule check:** <confirm imports point inward only>

## 3. Plan (writing-plans format)
> Checkbox tasks. Each step is one 2–5 min action. TDD. Commit per task.

### Task 1: <name>
**Files:** Create/Modify/Test `exact/paths`
**Interfaces:** Consumes `<sig>` · Produces `<sig>`
- [ ] Step 1: write failing test (`code`)
- [ ] Step 2: run it, expect FAIL
- [ ] Step 3: minimal implementation (`code`)
- [ ] Step 4: run it, expect PASS
- [ ] Step 5: commit

## 4. Test strategy
- <which fakes are used (FakeEmbedder / FakeVectorStore / null rerank); unit vs integration.>

## 5. Implementation log
| Date | Commit | Change |
|------|--------|--------|
| | | |

## 6. Decisions
- <link each decision taken here to `DECISIONS.md#<anchor>`>

## 7. Changelog
- <vX.Y.0 — summary on merge>
