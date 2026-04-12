# Module Contract

## Goal

Remote modules may use any implementation stack, but they must expose a stable contract to Platform Core.

The contract is intentionally small so simple modules can integrate quickly.

## Required Endpoints

### `GET /health`

Confirms the module is reachable and ready.

Example:

```json
{
  "status": "ok"
}
```

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

Platform Core sends these headers on every module request:

- `X-User-Id`
- `X-Space-Id`
- `X-Request-Id`
- `X-Correlation-Id`
- `X-Locale`
- `X-Timezone`

Modules may reject requests that do not provide this context.

## Security

Platform Core authenticates to each module with a dedicated internal bearer token configured on both sides.

The first implementation keeps this model intentionally simple and explicit.

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
