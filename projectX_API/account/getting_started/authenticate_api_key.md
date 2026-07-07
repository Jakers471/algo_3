# Authenticate (with API key)

We utilize JSON Web Tokens to authenticate all requests sent to the API. This process involves obtaining a session token, which is required for future requests.

## Step 1

To begin, ensure you have the following:

- An API key obtained from your firm. If you do not have these credentials, please contact your firm.
- The connection URLs, obtained [here](../getting_started/connection_urls.md).

## Step 2

**API URL:** `POST https://api.topstepx.com/api/Auth/loginKey`

**API Reference:** `/api/Auth/loginKey`

### cURL Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Auth/loginKey' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json' \
  -d '{
    "userName": "string",
    "apiKey": "string"
  }'
```

## Step 3

Process the API response, and make sure the result is Success (0), then store your session token in a safe place. This session token will grant full access to the Gateway API.

### Response

```json
{
  "token": "your_session_token_here",
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```
