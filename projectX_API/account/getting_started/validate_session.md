# Validate Session

Once you have successfully authenticated, session tokens are only valid for 24 hours.

If your token has expired, you must re-validate it to receive a new token.

## Validate Token

**API URL:** `POST https://api.topstepx.com/api/Auth/validate`

**API Reference:** `/api/Auth/validate`

To validate your token, you must make a POST request to the endpoint referenced above.

### cURL Request

```bash
curl -X 'POST' \
  'https://api.topstepx.com/api/Auth/validate' \
  -H 'accept: text/plain' \
  -H 'Content-Type: application/json'
```

### Response

```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null,
  "newToken": "NEW_TOKEN"
}
```
