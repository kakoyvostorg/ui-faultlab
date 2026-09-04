APPLICATION_FAULTS = ("save_noop", "value_corruption", "confirmation_transition_bug")


def corrupt_draft(draft: dict) -> dict:
    damaged = dict(draft)
    if damaged.get("attendees"):
        damaged["attendees"] = ["corrupted@example.invalid"]
    else:
        damaged["time"] = "09:99"
    return damaged

