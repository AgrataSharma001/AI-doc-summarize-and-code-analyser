# Phase 0 work board

This local Markdown board is the team's starting issue board. Replace owner letters with team member names at kickoff. Move a card to `Done` only when its acceptance evidence exists. The 20-hour Phase 0 estimate is planning time, not time already spent in this session.

| ID | Task and evidence | Owner | Estimate | Depends on | Status |
|---|---|---|---:|---|---|
| P0-01 | Agree on MVP, limits, privacy, target users, and release gates; sign off [scope](MVP_SCOPE.md) | A | 3 h | Frontend audit | Ready for team sign-off |
| P0-02 | Freeze frontend/API field and error contract; review [API contract](API_CONTRACT.md) with B | B | 4 h | P0-01 | Drafted; review pending |
| P0-03 | Run [20-case local model spike](MODEL_SPIKE.md) on demo laptop and select tested model digest | D | 6 h | P0-04; Ollama/model install | Pending hardware run |
| P0-04 | Review [80-case evaluation corpus](eval/README.md) and rubric; correct ambiguous expected answers | C+D | 5 h | Scope | Seed set created; reviewer audit pending |
| P0-05 | Assign named owners, accept branch/review rules, and maintain [decision log](DECISIONS.md) | A | 2 h | Team names | Drafted; team adoption pending |

## Ownership map

| Role | Responsibility in Phase 0 and later |
|---|---|
| A — project lead/architect | Scope, schedule, issues, architecture decisions, integration/demo |
| B — API/security lead | API contract, accounts, sessions, persistence, request validation |
| C — extraction/code lead | File parsing, source mapping, Python static tools, corpus quality |
| D — agent/evaluation lead | Local model spike, prompts/orchestration, evaluation and measurement |

Every card has one accountable lead even when another person helps. A reviews schedule changes weekly. B and D should jointly review any change to data flow between uploads, storage, and the model.

## Branch and review rules to adopt

1. Use a short-lived branch per issue, named `phase0/P0-xx-short-topic` or `phase1/P1-xx-short-topic`.
2. Put the issue ID, change summary, test evidence, and any data/privacy effect in each pull request description.
3. Require one reviewer other than the author and passing relevant CI before merge to `main`.
4. Keep `main` usable for the current milestone. Do not commit uploads, SQLite databases, model weights, credentials, or model outputs containing private data.
5. Record a decision in `DECISIONS.md` when scope, model, storage, security, or deployment assumptions change.

## Next board after Phase 0

The first Phase 1 card is **P1-01: FastAPI + SQLite skeleton**, owned by B, accepted when `/api/auth/session` and `/health` respond from the same origin as `Frontend/`. Start it after the API contract review; the model spike can continue independently on the demo laptop.
