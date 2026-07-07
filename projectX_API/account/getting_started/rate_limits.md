# Rate Limits

## Overview

The Gateway API employs a rate limiting system for all authenticated requests. Its goal is to promote fair usage, prevent abuse, and ensure the stability and reliability of the service, while clearly defining the level of performance clients can expect.

## Rate Limit Table

| Endpoint(s) | Limit |
|-------------|-------|
| `POST /api/History/retrieveBars` | 50 requests / 30 seconds |
| All other Endpoints | 200 requests / 60 seconds |

## What Happens If You Exceed Rate Limits?

If you exceed the allowed rate limits, the API will respond with an HTTP **429 Too Many Requests** error. When this occurs, you should reduce your request frequency and try again after a short delay.
