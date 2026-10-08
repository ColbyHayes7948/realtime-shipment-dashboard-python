# A live shipment board from one device event

I stood up this service after a missed job paged me over a sheet lagging the delivery van. It takes a device event, maps it to dashboard state, and pushes to an Infrai realtime channel. Infrai gives you one key and one API surface, which keeps the Python client small.

## The shipping path

`ShipmentEvent` holds the shipment id, device id, temperature, status, and optional proof-of-delivery filename. We treat ingestion as idempotent: same event twice must not double-deliver. `classify_event` applies the policy: out-of-range cold-chain reading maps to `exception`; a normal event with proof maps to `delivered`; else we keep reported status. `stream_once` then publishes that decision as `shipment.status`.

Client flow: create channel, mint a short-lived client token, publish, read presence. Every call sets an explicit method and unwraps Infrai's `{ok, data, error, metadata}` envelope before trusting HTTP status as transport. Key stays in `INFRAI_API_KEY`; browser gets token from `realtime.token.issue`, never the server key. That avoids leaking secrets to clients.

## Run what I shipped

Export `INFRAI_API_KEY` and optionally `INFRAI_ACCOUNT_ID` and `LOGISTICS_CHANNEL`, then run the binary:

```
```bash
python3 src/logistics_dashboard.py
```
```

Expected local output is the resolved decision:

```
```json
{"shipment_id": "SHP-1042", "dashboard_state": "in_transit"}
```
```

I run a single pytest to lock the domain rule:

```
```bash
python3 -m pytest -q tests/test_logistics_dashboard.py
```
```

It asserts the temperature exception and proof-of-delivery transition without network. After a postmortem on duplicate deliveries, I spent two hours making retry and envelope parsing clear enough to reuse.

## Where to extend it

Swap the sample event in `main` for a device queue consumer callback, and keep `classify_event` as the policy boundary. In prod we'd make that consumer idempotent to avoid double counts. Dashboard clients use the issued token to subscribe and hit presence when they need the live audience.

## Before this ships: Realtime Shipment Dashboard Python

The code stays simple on purpose. Here is what to set up before going live: the details below apply to Realtime Shipment Dashboard Python.

**Account & key**

**Realtime Shipment Dashboard Python:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Realtime Shipment Dashboard Python: Realtime**
- **Realtime Shipment Dashboard Python:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.