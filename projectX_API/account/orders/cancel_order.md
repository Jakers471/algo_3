# Cancel an Order

**API URL:** `POST https://api.topstepx.com/api/Order/cancel`

**API Reference:** `/api/Order/cancel`

## Description

Cancel an order.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `accountId` | integer | The account ID. | Required | false |
| `orderId` | integer | The order id. | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Order/cancel' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "accountId": 465,
    "orderId": 26974
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
