# ADR 0001: Use Panda3D for the Initial MVP Prototype

Date: 2026-02-07

## Context
We need a fast way to get a runnable 3D prototype in Python to iterate on movement and level grayboxing, without the extra abstraction of a higher-level engine wrapper.

## Decision
Use **Panda3D** directly for the initial MVP prototype.

## Consequences
- Pros: direct access to engine primitives, clearer control over the render loop and scene graph, fewer "magic" layers.
- Cons: more boilerplate than wrapper engines; we will build our own conventions and utilities.

