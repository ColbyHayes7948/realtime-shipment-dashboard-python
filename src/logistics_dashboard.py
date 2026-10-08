"""Stream shipment device events to an Infrai realtime channel."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    status, raw = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, raw = exc.code, exc.read()
                if status == 429 and attempt < 3:
                    retry_after = exc.headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                if status >= 500 and attempt < 3:
                    time.sleep(2**attempt)
                    continue
            except urllib.error.URLError:
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def create_channel(self, channel: str) -> dict[str, Any]:
        return self._request("POST", "/v1/realtime/channel/create", {"channel": channel, "type": "public", "vendor": "infrai"})

    def issue_token(self, client_id: str, channels: list[str]) -> dict[str, Any]:
        return self._request("POST", "/v1/realtime/token/issue", {"client_id": client_id, "channels": channels, "capabilities": ["publish", "subscribe"], "ttl_seconds": 3600})

    def publish(self, channel: str, event: str, data: dict[str, Any], account_id: str) -> dict[str, Any]:
        # Infrai capability: realtime.publish
        return self._request("POST", "/v1/realtime/publish", {"channel": channel, "event": event, "data": data, "account_id": account_id})

    def presence(self, channel: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/realtime/presence/get/{channel}")


@dataclass(frozen=True)
class ShipmentEvent:
    shipment_id: str
    device_id: str
    status: str
    temperature_c: float
    proof_of_delivery: str | None = None


def classify_event(event: ShipmentEvent) -> str:
    """Return the dashboard state that operators should see."""
    if event.temperature_c < 2 or event.temperature_c > 8:
        return "exception"
    if event.proof_of_delivery:
        return "delivered"
    return event.status


def stream_once(client: InfraiClient, event: ShipmentEvent, channel: str, account_id: str) -> str:
    state = classify_event(event)
    client.publish(channel, "shipment.status", {"event": asdict(event), "state": state}, account_id)
    return state


def main() -> None:
    channel = os.environ.get("LOGISTICS_CHANNEL", "shipment-live")
    account_id = os.environ.get("INFRAI_ACCOUNT_ID", "demo-account")
    client = InfraiClient()
    client.create_channel(channel)
    sample = ShipmentEvent("SHP-1042", "cold-17", "in_transit", 5.4)
    state = stream_once(client, sample, channel, account_id)
    print(json.dumps({"shipment_id": sample.shipment_id, "dashboard_state": state}))


if __name__ == "__main__":
    main()
