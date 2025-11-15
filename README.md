# PITAS HS25 Auction API Specification

This repository contains the API specification used for the PITAS auction house.

The OpenAPI document is automatically rendered to GitHub Pages.

## API Versioning
The used API version is passed with each request as the header `X-API-Version`. If the implementation does not support the version, HTTP error `400` shall be returned

## Shared Job Type
In order to allow groups to test the system easily, a shared job type is defined which every group shall implement.

| jobType | inputData | outputData |
| --- | --- | --- |
| `testJob` | string | `Testing: {string}` |

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
