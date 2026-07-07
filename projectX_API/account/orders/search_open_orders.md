# Search for Open Orders

**API URL:** `POST https://api.topstepx.com/api/Order/searchOpen`

**API Reference:** `/api/Order/searchOpen`

## Description

Search for open orders.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `accountId` | integer | The account ID. | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Order/searchOpen' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "accountId": 212
  }'
```

### Example Response

#### Success

```json
{
  "orders": [
    {
      "id": 26970,
      "accountId": 212,
      "contractId": "CON.F.US.EP.M25",
      "creationTimestamp": "2025-04-21T19:45:52.105808+00:00",
      "updateTimestamp": "2025-04-21T19:45:52.105808+00:00",
      "status": 1,
      "type": 4,
      "side": 1,
      "size": 1,
      "limitPrice": null,
      "stopPrice": 5138.000000000,
      "filledPrice": null
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
