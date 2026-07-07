# Placing Your First Order

This documentation outlines the process for placing your first order using our API. To successfully execute an order, you must have an active trading account associated with your user. Follow the steps below to retrieve your account details, browse available contracts, and place your order.

## Step 1: Retrieve Active Accounts

To initiate the order process, you must first retrieve a list of active accounts linked to your user. This step is essential for confirming your account status before placing an order.

**API URL:** `POST https://api.topstepx.com/api/Account/search`

**API Reference:** `/api/Account/search`

### Request

```json
{
  "onlyActiveAccounts": true
}
```

### Response

```json
{
  "accounts": [
    {
      "id": 1,
      "name": "TEST_ACCOUNT_1",
      "canTrade": true,
      "isVisible": true
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

Save the `id` of the account you want to use for placing orders. This will be used in Step 3.

## Step 2: Retrieve Available Contracts

To place an order, you need to retrieve a list of available contracts. This step allows you to browse through the contracts that can be traded.

**API URL:** `POST https://api.topstepx.com/api/Contract/available`

**API Reference:** `/api/Contract/available`

### Request

```json
{
  "live": true
}
```

### Response

```json
{
  "contracts": [
    {
      "id": "CON.F.US.BP6.U25",
      "name": "6BU5",
      "description": "British Pound (Globex): September 2025",
      "tickSize": 0.0001,
      "tickValue": 6.25,
      "activeContract": true,
      "symbolId": "F.US.BP6"
    }
    // Additional contracts...
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

Save the `id` of the contract on which you would like to place an order. This will be used in Step 3.

## Step 3: Place Your Order

Now that you have the account ID and a list of available contracts, you can place your order. Use the following endpoint to submit your order request.

**API URL:** `POST https://api.topstepx.com/api/Order/place`

**API Reference:** `/api/Order/place`

### Request

```json
{
  "accountId": 1,                     // Replace with your actual account ID
  "contractId": "CON.F.US.BP6.U25",   // Replace with the contract ID you want to trade
  "type": 2,                          // Market order
  "side": 1,                          // Ask (sell)
  "size": 1                           // Size of the order
}
```

### Response

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
