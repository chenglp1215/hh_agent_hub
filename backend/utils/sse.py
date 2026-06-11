import json
from typing import AsyncGenerator, Dict, Any


async def sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format a single SSE event.

    Args:
        event_type: The SSE event type (e.g., "text", "agent_call", "done")
        data: The event payload as a dictionary

    Returns:
        A formatted SSE event string
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def sse_stream(events: AsyncGenerator) -> AsyncGenerator[str, None]:
    """Wrap an async generator of events into SSE format.

    Args:
        events: An async generator yielding (event_type, data) tuples

    Yields:
        Formatted SSE event strings, ending with a "done" event
    """
    async for event_type, data in events:
        yield await sse_event(event_type, data)
    yield await sse_event("done", {"message": "stream complete"})
