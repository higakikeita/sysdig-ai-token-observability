# Architecture

```
                ┌──────────────────────────────┐
                │ AI / Coding Agents           │
                │  ─ Claude Code (native OTLP) │
                │  ─ Python OpenAI demo        │
                │  ─ Cursor / other (via proxy)│
                └──────────────┬───────────────┘
                               │ OTLP gRPC :4317
                               ▼
                ┌──────────────────────────────┐
                │ OpenTelemetry Collector       │
                │  ─ receivers: otlp            │
                │  ─ processors: batch          │
                │  ─ exporters:                 │
                │      prometheus  :9464        │  ← Sysdig Agent can scrape
                │      prometheusremotewrite/sysdig │ ← direct push
                └──────────────┬────────────────┘
                               │ HTTPS
                               ▼
                ┌──────────────────────────────┐
                │ Sysdig Monitor                │
                │  ─ PromQL Explore             │
                │  ─ Dashboards                 │
                │  ─ Alerts                     │
                └──────────────────────────────┘
```

## Why two exporters?

| Path | When to use |
|---|---|
| `prometheusremotewrite/sysdig` (direct push) | Local / laptop / lightweight VM. No Sysdig Agent required. Fastest path to first datapoint. |
| `prometheus` scrape endpoint | Production Kubernetes where Sysdig Agent is already running and you want one place to manage scrape jobs. |

Both can run simultaneously; pick whichever fits the target environment.

## Metric flow

1. Application/Agent emits OTLP metrics with semantic-convention names
   (`gen_ai.client.token.usage`, `claude_code.token.usage`).
2. OTel Collector normalises and forwards.
3. Sysdig ingests as Prometheus-compatible metrics:
   - dots in the name become underscores
   - counters get a `_total` suffix
   - resource attributes become labels (requires `resource_to_telemetry_conversion: enabled: true`)

## Security posture

- The collector terminates the OTLP connection inside the trust boundary
  (loopback by default in compose; Pod-local in Kubernetes).
- Outbound traffic is HTTPS to `*.app.sysdig.com` only.
- The Sysdig **Monitor** API token (NOT Secure token) is the only secret;
  scope it to a service account with metric-write only.
- No customer prompt content is captured — only counter values and
  low-cardinality labels (model, token type, service name).
