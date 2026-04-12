# Module Contract

## Goal

Remote modules may use any implementation stack, but they must expose a stable contract to Platform Core.

The contract is intentionally small so simple modules can integrate quickly.

## Required Endpoints

### `GET /health`

Confirms the module is reachable and ready.

Timeout: 3 seconds. Called by Platform Core health poller every 30 seconds.

Example:

```json
{
  "status": "ok"
}
```

### `DELETE /cleanup/space/{space_id}` (Phase 2)

Deletes all domain data associated with the given space.

Called by Platform Core when a space is being deleted. This endpoint is not required in v1, but modules must persist `space_id` on all domain records from v1 to make cleanup possible when this protocol is activated.

Example response:

```json
{
  "status": "ok",
  "deleted_count": 42
}
```

If the module has no data for the given space, it must return a success response with `deleted_count: 0`.

### `GET /meta`

Returns module identity and version metadata.

Example:

```json
{
  "module_id": "vocabulary",
  "display_name": "Vocabulary",
  "description": "Vocabulary learning module",
  "api_version": "v1",
  "module_version": "0.1.0"
}
```

### `GET /capabilities`

Returns optional platform-facing capabilities.

Example:

```json
{
  "search": true,
  "activity": false,
  "widgets": ["vocabulary_summary"],
  "views": ["list", "detail", "form"]
}
```

## Required Runtime Behavior

Every module must:

- accept authenticated requests from Platform Core
- validate required platform context headers
- treat `space_id` as the data boundary
- expose read and write operations for its domain
- return normalized JSON errors
- expose `GET /capabilities` even when all optional capabilities are disabled

## Required Platform Context

Platform Core sends the following on every module request:

- `Authorization: Bearer <module_token>` — static module-specific bearer token
- `X-Platform-Token` — platform context payload containing user_id, space_id, locale, timezone, audience, issuer (signed JWT in Phase 2)
- `X-Request-Id` — unique request identifier
- `X-Correlation-Id` — groups related requests within one user action
- `X-Idempotency-Key` — unique key for state-changing requests (POST, PUT, PATCH, DELETE)

Legacy individual headers (`X-User-Id`, `X-Space-Id`, `X-Locale`, `X-Timezone`) may be sent during the migration period but must not be trusted without bearer token verification.

Modules must extract platform context from the `X-Platform-Token` payload after validating the bearer token.

## Idempotency

For state-changing requests, Platform Core sends an `X-Idempotency-Key` header with a unique UUID.

Modules should check whether the key was already processed. If yes, return the cached response. If no, execute the operation and store the key with the response for at least 24 hours.

This prevents duplicate writes when a successful operation is followed by a connector timeout.

## Security

Platform Core authenticates to each module using a dedicated internal bearer token configured on both sides (sent as `Authorization: Bearer <token>`).

Each module has its own unique token. The bearer token proves that the request comes from Platform Core.

### Module-Side Verification (v1)

Modules must:

1. Verify the `Authorization` bearer token matches the configured value.
2. Extract platform context (user_id, space_id, etc.) from the `X-Platform-Token` payload.
3. Reject requests with an invalid or missing bearer token.

Raw `X-User-Id` and `X-Space-Id` headers must not be trusted without bearer token verification.

### Phase 2: Signed JWT Verification

In Phase 2, `X-Platform-Token` becomes a signed JWT (RS256) with a 30-second TTL and an audience claim. Modules will additionally verify the JWT signature, expiry, issuer, and audience. The bearer token remains as a first layer of defense.

### Health Endpoint Authentication

Health checks (`GET /health`) must include the `Authorization: Bearer <token>` header but do not require `X-Platform-Token` JWT because there is no user context for health probes.

Health responses must be limited to `{"status": "ok"}` with no system internals.

## Response Content-Type

All module responses must use `Content-Type: application/json`.

Connectors validate the Content-Type before parsing. Non-JSON responses are treated as a module error (502).

## Error Format

All module errors must follow this shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid status transition"
  }
}
```

All error responses must use `Content-Type: application/json`.

### Standard Module Error Codes

| HTTP Status | Code | Meaning |
|-------------|------|---------|  
| 400 | `validation_error` | Input validation failed |
| 404 | `not_found` | Domain entity not found in this space |
| 409 | `conflict` | Domain state conflict (e.g., duplicate entry) |
| 422 | `domain_rule_violation` | Business rule violated |
| 500 | `internal_error` | Unexpected module error |

### Error Mapping by Platform Core

| Module Returns | Core Returns to Frontend |
|----------------|-------------------------|
| 4xx with valid error shape | Same code, wrapped in platform envelope |
| 5xx | 502 `module_error` with generic message |
| Timeout | 504 `module_timeout` |
| Unreachable (circuit open) | 503 `module_unavailable` |

## Version Semantics

- `api_version` is the module contract version used for compatibility checks
- `module_version` is the deployable application version

Compatibility decisions are based on `api_version`.

## Optional Capabilities

Modules may also expose:

- search
- activity
- widgets
- richer command or query surfaces

Optional capabilities are discovered through `GET /capabilities`, not hardcoded into Platform Core.
