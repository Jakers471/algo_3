# Modify an Order

**API URL:** `POST https://api.topstepx.com/api/Order/modify`

**API Reference:** `/api/Order/modify`

## Description

Modify an open order.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `accountId` | integer | The account ID. | Required | false |
| `orderId` | integer | The order id. | Required | false |
| `size` | integer | The size of the order. | Optional | true |
| `limitPrice` | decimal | The limit price for the order, if applicable. | Optional | true |
| `stopPrice` | decimal | The stop price for the order, if applicable. | Optional | true |
| `trailPrice` | decimal | The trail price for the order, if applicable. | Optional | true |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Order/modify' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "accountId": 465,
    "orderId": 26974,
    "size": 1,
    "limitPrice": null,
    "stopPrice": 1604,
    "trailPrice": null
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
