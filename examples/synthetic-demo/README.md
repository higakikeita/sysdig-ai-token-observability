# Synthetic demo data

Populate the Sysdig dashboard without burning OpenAI / Anthropic credits or
needing Claude Code installed.

Useful for:
- Enterprise evaluators who want to see the dashboard light up in 2 minutes.
- Demos / screenshots / Qiita posts.
- Smoke-testing the OTel Collector and Sysdig Remote Write path.

## Run

```bash
# 1. Make sure the collector is up
docker compose up -d otelcol

# 2. Pulse 12 times (2 minutes of data)
python examples/synthetic-demo/generate.py

# Or run continuously
python examples/synthetic-demo/generate.py --forever
```

No external dependencies — pure stdlib.

## What it sends

| Metric | Series | Why |
|---|---|---|
| `claude_code.token.usage` (unit `tokens`) | `type ∈ {input, output, cacheRead, cacheCreation}` × model `claude-opus-4-7[1m]` | Lights the **token rate by type** and **cache hit ratio** panels |
| `claude_code.cost.usage` (unit `USD`)      | model ∈ {opus, haiku} | Lights the **cost rate** panel |
| `gen_ai.client.token.usage` (unit `{token}`) | `gen_ai.token.type ∈ {input, output}`, model `gpt-4o-mini`, service `ai-token-demo` | Lights the **GenAI rate / Input vs Output / Top services** panels |

Deltas per pulse are randomised but biased to look realistic:
- ~5-15k cacheRead vs ~50-500 cacheCreation → cache hit ratio ~0.97
- ~$0.01-0.05 / pulse for opus vs ~$0.0001-0.0005 for haiku

## Flags

```
--endpoint URL      OTLP HTTP metrics endpoint     (default: http://localhost:4318/v1/metrics)
--pulses N          Number of pulses then exit     (default: 12)
--interval SEC      Seconds between pulses         (default: 10)
--forever           Run until ctrl-c
```
