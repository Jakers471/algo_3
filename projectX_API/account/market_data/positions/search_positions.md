# Search for Positions

**API URL:** `POST https://api.topstepx.com/api/Position/searchOpen`

**API Reference:** `/api/Position/searchOpen`

## Description

Search for open positions.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `accountId` | integer | The account ID. | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Position/searchOpen' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "accountId": 536
  }'
```

### Example Response

#### Success

```json
{
  "positions": [
    {
      "id": 6124,
      "accountId": 536,
      "contractId": "CON.F.US.GMET.J25",
      "creationTimestamp": "2025-04-21T19:52:32.175721+00:00",
      "type": 1,
      "size": 2,
      "averagePrice": 1575.750000000
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
