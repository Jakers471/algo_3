# Search for Account

**API URL:** `POST https://api.topstepx.com/api/Account/search`

**API Reference:** `/api/Account/search`

## Description

Search for accounts.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `onlyActiveAccounts` | boolean | Whether to filter only active accounts. | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Account/search' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "onlyActiveAccounts": true
  }'
```

### Example Response

#### Success

```json
{
  "accounts": [
    {
      "id": 1,
      "name": "TEST_ACCOUNT_1",
      "balance": 50000,
      "canTrade": true,
      "isVisible": true
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
