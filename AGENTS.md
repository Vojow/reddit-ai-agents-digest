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
- Structured export to Google Sheets

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

## Digest rules
Each daily digest should include:
1. Executive summary
2. Top tools mentioned
3. Top approaches/workflows
4. Top guides/resources
5. Testing and quality insights
6. Notable Reddit threads
7. Emerging themes
8. Optional "watch next" section

For every notable item include:
- title
- subreddit
- permalink
- why it matters
- impact score
- extracted tags

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
- secrets leakage risk
- changes that break deterministic output

## Workflow guidance
When implementing an issue:
1. Read the issue carefully
2. Make the smallest complete change that satisfies acceptance criteria
3. Update docs if behavior changes
4. Add or update tests
5. Keep commits/PR scope focused
