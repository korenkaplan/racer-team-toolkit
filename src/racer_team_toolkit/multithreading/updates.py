"""Deliver worker events on the calling (UI) thread until all work finishes."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from typing import TypeVar

Update = TypeVar("Update")
Result = TypeVar("Result")


def run_with_updates(
    operation: Callable[[Callable[[Update], None]], Result],
    on_update: Callable[[Update], None],
    refresh: Callable[[], None] = lambda: None,
) -> Result:
    """Run a batch off-thread; drain its final events before returning/raising.

    The operation must join its workers before returning. Only this caller
    invokes on_update and refresh, so workers never touch terminal renderers.
    Qt callers can instead forward the same operation's events through signals.
    """
    updates: Queue[Update] = Queue()
    with ThreadPoolExecutor(max_workers=1) as coordinator:
        future = coordinator.submit(operation, updates.put)
        while True:
            try:
                update = updates.get(timeout=0.1)
            except Empty:
                if future.done():
                    # Recheck the queue after observing completion: an event may
                    # have arrived between the timeout and the done() check.
                    while True:
                        try:
                            on_update(updates.get_nowait())
                        except Empty:
                            break
                    refresh()
                    return future.result()
            else:
                on_update(update)
            refresh()
