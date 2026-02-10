---
description: Execute a plan by delegating tasks to sub-agents
---

The user wants to execute a plan or set of tasks.

**User input (optional plan details):**
$input

---

**Your task:**

Execute the plan by delegating work to sub-agents using the `Task` tool.

**Execution strategy:**

1. **Analyze dependencies** — identify which tasks depend on each other and which can run in parallel.

2. **Wave execution:**
   - Group independent tasks into "waves"
   - Launch all tasks in a wave simultaneously (multiple `Task` tool calls in one message)
   - Wait for wave completion before starting dependent tasks

3. **Delegation rules:**
   - Trust sub-agent results — don't redo their work
   - Provide clear, detailed task descriptions with all necessary context
   - Each sub-agent starts fresh — include all relevant info in the prompt

4. **Final verification:**
   - After all tasks complete, launch ONE more agent to verify the combined result
   - This agent should check that changes work together correctly

**Example wave structure:**
```
Wave 1 (parallel): TaskA, TaskB, TaskC (independent)
Wave 2 (parallel): TaskD, TaskE (depend on Wave 1)
Wave 3: Final verification agent
```

**Important:**
- Maximize parallelism — if tasks CAN run in parallel, they SHOULD
- Don't do work yourself — delegate everything to sub-agents
- Keep the main conversation clean — sub-agents handle the heavy lifting
- Report final summary to the user when complete
