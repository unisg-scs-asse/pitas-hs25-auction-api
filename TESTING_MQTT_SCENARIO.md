# Case 1 – External Auction Workflow Test

This guide verifies the full workflow where our scheduler cannot allocate an internal worker, triggers our **internal** auction house, publishes the auction via MQTT, receives a bid from the **external** auction house emulator via HTTP, and patches the job in PITAS-Jobs once the external worker returns the result.

## Prerequisites
- Local Docker Desktop running
- Project repo checked out (`pitas-hs25-group3`)
- The official test client repo available at `../pitas-hs25-auction-api`
- No VPN/network blockers for HiveMQ (`broker.hivemq.com`)
- Ensure the internal auction house advertises a host the external emulator can reach. For local runs we set `auction.house.uri=http://host.docker.internal:8090/` (see `pitas-auction-house/src/main/resources/application-local.properties`). When recreating this test elsewhere, adjust that property and the emulator’s `AUCTION_HOUSE_BASE_URL` to the correct host (e.g., your VM HTTPS URL) so bids and callbacks succeed.

## 1. Boot the PITAS stack (then stop workers)
Bring everything up once so MongoDB and dependent services initialize correctly. Afterward stop the worker services to simulate a fully booked cluster (so the internal auction house must escalate externally).

```bash
docker compose -f docker-compose-local.yml up -d --build
# once everything is healthy:
docker compose -f docker-compose-local.yml stop work-calculator work-weather work-groupidentifier
```

Tail the auction-house logs:
```bash
docker compose -f docker-compose-local.yml logs -f pitas-auction-house
```

## 2. Run the automated external auction house
> The test client joins the `pitas-hs25-group3_pitas-network` Docker network so it can talk directly to the internal services. Make sure the local stack from step 1 is running (which creates the network) before starting the emulator.
From `../pitas-hs25-auction-api`:
```bash
cd ../pitas-hs25-auction-api
docker compose -f docker-compose.test-v1.yaml up --build
```
This container emulates the external auction house: it subscribes to `ch/unisg/pitas/auctions/#`, filters job types defined via `SUPPORTED_JOB_TYPES`, bids on every discovered auction using REST (`POST /auctions/{id}/bid`), and posts job results back to `/auctions/{id}/job`. Because it shares the Docker network, all URLs inside MQTT payloads (`http://pitas-auction-house:8090/...`, `http://pitas-jobs:8081/...`) resolve without extra host aliases.

## 3. Create a job the idle worker **cannot** execute
Back in `pitas-hs25-group3`, create a `computation` job so the scheduler fails (because the workers are offline):
```bash
curl -i -X POST http://localhost:8081/jobs/ \
  -H 'Content-Type: application/job+json' \
  -d '{
        "jobName": "delegated-001",
        "jobType": "computation",
        "inputData": "21+21"
      }'
# observe the Location header -> https://pitas-jobs.../jobs/{jobId}
```
The endpoint does not return a body; the `Location` header is the canonical job URI. Copy it because the scheduler and any manual auction launch must pass this exact `jobUri` to `/auctions/`.

> **Note:** inside Docker the header points to `http://pitas-jobs:8081/...`. This host is only resolvable from other containers. When curling from your laptop, replace `pitas-jobs` with `localhost`; when another container (scheduler, auction house, emulator) uses the URI, leave it unchanged.

## 4. Observe the scheduler emitting the auction (or trigger manually)
Tail the scheduler logs to see the `InternalWorkerNotFound` event:
```bash
docker compose -f docker-compose-local.yml logs -f scheduler | rg --line-buffered "InternalWorkerNotFound"
```
When triggered, the scheduler POSTs to the internal auction house (`http://pitas-auction-house:8090/auctions/` from inside Docker) with the job URI.

If you want to trigger the auction manually from the host (e.g., when the scheduler is disabled), POST directly to the internal auction house using that job URI (replace `pitas-auction-house` with `localhost` when calling from your laptop):
```bash
curl -X POST http://localhost:8090/auctions/ \
  -H 'Content-Type: application/json' \
  -H 'X-API-Version: 1' \
  -d '{
        "jobUri": "http://localhost:8081/jobs/{jobId}",
        "jobType": "computation",
        "deadline": 15000
      }'
```
The auction house rejects payloads that omit `jobUri`, so make sure you substitute the exact URL from step 3.

## 5. Verify MQTT publish and external bid
In the internal auction-house logs look for:
- `Publishing auction ... via MQTT`
- `Received auction started event via MQTT` (from the test client)

The external emulator should log:
- `MQTT: discovered auction …` followed by `Placing bid on auction …`

You can also tap the broker directly:
```bash
mqtt sub -h broker.hivemq.com -t "ch/unisg/pitas/auctions/#"
```

## 6. Confirm HTTP winner notification & job execution
After the auction deadline expires (default 10–15s):
1. Auction house logs `Bidder test-client acknowledged win for auction …`.
2. Emulator logs `Received job assignment …` and `Sending job result …`.
3. Internal auction house logs `Job executed for auction …` followed by `Updated delegated job …`.

## 7. Validate PITAS-Jobs reflects the external result
Fetch the job state using the URI from step 3:
```bash
curl -H 'Accept: application/job+json' http://localhost:8081/jobs/{jobId}
```
Expected response fields:
- `jobStatus`: `EXECUTED`
- `serviceProvider`: `auction-test-client`
- `outputData`: the canned message from the emulator (“Cloudflare is having…”)

## 8. Clean up
```bash
docker compose -f docker-compose-local.yml down
cd ../pitas-hs25-auction-api && docker compose -f docker-compose.test-v1.yaml down
```

## VM Variant
Once DNS/Traefik works, repeat the workflow against the deployed stack:
1. SSH into the VM, ensure auction house runs with `SPRING_PROFILES_ACTIVE=mqtt`.
2. Run the emulator locally with `AUCTION_HOUSE_BASE_URL=https://pitas-auction-house.<IP>.asse.scs.unisg.ch` and `MQTT_BROKER=broker.hivemq.com`.
3. Create a job via the public `pitas-jobs` endpoint, observe the same log sequence, and verify the remote `/auctions/{id}/job` callbacks succeed (look for `Updated delegated job https://…`).

Following these steps guarantees every part of the Case 1 scenario (worker shortage → scheduler fallback → MQTT publish → HTTP bid → remote execution → PITAS-Jobs patch) is exercised and logged.
