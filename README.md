# LifeOps Platform

LifeOps Platform is a modular personal productivity platform built around one product surface: one dashboard, one UI shell, many remote domain modules.

## Current Status

This repository currently contains the public architecture and interface definition for the first implementation. Application code for Platform Core, the frontend shell, and reference modules will be added incrementally.

## Product Summary

LifeOps Platform is built around four parts:

- Platform Core: central backend for auth, spaces, roles, registry, connectors, and dashboard composition
- Platform Frontend Shell: single Vue application with shared navigation and module pages
- Remote Modules: independent services that own domain logic and persistence
- Connectors: Platform Core adapters that call modules and normalize their behavior

The platform is not an API gateway. It is the main product surface for users, with one UI and one access model across multiple modules.

## First Implementation Goals

- Shared auth, spaces, and roles
- Config-based module registry
- One integrated module path proved end-to-end
- Unavailable-module handling in the UI
- At least one dashboard widget backed by a remote module

## Public Docs

- [Architecture](./ARCHITECTURE.md)
- [Module Contract](./MODULE_CONTRACT.md)
- [Roadmap](./ROADMAP.md)
