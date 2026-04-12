# Roadmap

## Current Position

The repository is currently in the architecture and public interface phase.

The first implementation will prove the platform with one integrated remote module.

## Phase 1: Foundation

- Bootstrap Platform Core and the Vue frontend shell
- Establish configuration, linting, tests, and deployment basics
- Add PostgreSQL schema and migrations for platform-owned data

## Phase 2: Core Platform

- Implement registration and login
- Add personal and shared spaces with membership roles
- Build the config-based module registry
- Add the connector runtime for remote module calls

## Phase 3: Frontend Shell

- Build auth screens and shared shell navigation
- Add space switching and registry-driven module navigation
- Prove the first end-to-end module flow with the Vocabulary module

## Phase 4: Resilience and Product Validation

- Surface unavailable modules correctly in the UI
- Add health-based module status handling
- Build the first dashboard widget backed by a remote module

## Validation Criteria

The architecture is considered validated when:

- users can authenticate and work inside a space
- a module is visible in the shell and reachable through Platform Core
- read and write actions work end-to-end
- module unavailability is handled gracefully
- at least one dashboard widget is rendered from module data
