"""Minimal demo: emit OpenTelemetry GenAI token-usage metrics for one OpenAI call.

Run:
    pip install -r requirements.txt
    export OPENAI_API_KEY=sk-...
    python app.py
"""

import os
import sys

from openai import OpenAI
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "ai-token-demo")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def main() -> int:
    resource = Resource.create({"service.name": SERVICE_NAME})
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True),
        export_interval_millis=5000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    meter = metrics.get_meter("ai-token-demo")
    token_counter = meter.create_counter(
        "gen_ai.client.token.usage",
        unit="{token}",
        description="GenAI token usage (OpenTelemetry semantic convention)",
    )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "user", "content": "Reply with one short sentence about observability."},
        ],
    )
    usage = resp.usage
    base_attrs = {
        "gen_ai.system": "openai",
        "gen_ai.request.model": MODEL,
        "gen_ai.response.model": resp.model,
    }
    token_counter.add(usage.prompt_tokens,     {**base_attrs, "gen_ai.token.type": "input"})
    token_counter.add(usage.completion_tokens, {**base_attrs, "gen_ai.token.type": "output"})

    print(f"model={resp.model} input={usage.prompt_tokens} output={usage.completion_tokens}")
    print(resp.choices[0].message.content)

    # PeriodicExportingMetricReader.shutdown() flushes the last batch.
    metrics.get_meter_provider().shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
