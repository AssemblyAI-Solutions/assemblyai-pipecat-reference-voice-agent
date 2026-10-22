---
name: add-a-tool
description: Give the voice agent a new ability by adding a tool that the LLM can call, such as looking something up in an API or database, booking, checking an order or transferring, with per-call state and tests. Use when the agent needs to fetch data or take an action, or when replacing the example get_current_time tool with real ones.
---

# Add a tool

A tool in `src/bot.py` has three parts: a plain function that does the work, an entry in `TOOL_FUNCTIONS`, and a schema in `TOOLS`, which is what the LLM sees. `get_current_time` is the example.

```python
def check_order(order_number: str, detail: str) -> str:
    order = ORDERS.get(order_number)
    if order is None:
        raise ToolError(
            "No order has that number. Read it back to the caller and ask them to check it."
        )
    return f"Order {order.number} is {order.status}."


TOOL_FUNCTIONS = {f.__name__: f for f in (get_current_time, check_order)}

TOOLS = ToolsSchema(
    standard_tools=[
        ...,
        FunctionSchema(
            "check_order",
            "Look up one of the caller's orders.",
            properties={
                "order_number": {"type": "string", "description": "As the caller read it out"},
                "detail": {"type": "string", "enum": ["status", "items"]},
            },
            required=["order_number", "detail"],
            handler=_run_tool,
        ),
    ]
)
```

## Rules

- **Keep the function free of Pipecat code,** so the tests can call it directly.
- **Describe it for the LLM** in the schema: one line on what it does, and every property. Use `"enum"` for fixed choices, so the LLM can only pass valid ones.
- **Return a sentence or two of plain text.** It's turned into speech; no JSON, lists or markdown.
- **Raise `ToolError` with a recovery hint** when something goes wrong; `call_tool` hands it to the LLM, which passes it on.
- **For an API,** make the function `async`, `await` it in `call_tool`, and give the request a timeout. Keep credentials in `.env.local` (and `.env.example`, empty).
- **Keep per-call state out of the LLM's hands.** Who the user is, or which order they mean, goes in a state object rather than arguments the LLM repeats: pass `app_resources=CallState()` to `PipelineWorker(...)`, read `params.app_resources` in `_run_tool`, and pass it to the function.
- **Tell the agent when to use it.** Add a line to `INSTRUCTIONS` about what the tool is for and when to call it. Update the "What you do" line too.
- **Log IDs, not personal details.**

## Test it

Add a test to `tests/test_bot.py`:

```python
async def test_checks_an_order(assistant, gateway):
    turn = await assistant.hear("Where's my order 4 1 2 7?")
    assert turn.tool_calls[0][0] == "check_order"
    await judge(gateway, turn.reply, intent="Tells the user the order's status.")
```

Use a fake of the API in tests so they don't depend on a live system. Run `uv run pytest` twice; an LLM doesn't answer the same way every time.

If the agent now has a clear purpose, also rewrite `INSTRUCTIONS` and `GREETING` for it, and remove `get_current_time` if it doesn't belong.
