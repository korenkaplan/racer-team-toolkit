from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter
from typing import Generic, TypeVar

TaskInput = TypeVar("TaskInput")
TaskOutput = TypeVar("TaskOutput")


@dataclass(frozen=True)
class TaskResult(Generic[TaskInput, TaskOutput]):
    item: TaskInput
    value: TaskOutput | None
    error: Exception | None
    elapsed_seconds: float

    @property
    def succeeded(self) -> bool:
        return self.error is None


def _execute_task(
    task: Callable[[TaskInput], TaskOutput],
    item: TaskInput,
) -> TaskResult[TaskInput, TaskOutput]:
    started = perf_counter()

    try:
        value = task(item)
    except Exception as error:
        return TaskResult(
            item=item,
            value=None,
            error=error,
            elapsed_seconds=perf_counter() - started,
        )

    return TaskResult(
        item=item,
        value=value,
        error=None,
        elapsed_seconds=perf_counter() - started,
    )


def run_tasks(
    items: Iterable[TaskInput],
    task: Callable[[TaskInput], TaskOutput],
    max_workers: int = 3,
) -> list[TaskResult[TaskInput, TaskOutput]]:
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")

    task_items = list(items)
    if not task_items:
        return []

    results: dict[int, TaskResult[TaskInput, TaskOutput]] = {}

    with ThreadPoolExecutor(max_workers=min(max_workers, len(task_items))) as executor:
        futures = {
            executor.submit(_execute_task, task, item): index
            for index, item in enumerate(task_items)
        }

        for future in as_completed(futures):
            results[futures[future]] = future.result()

    return [results[index] for index in range(len(task_items))]
