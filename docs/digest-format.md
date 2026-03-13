# Digest Format

The deterministic digest is the source-of-record output for a run:
- `reports/daily/YYYY-MM-DD.md`
- `reports/latest.md`

When `OPENAI_API_KEY` is configured, the pipeline can also render an
LLM-enhanced variant:
- `reports/daily/YYYY-MM-DD.llm.md`
- `reports/latest.llm.md`

The LLM variant must use the same picked topics as the deterministic digest. It
may only rewrite topic prose and must not change titles, links, subreddit
attribution, support counts, or impact scores.

Current section order:

```md
# Daily Reddit Digest — 2026-03-12

## Warnings
- OPENAI QUOTA EXHAUSTED: Watch Next suggestions and LLM topic rewrites were skipped. The deterministic markdown below was generated successfully without OpenAI enhancements.

## Executive Summary
- Picked 6 topics from 3 subreddit(s): r/Codex, r/ClaudeCode, r/Vibecoding
- Highest-signal topic: Example topic
- Total posts analyzed: 48

## Picked Topics
### 1. Example topic
- Executive summary: Concise explanation of the topic.
- Relevance for you: Why the topic matters for AI agents, AI dev, or AI testing.
- Original post: [Thread title](https://www.reddit.com/...)
- Source subreddit: r/Codex
- Supporting threads: 3
- Impact score: 8.88

## Emerging Themes
- AI Agents
  - Evidence: Example topic, Another topic

## Watch Next
- Signal worth monitoring tomorrow
```

Notes:
- `Warnings` is optional. It appears near the top of the digest when advisory
  OpenAI steps are skipped because of a hard-to-miss operational problem such as
  exhausted quota.
- `Executive Summary` is generated from the selected topics and ranked post set.
- `Picked Topics` is the core section and is capped to the top six topics.
- `Emerging Themes` is derived from the most common insight tags for the run.
- `Watch Next` is optional. It uses OpenAI suggestions when available; otherwise
  it falls back to up to three insights marked `new`. If neither exists, the
  section is omitted.
