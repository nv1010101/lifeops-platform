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
- sending platform context
- authenticating with a module-specific bearer token
- normalizing module responses and errors
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
3. Platform Core resolves the connector for the target module.
4. The connector calls the remote module with platform context and internal authentication.
5. The module performs the domain action.
6. Platform Core returns a normalized response to the frontend.

## Platform Context

Every module-facing request includes:

- `X-User-Id`
- `X-Space-Id`
- `X-Request-Id`
- `X-Correlation-Id`
- `X-Locale`
- `X-Timezone`

This supports tracing, auditability, and space-aware behavior across modules.

## Runtime Expectations

The first release is intentionally simple:

- module registration is config-based
- module calls are synchronous
- module availability is surfaced in the UI
- modules stay visible even when temporarily unavailable

The design must still remain compatible with future async workflows, richer modules, and more advanced deployment topologies.
