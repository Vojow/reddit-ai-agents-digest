# AGENTS.md

## Project purpose
Build a daily Reddit intelligence pipeline focused on:
- AI agents
- AI-enhanced development
- AI-enhanced testing

Primary source subreddits for MVP:
- r/Codex
- r/ClaudeCode
- r/Vibecoding

Primary outputs:
- Daily Markdown digest in `reports/daily/YYYY-MM-DD.md`
- Refreshed `reports/latest.md`
- Optional LLM-enhanced digest in `reports/daily/YYYY-MM-DD.llm.md`
- Optional refreshed `reports/latest.llm.md`
- Structured export to Google Sheets
- Optional OpenAI-generated "watch next" suggestions derived from the day's findings

## Tech expectations
- Python 3.12
- Prefer small, composable modules
- Use typed Python where practical
- Keep external dependencies minimal
- Prefer clear data models over loose dict passing
- Use pytest for tests

## Implementation rules
- Do not hardcode secrets
- Read config from environment variables or files in `config/`
- Keep raw fetched data in `data/raw/`
- Keep normalized/intermediate data in `data/processed/`
- Keep run state in `data/state/`
- Markdown output must be deterministic for the same input
- Every new feature should include at least one test when reasonable
- Treat [`docs/invariants.md`](docs/invariants.md) as the primary change-safety reference
- For delegated Codex work, use the project-local subagents in `.codex/agents/`
- Treat [`docs/subagents.md`](docs/subagents.md) as the authoritative contract for those subagents

## Digest rules
Each daily digest should include:
1. Executive summary
2. Picked topics
3. Emerging themes
4. Optional "watch next" section

For every picked topic include:
- title
- executive summary
- relevance for you
- original post link
- source subreddit
- supporting thread count
- impact score

If the LLM-enhanced digest is generated:
- it must use the same selected topics as the deterministic digest
- it may only rewrite the top-level executive summary and topic prose
- it must not change topic titles, links, source subreddit attribution, scores, or counts

## Scoring guidance
Prioritize:
- actionable technical value
- useful discussion depth in comments
- novelty
- relevance to AI agents / AI dev / AI testing
- recency

Avoid over-weighting raw upvotes alone.

## Review guidelines
Treat these as high priority:
- broken scheduling logic
- duplicate row creation in Google Sheets
- missing idempotency in daily runs
- silently swallowed exceptions
- incorrect subreddit filtering
- malformed Markdown digest structure
- LLM rewriting that changes deterministic topic selection or source attribution
- secrets leakage risk
- changes that break deterministic output

## Workflow guidance
When implementing an issue:
1. Read the issue carefully
2. Make the smallest complete change that satisfies acceptance criteria
3. Update docs if behavior changes
4. Add or update tests
5. Keep commits/PR scope focused
