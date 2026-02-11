# Requirements Mapping (User Request)

Status: `planned`

## Source Requirements to Scope Mapping

| Requirement | Scope |
|---|---|
| Skybox support (`sky`) and default skybox fallback | `01-runtime-world-baseline.md` |
| Launcher redesign, remove noisy menus, intuitive flow, tooltips | `02-launcher-and-runflow-redesign.md` |
| Reduce useless run options; choose settings at launch | `02-launcher-and-runflow-redesign.md` |
| Validate with `demo.map` | `05-demo-map-validation-and-rollout.md` |
| Old maps look like old renderer; enforce expected runtime behavior | `01-runtime-world-baseline.md` + `05-demo-map-validation-and-rollout.md` |
| Default fog/horizon expectation | `01-runtime-world-baseline.md` |
| Loading is too slow; speed up | `03-loading-performance-program.md` |
| MCP real-time map element creation/manipulation | `04-console-command-bus-and-mcp-realtime.md` |
| Scene search by name, pagination, filters | `04-console-command-bus-and-mcp-realtime.md` |
| Player look-direction/target introspection tool | `04-console-command-bus-and-mcp-realtime.md` |
| Everything should go through console bus, without bottleneck | `04-console-command-bus-and-mcp-realtime.md` |
| Menu elements should call console commands | `02-launcher-and-runflow-redesign.md` + `04-console-command-bus-and-mcp-realtime.md` |
| Group entities and move group together | `04-console-command-bus-and-mcp-realtime.md` |
| Live fog changes from console | `04-console-command-bus-and-mcp-realtime.md` |
| Console hints/help and Up-arrow history | `04-console-command-bus-and-mcp-realtime.md` |
| Create task system under `/tasks/myfunc/...` with dependencies | `tasks/README.md` + `tasks/myfunc/README.md` |

## Execution Order
1. `01-runtime-world-baseline.md`
2. `02-launcher-and-runflow-redesign.md` (depends on 01)
3. `03-loading-performance-program.md` (depends on 01)
4. `04-console-command-bus-and-mcp-realtime.md` (depends on 01, 02)
5. `05-demo-map-validation-and-rollout.md` (depends on 02, 03, 04)
