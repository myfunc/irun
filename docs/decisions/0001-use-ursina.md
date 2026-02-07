# ADR 0001: Use Ursina for the Initial Prototype

Date: 2026-02-07

## Context
We need a fast way to get a runnable 3D prototype in Python to iterate on movement and level grayboxing.

## Decision
Use **Ursina** as the initial engine/runtime for the prototype.

## Consequences
- Pros: quick bootstrap, Python-native iteration, simple scene setup.
- Cons: dependency footprint (Panda3D underneath), engine constraints may appear later.

