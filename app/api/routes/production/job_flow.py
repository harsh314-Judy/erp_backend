_TRANSITIONS = {
    ("pending", "start"): "in_progress",
    ("pending", "cancel"): "cancelled",
    ("in_progress", "stage_continues"): "in_progress",
    ("in_progress", "revert"): "in_progress",
    ("in_progress", "await_approval"): "awaiting_approval",
    ("in_progress", "cancel"): "cancelled",
    ("awaiting_approval", "revert"): "in_progress",
    ("awaiting_approval", "approve"): "completed",
}


def next_status(current: str, event: str) -> str:
    try:
        return _TRANSITIONS[(current, event)]
    except KeyError as exc:
        raise ValueError(f"A {current.replace('_', ' ')} job cannot {event.replace('_', ' ')}") from exc
