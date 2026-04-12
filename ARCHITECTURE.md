# Architecture

## Overview

LifeOps Platform is a modular application with one user-facing product surface and multiple remote domain modules.

The architecture is split into four parts:

- Platform Core
- Platform Frontend Shell
- Remote Modules
- Connectors

## Platform Core

Platform Core is the central backend service.

It owns:

- authentication
- users
- spaces
- memberships and roles
- module registry
- connector runtime
- unified UI-facing API
- dashboard composition
- notifications and activity aggregation

It does not own module business logic.

## Platform Frontend Shell

The frontend is a single Vue application.

It owns:

- login and registration flows
- top-level navigation
- space switching
- shared layout
- dashboard rendering
- module pages inside the shell

The main product UI lives here, not inside remote modules.

## Remote Modules

Each module is an independent backend service with its own domain logic and data.

Examples:

- vocabulary learning
- job tracking
- task management

Modules may use any stack as long as they satisfy the platform contract.

## Connectors

Connector code lives inside Platform Core.

Each connector is responsible for:

- resolving the target module
- checking the circuit breaker state before calling
- sending platform context via `X-Platform-Token` header
- authenticating with a module-specific bearer token
- enforcing timeout limits on outbound calls
- normalizing module responses and errors
- recording success or failure in the circuit breaker
- hiding module-specific transport details from the rest of the platform

## Ownership Boundaries

Platform Core owns platform concerns.

Remote modules own:

- domain entities
- domain rules
- domain workflows
- domain persistence

This boundary is strict. Platform Core does not reach into module databases, and modules do not depend on Platform Core internals.

## Collaboration Model

The system is multi-user and space-aware.

Core rules:

- every user gets a personal space
- users may also belong to shared spaces
- module data belongs to a space
- access is controlled through memberships and roles

Initial roles:

- admin
- member
- viewer

## Request Flow

The first implementation uses a synchronous flow:

1. The frontend calls Platform Core.
2. Platform Core authenticates the user and resolves the current space.
3. Platform Core checks the user role in that space.
4. Platform Core resolves the connector for the target module.
5. The connector checks the circuit breaker state for this module.
6. If the circuit is open, the connector returns an immediate 503 failure.
7. The connector calls the remote module with platform context headers and a bearer token.
8. The module verifies the bearer token and performs the domain action.
9. The connector normalizes the response or error.
10. Platform Core returns a normalized response to the frontend.

### Timeout Budget

Every segment of the request chain has a time limit:

- frontend to Core: 15 seconds
- Core to module via connector: 10 seconds
- module internal processing: should complete within 8 seconds
- health check poll: 3 seconds

If a module does not respond within the connector timeout, the connector records a failure, the circuit breaker updates its state, and Core returns a 504 timeout error to the frontend.

### Circuit Breaker

Each connector maintains a circuit breaker per module:

- Closed: requests flow normally, failures are counted
- Open: requests are rejected immediately without calling the module
- Half-Open: one probe request is allowed to test recovery

Parameters for the first implementation:

- failure threshold: 5 failures within 60 seconds
- open duration: 30 seconds
- probe: GET /health

When the circuit is open, the connector returns 503 with error code `module_unavailable` without network I/O.

### Circuit Breaker Startup Behavior (Recommended)

On Platform Core startup, circuits should begin in HALF-OPEN state rather than CLOSED. The first interaction with each module is a health probe; only after a successful probe does the circuit transition to CLOSED. This prevents a burst of domain requests against modules whose health has not been confirmed after a Core restart.

## Platform Context

Every module-facing request includes:

- `Authorization: Bearer <module_token>` — module-specific bearer token
- `X-Platform-Token` — platform context payload (user_id, space_id, locale, timezone, audience, issuer)
- `X-Request-Id`
- `X-Correlation-Id`
- `X-Idempotency-Key` — for state-changing requests (POST, PUT, PATCH, DELETE)

In v1, `X-Platform-Token` carries a plain context payload. Modules must validate the bearer token before trusting context claims. In Phase 2, `X-Platform-Token` becomes a signed JWT with cryptographic verification.

This supports tracing, auditability, and space-aware behavior across modules.

## Inter-Service Security

Platform Core authenticates to each module using a module-specific internal bearer token configured on both sides (sent as `Authorization: Bearer <token>`).

The bearer token proves that the request comes from Platform Core. Each module has its own unique token.

Platform Core also sends platform context (user_id, space_id, locale, timezone) via the `X-Platform-Token` header. In v1, this is a plain context payload. Modules must validate the bearer token before trusting any context claims.

### Phase 2: Signed Inter-Service JWT

In Phase 2, `X-Platform-Token` will become a signed JWT (RS256, asymmetric RSA) with a 30-second TTL and an audience claim scoped to the target module. This upgrade provides cryptographic proof of origin and prevents header spoofing even if a bearer token is compromised.

The v1 design is forward-compatible: the `X-Platform-Token` header and context structure remain the same, only the signing and verification are added in Phase 2.

Phase 2 will also introduce key rotation with dual-key support (`current` + `previous`) and optional JWKS discovery (`GET /.well-known/jwks.json`).

## Idempotency Protocol

For all state-changing requests forwarded to modules (POST, PUT, PATCH, DELETE), Platform Core must generate and include an `X-Idempotency-Key` header with a unique UUID.

Modules should check whether the key was already processed. If yes, return the cached response. If no, execute the operation and store the key with the response for at least 24 hours.

This prevents duplicate data creation when a module writes successfully but the response is lost due to a connector timeout.

## Space Cleanup Protocol (Phase 2)

When space deletion is implemented, Platform Core must coordinate cleanup across all registered modules.

Design:

1. Platform Core soft-deletes the space.
2. Platform Core sends a cleanup request to every registered module connector.
3. Each module deletes domain data for the given space_id.
4. Platform Core tracks cleanup status per module.
5. If a module is unavailable, cleanup is retried when the module recovers.
6. The space is permanently deleted only after all modules confirm cleanup.

Modules must persist `space_id` on all domain records from v1, so cleanup is possible when this protocol is activated.

## User Deletion (Phase 2)

User account deletion depends on the space cleanup protocol. When both are implemented:

- block deletion if the user is the sole admin in any shared space
- remove memberships from shared spaces (module data stays under space ownership)
- trigger personal space cleanup
- soft-delete the user record after cleanup completes

Detailed protocol is defined in Phase 2 scope.

## Graceful Shutdown

On SIGTERM, Platform Core must:

1. Stop accepting new HTTP requests.
2. Allow in-flight requests up to 30 seconds to complete.
3. Stop the health poller.
4. Not start new cleanup or retry operations.
5. Log shutdown initiation and completion.

## Runtime Expectations

The first release is intentionally simple:

- module registration is config-based
- module calls are synchronous
- module availability is surfaced in the UI
- modules stay visible even when temporarily unavailable

The design must still remain compatible with future async workflows, richer modules, and more advanced deployment topologies.
