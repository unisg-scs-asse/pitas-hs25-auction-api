# PITAS HS25 Auction API Specification

This repository contains the API specification used for the PITAS auction house.

The OpenAPI document is automatically rendered to GitHub Pages.

## API Versioning

The API version is specified in the request and response payloads using a `version` field. Clients should include the `version` field in their requests, and servers should respond with the corresponding `version` field. If the implementation does not support the requested version, an HTTP error `400` shall be returned.

## Interactions

### WebSub Subscribe to Another Auction House

```mermaid
sequenceDiagram
participant subscriber as Subscriber Auction House
participant websub as WebSub Hub
participant publisher as Publisher Auction House

    subscriber->>websub: POST https://switchboard.p3k.io/
    Note over subscriber,websub: Content-Type: application/json<br/>hub.mode=subscribe<br/>hub.topic=https://publisher-auction-house-uri/auctions<br/>hub.callback=https://subscriber-auction-house-uri/callback
    websub-->>subscriber: 202 Accepted

    websub->>subscriber: GET https://subscriber-auction-house-uri/callback?hub.challenge=XYZ&hub.mode=subscribe
    Note over websub,subscriber: Intent verification with hub.challenge
    subscriber-->>websub: 200 OK<br/>Body: hub.challenge

    Note over subscriber: Subscription active, waits for notifications
```

### WebSub Publish New Auction

Each auction house must subscribe to the other auction houses, retrieve the list either via the provided RegistryService or the custom discovery method.

```mermaid
sequenceDiagram
participant auction_house as Auction House
participant websub as WebSub Hub
participant subscriber as Subscriber

    auction_house->>websub: POST https://switchboard.p3k.io/
    Note over auction_house,websub: Content-Type: application/json<br/>hub.mode=publish<br/>hub.url=https://auction-house-uri/auctions<br/>Body: AuctionPayloadDto
    websub-->>auction_house: 202 Accepted

    websub->>subscriber: POST subscriber-auction-house-uri/callback
    Note over websub,subscriber: Content-Type: application/json<br/>Body: AuctionPayloadDto
    subscriber-->>websub: 200 OK

    Note over subscriber: Process auction notification
```

### MQTT Publish New Auction

We use the public broker hive.mq, with the topic `/ch/unisg/pitas/auctions`. All groups publish and listen on the same topic.

```mermaid
sequenceDiagram
participant auction_house as Auction House
participant broker as MQTT Broker
participant subscriber as Subscriber

    auction_house->>broker: MQTT Publish /ch/unisg/pitas/auctions
    Note over auction_house,broker: Payload: AuctionPayloadDto

    broker->>subscriber: MQTT Listen /ch/unisg/pitas/auctions
    Note over broker,subscriber: Payload: AuctionPayloadDto

    Note over subscriber: Process auction notification
```

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

## Hypermedia Links Implementation

**In short**:

- Every group has the following group as entry node (eg. group1 -> group2 -> ... -> groupN -> group1)
- Each group exposes the `/discovery` endpoint which returns a list of all known nodes. Including their own node as well. See [API Spec](auction-house.yaml) for details.
- Each group is responsible to proactively maintain the list of nodes and not compute it on request.

**Assumptions**:

- Nodes stay online forever (e.g. they do not disappear). It's the responsibility of each group if they want to check if a node is still online.

**Available Relations**:

- `relation`: Indicates a generic link between resources in the hypermedia API. This relation can be used to express connections or associations between nodes or entities, where a more specific relation type is not applicable.

## Test Client

The `auction-test-client` is a lightweight test service that automatically interacts with the auction house API for testing purposes.

### Deployment

See [DOCKER_README.md](auction-test-client/DOCKER_README.md) for Docker-based deployment and usage instructions.
