# Search for Orders

**API URL:** `POST https://api.topstepx.com/api/Order/search`

**API Reference:** `/api/Order/search`

## Description

Search for orders.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `accountId` | integer | The account ID. | Required | false |
| `startTimestamp` | datetime | The start of the timestamp filter. | Required | false |
| `endTimestamp` | datetime | The end of the timestamp filter. | Optional | true |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Order/search' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "accountId": 704,
    "startTimestamp": "2025-07-18T21:00:01.268009+00:00",
    "endTimestamp": "2025-07-18T21:00:01.278009+00:00"
  }'
```

### Example Response

#### Success

```json
{
  "orders": [
    {
      "id": 36598,
      "accountId": 704,
      "contractId": "CON.F.US.EP.U25",
      "symbolId": "F.US.EP",
      "creationTimestamp": "2025-07-18T21:00:01.268009+00:00",
      "updateTimestamp": "2025-07-18T21:00:01.268009+00:00",
      "status": 2,
      "type": 2,
      "side": 0,
      "size": 1,
      "limitPrice": null,
      "stopPrice": null,
      "fillVolume": 1,
      "filledPrice": 6335.250000000,
      "customTag": null
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

#### Error

```
Error: response status is 401
```
