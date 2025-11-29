# Docker Test Setup

This directory contains Docker configurations for testing the auction house API endpoints.

## Test Clients

### 1. Discovery Test Client (`test_discovery.py`)

- One-time test execution
- Tests GET and POST `/discovery` endpoints
- Validates response formats
- Exits with success/failure code

### 2. Auction Test Client (`test_rest.py`)

- Continuous service
- Automatically polls for auctions
- Bids on testJob auctions
- Executes jobs when won
- Tests auction and bidding endpoints

## Docker Files

- `Dockerfile.rest` - Rest Auction test client (continuous service)
- `Dockerfile.discovery` - Discovery test client (one-time execution)
- `docker-compose.test.yaml` - Unified compose file with profiles

## Running Tests

### Discovery Endpoint Tests (One-time)

```bash
# Run discovery tests with default settings
docker compose -f docker-compose.test.yaml --profile discovery-test up --build

# Clean up after tests
docker compose -f docker-compose.test.yaml --profile discovery-test down
```

### Auction Test Client (Continuous)

```bash
# Run auction test client
docker compose -f docker-compose.test.yaml --profile auction-test up --build

# Run in background
docker compose -f docker-compose.test.yaml --profile auction-test up -d --build

# View logs
docker compose -f docker-compose.test.yaml --profile auction-test logs -f

# Stop the client
docker compose -f docker-compose.test.yaml --profile auction-test down
```

### Run Both Test Clients

```bash
# Run all test services
docker compose -f docker-compose.test.yaml --profile discovery-test --profile auction-test up --build

# Note: discovery-test will exit after completion, auction-test continues running
```
