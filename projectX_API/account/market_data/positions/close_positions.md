# Close Positions

**API URL:** `POST https://api.topstepx.com/api/Position/closeContract`

**API Reference:** `/api/Position/closeContract`

## Description

Close a position.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `accountId` | integer | The account ID. | Required | false |
| `contractId` | string | The contract ID. | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Position/closeContract' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "accountId": 536,
    "contractId": "CON.F.US.GMET.J25"
  }'
```

### Example Response

#### Success

```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

#### Error

```
Error: response status is 401
```
