# PITAS HS25 Auction API Specification

This repository contains the API specification used for the PITAS auction house.

The OpenAPI document is automatically rendered to GitHub Pages.

## API Versioning

The used API version is passed with each request as the header `X-API-Version`. If the implementation does not support the version, HTTP error `400` shall be returned

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
