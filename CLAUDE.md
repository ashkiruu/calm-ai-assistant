# CALM AI Assistant — Claude Code Setup

## Project Overview
CALM is a **safety-critical** context-aware assistant for VR emergency-response learning (Grade 4). This requires:
- ✅ Deterministic protocol routing (no LLM for P0/P1 decisions)
- ✅ Curated protocol cards only (no raw PDF chunks)
- ✅ Comprehensive test coverage (55+ unit tests)
- ✅ Multi-language support (EN/Filipino/Taglish)
- ✅ Child-safety compliance

## ECC Workflow (Plan → Test → Implement → Review → Verify)

### Before Starting Any Task
```bash
/plan [task description]
```
ECC planning agent will outline the approach, consider safety implications, and flag risks.

### While Coding
```bash
/run
```
Start the dev server to test changes in real scenarios.

### Before Committing
1. **Tests must pass:**
   ```powershell
   .\venv\Scripts\python.exe -m unittest discover -s tests -v
   ```

2. **Validate corpus & missions:**
   ```powershell
   .\venv\Scripts\python.exe scripts\validate_corpus.py
   .\venv\Scripts\python.exe scripts\validate_missions.py
   ```

3. **ECC auto-review diffs:**
   ```bash
   /code-review medium
   ```

### After Committing
```bash
/security-review
```
For safety-critical changes (protocol cards, router logic, API endpoints).

## Key Files & Their Purpose

| File | Purpose | Strictness |
|------|---------|-----------|
| `calm_core/router.py` | Deterministic P0/P1 decisions | **CRITICAL** — reviewed only |
| `calm_core/retrieval.py` | P2 question search | **HIGH** — test 100% |
| `config/protocol_cards.yaml` | Curated protocols | **CRITICAL** — DepEd approved only |
| `examples/school_earthquake_request.json` | API contract | **HIGH** — tests must match |
| `tests/` | Unit test suite | **HIGH** — new code → new tests |

## Safety Guidelines
- **Never use LLM for routing decisions** — use deterministic logic only
- **Never search raw PDFs** — only curated protocol cards
- **Never include child PII** in logs/events
- **Never skip validation** before schema changes
- **Always update tests** when touching request/response contracts

## Memory & Learning
ECC remembers:
- Safety decisions you've made
- Protocol revisions & approvals
- Test coverage improvements
- Integration milestones

Access with: `/ecc-recall safety-decisions`

## External Approvals Required
- [ ] BFP (Bureau of Fire Protection)
- [ ] PHIVOLCS (Philippine Institute of Volcanology)
- [ ] PAGASA (Philippine weather service)
- [ ] DepEd (Department of Education)
- [ ] Local DRRMO (Disaster Risk Reduction Office)
- [ ] Partner school approval

Current status: **Internally validated** (prototype development only)

## Useful Commands
- `/help` — All available ECC commands
- `/ecc-config` — View/edit project ECC settings
- `/code-review ultra` — Deep multi-agent review (for risky changes)
- `/security-review` — Safety-specific audit
- `/run` — Launch dev server for manual testing
- `/plan [task]` — Plan before starting work
