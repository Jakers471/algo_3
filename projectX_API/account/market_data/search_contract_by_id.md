# Search for Contract by ID

**API URL:** `POST https://api.topstepx.com/api/Contract/searchById`

**API Reference:** `/api/Contract/searchById`

## Description

Search for contracts.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `contractId` | string | The id of the contract to search for. | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Contract/searchById' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "contractId": "CON.F.US.ENQ.H25"
  }'
```

### Example Response

#### Success

```json
{
  "contract": {
    "id": "CON.F.US.ENQ.H25",
    "name": "NQH5",
    "description": "E-mini NASDAQ-100: March 2025",
    "tickSize": 0.25,
    "tickValue": 5,
    "activeContract": false,
    "symbolId": "F.US.ENQ"
  },
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

#### Error

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Contract/searchById' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "contractId": "CON.F.US.ENQ.H25"
  }'
```
