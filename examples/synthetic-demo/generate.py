"""Synthetic OpenTelemetry GenAI / Claude Code metrics.

Use when you want to populate the Sysdig dashboard without burning real
OpenAI / Anthropic credits or running Claude Code interactively.

Usage:
    # Make sure the collector is up
    docker compose up -d otelcol

    # 2 minutes of pulses, then exit
    python examples/synthetic-demo/generate.py --pulses 12 --interval 10

    # Run forever (until ctrl-c) for a long demo
    python examples/synthetic-demo/generate.py --forever

After ~30s, the panels in https://<your-region>.app.sysdig.com/#/dashboards/<id>
will start filling.
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request


def make_sum(name: str, unit: str, points: list[dict]) -> dict:
    return {
        "name": name,
        "unit": unit,
        "sum": {
            "aggregationTemporality": 2,   # CUMULATIVE
            "isMonotonic": True,
            "dataPoints": [
                {
                    "attributes": [
                        {"key": k, "value": {"stringValue": v}}
                        for k, v in p["attrs"].items()
                    ],
                    "startTimeUnixNano": str(p["start"]),
                    "timeUnixNano":      str(p["now"]),
                    ("asInt" if isinstance(p["val"], int) else "asDouble"): p["val"],
                }
                for p in points
            ],
        },
    }


def send(endpoint: str, payload: dict) -> int:
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default="http://localhost:4318/v1/metrics",
                    help="OTLP HTTP metrics endpoint (default: %(default)s)")
    ap.add_argument("--pulses", type=int, default=12,
                    help="Number of pulses to send (default: %(default)s).")
    ap.add_argument("--interval", type=float, default=10.0,
                    help="Seconds between pulses (default: %(default)s).")
    ap.add_argument("--forever", action="store_true",
                    help="Ignore --pulses and run until interrupted.")
    args = ap.parse_args()

    state = {
        "cc_token_input":         0,
        "cc_token_output":        0,
        "cc_token_cacheRead":     0,
        "cc_token_cacheCreation": 0,
        "cc_cost_opus":           0.0,
        "cc_cost_haiku":          0.0,
        "ga_input":               0,
        "ga_output":              0,
    }
    start = int(time.time() * 1e9) - 120_000_000_000

    def step():
        state["cc_token_input"]         += random.randint(100, 500)
        state["cc_token_output"]        += random.randint(200, 800)
        state["cc_token_cacheRead"]     += random.randint(5_000, 15_000)
        state["cc_token_cacheCreation"] += random.randint(50, 500)
        state["cc_cost_opus"]           += random.uniform(0.01, 0.05)
        state["cc_cost_haiku"]          += random.uniform(0.0001, 0.0005)
        state["ga_input"]               += random.randint(50, 200)
        state["ga_output"]              += random.randint(80, 250)

    def pulse() -> tuple[int, int]:
        now = int(time.time() * 1e9)
        cc_res = [
            {"key": "service.name", "value": {"stringValue": "claude-code-cli-synth"}},
            {"key": "host.arch",    "value": {"stringValue": "arm64"}},
            {"key": "os.type",      "value": {"stringValue": "darwin"}},
        ]
        ga_res = [
            {"key": "service.name", "value": {"stringValue": "ai-token-demo"}},
        ]

        def cc_pt(t, m, v):
            return {"attrs": {"type": t, "model": m}, "start": start, "now": now, "val": v}

        def cc_cost_pt(m, v):
            return {"attrs": {"model": m}, "start": start, "now": now, "val": v}

        def ga_pt(tt, v):
            return {
                "attrs": {
                    "gen_ai.system": "openai",
                    "gen_ai.request.model": "gpt-4o-mini",
                    "gen_ai.token.type": tt,
                },
                "start": start, "now": now, "val": v,
            }

        cc_payload = {"resourceMetrics": [{
            "resource": {"attributes": cc_res},
            "scopeMetrics": [{"scope": {"name": "synth"}, "metrics": [
                make_sum("claude_code.token.usage", "tokens", [
                    cc_pt("input",         "claude-opus-4-7[1m]", state["cc_token_input"]),
                    cc_pt("output",        "claude-opus-4-7[1m]", state["cc_token_output"]),
                    cc_pt("cacheRead",     "claude-opus-4-7[1m]", state["cc_token_cacheRead"]),
                    cc_pt("cacheCreation", "claude-opus-4-7[1m]", state["cc_token_cacheCreation"]),
                ]),
                make_sum("claude_code.cost.usage", "USD", [
                    cc_cost_pt("claude-opus-4-7[1m]",       state["cc_cost_opus"]),
                    cc_cost_pt("claude-haiku-4-5-20251001", state["cc_cost_haiku"]),
                ]),
            ]}],
        }]}

        ga_payload = {"resourceMetrics": [{
            "resource": {"attributes": ga_res},
            "scopeMetrics": [{"scope": {"name": "synth"}, "metrics": [
                make_sum("gen_ai.client.token.usage", "{token}", [
                    ga_pt("input",  state["ga_input"]),
                    ga_pt("output", state["ga_output"]),
                ]),
            ]}],
        }]}

        return send(args.endpoint, cc_payload), send(args.endpoint, ga_payload)

    i = 0
    try:
        while args.forever or i < args.pulses:
            i += 1
            step()
            try:
                s1, s2 = pulse()
            except urllib.error.URLError as e:
                print(f"pulse {i}: failed to reach {args.endpoint}: {e}", file=sys.stderr)
                return 2
            print(
                f"pulse {i:>3} cc={s1} ga={s2}  "
                f"opus_input={state['cc_token_input']}  "
                f"opus_cacheRead={state['cc_token_cacheRead']}  "
                f"opus_cost=${state['cc_cost_opus']:.4f}",
                flush=True,
            )
            if args.forever or i < args.pulses:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped by user", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
