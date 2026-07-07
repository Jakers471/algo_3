# Place an Order

**API URL:** `POST https://api.topstepx.com/api/Order/place`

**API Reference:** `/api/Order/place`

## Description

Place an order.

## Parameters

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `accountId` | integer | The account ID. | Required | false |
| `contractId` | string | The contract ID. | Required | false |
| `type` | integer | The order type:<br>1 = Limit<br>2 = Market<br>4 = Stop<br>5 = TrailingStop<br>6 = JoinBid<br>7 = JoinAsk | Required | false |
| `side` | integer | The side of the order:<br>0 = Bid (buy)<br>1 = Ask (sell) | Required | false |
| `size` | integer | The size of the order. | Required | false |
| `limitPrice` | decimal | The limit price for the order, if applicable. | Optional | true |
| `stopPrice` | decimal | The stop price for the order, if applicable. | Optional | true |
| `trailPrice` | decimal | The trail price for the order, if applicable. | Optional | true |
| `customTag` | string | An optional custom tag for the order. Must be unique across the account. | Optional | true |
| `stopLossBracket` | object | Stop loss bracket configuration. | Optional | true |
| `takeProfitBracket` | object | Take profit bracket configuration. | Optional | true |

## Bracket Objects

### stopLossBracket

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `ticks` | integer | Number of ticks for stop loss | Required | false |
| `type` | integer | Type of stop loss bracket. Uses same OrderType enum values:<br>1 = Limit<br>2 = Market<br>4 = Stop<br>5 = TrailingStop<br>6 = JoinBid<br>7 = JoinAsk | Required | false |

### takeProfitBracket

| Name | Type | Description | Required | Nullable |
|------|------|-------------|----------|----------|
| `ticks` | integer | Number of ticks for take profit | Required | false |
| `type` | integer | Type of take profit bracket. Uses same OrderType enum values:<br>1 = Limit<br>2 = Market<br>4 = Stop<br>5 = TrailingStop<br>6 = JoinBid<br>7 = JoinAsk | Required | false |

## Example Usage

### Example Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Order/place' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "accountId": 465,
    "contractId": "CON.F.US.DA6.M25",
    "type": 2,
    "side": 1,
    "size": 1,
    "limitPrice": null,
    "stopPrice": null,
    "trailPrice": null,
    "customTag": null,
    "stopLossBracket": {
      "ticks": 10,
      "type": 1
    },
    "takeProfitBracket": {
      "ticks": 20,
      "type": 1
    }
  }'
```

### Example Response

#### Success

```json
{
  "orderId": 9056,
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

#### Error

```
Error: response status is 401
```
