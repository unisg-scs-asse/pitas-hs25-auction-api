# PITAS HS25 Auction API Specification

This repository contains the API specification used for the PITAS auction house.

The OpenAPI document is automatically rendered to GitHub Pages.

## API Versioning

The used API version is passed with each request as the header `X-API-Version`. If the implementation does not support the version, HTTP error `400` shall be returned

## Shared Job Type

In order to allow groups to test the system easily, a shared job type is defined which every group shall implement.

| jobType   | inputData | outputData          |
| --------- | --------- | ------------------- |
| `testJob` | string    | `Testing: {string}` |

### Example

#### Request

```
{
    "jobType": "testJob",
    "inputData": "abcde"
}
```

#### Reply

```
{
    "outputData": "Testing: abcde"
}
```

## Test Client

The `auction-test-client` is a lightweight test service that automatically discovers open auctions by polling the auction house GET-API, places bids on them, and executes jobs when it wins. It tracks which auctions it has already bid on to avoid duplicate bids.

### Deployment

To deploy the test client using Docker Compose:

```bash
docker compose -f docker-compose.test-v1.yaml up --build -d
```

The test client will start polling the auction house at the configured interval (default: 5 seconds, configurable via `POLL_INTERVAL_SECONDS` environment variable) and automatically bid on any new open auctions it discovers.
