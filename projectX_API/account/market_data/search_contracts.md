# Search for Contracts

**API URL:** `POST https://api.topstepx.com/api/Contract/search`

**API Reference:** `/api/Contract/search`

## Description

Search for contracts.

**Note:** The response returns up to 20 contracts at a time.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `searchText` | string | The name of the contract to search for. | Required | false |
| `live` | boolean | Whether to search for contracts using the sim/live data subscription. | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Contract/search' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "live": false,
    "searchText": "NQ"
  }'
```

### Example Response

#### Success

```json
{
  "contracts": [
    {
      "id": "CON.F.US.ENQ.U25",
      "name": "NQU5",
      "description": "E-mini NASDAQ-100: September 2025",
      "tickSize": 0.25,
      "tickValue": 5,
      "activeContract": true,
      "symbolId": "F.US.ENQ"
    },
    {
      "id": "CON.F.US.MNQ.U25",
      "name": "MNQU5",
      "description": "Micro E-mini Nasdaq-100: September 2025",
      "tickSize": 0.25,
      "tickValue": 0.5,
      "activeContract": true,
      "symbolId": "F.US.MNQ"
    },
    {
      "id": "CON.F.US.NQG.Q25",
      "name": "QGQ5",
      "description": "E-Mini Natural Gas: August 2025",
      "tickSize": 0.005,
      "tickValue": 12.5,
      "activeContract": true,
      "symbolId": "F.US.NQG"
    },
    {
      "id": "CON.F.US.NQM.U25",
      "name": "QMU5",
      "description": "E-Mini Crude Oil: September 2025",
      "tickSize": 0.025,
      "tickValue": 12.5,
      "activeContract": true,
      "symbolId": "F.US.NQM"
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
