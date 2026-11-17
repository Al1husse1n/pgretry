"""Decorator for declarative whole-transaction execution in PGRetry.

This module provides the `@transaction` decorator which wraps async functions and
delegates execution directly to `TransactionRunner`.
"""

from __future__ import annotations

import functools
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    ParamSpec,
    Set,
    TypeVar,
    overload,
)

from pgretry.instrumentation.logging import TransactionLogger
from pgretry.instrumentation.metrics import MetricsCollector
from pgretry.postgres.diagnostics import DiagnosticCollector
from pgretry.retry.backoff import RandomFloatGenerator
from pgretry.retry.classifier import SQLStateExtractor
from pgretry.retry.policy import RetryPolicy
from pgretry.transaction.runner import (
    SleepCallable,
    TransactionAdapter,
    TransactionRunner,
)

P = ParamSpec("P")
R = TypeVar("R")


def _build_policy(
    policy: Optional[RetryPolicy],
    *,
    max_attempts: Optional[int],
    base_delay: Optional[float],
    max_delay: Optional[float],
    backoff_factor: Optional[float],
    jitter: Optional[bool],
    retryable_sqlstates: Optional[Set[str]],
) -> RetryPolicy:
    """Resolve a RetryPolicy from an explicit policy or shorthand keyword overrides."""
    if policy is not None:
        return policy

    overrides: dict[str, Any] = {
        key: value
        for key, value in (
            ("max_attempts", max_attempts),
            ("base_delay", base_delay),
            ("max_delay", max_delay),
            ("backoff_factor", backoff_factor),
            ("jitter", jitter),
            ("retryable_sqlstates", retryable_sqlstates),
        )
        if value is not None
    }
    return RetryPolicy(**overrides)


def _wrap_with_runner(
    target_fn: Callable[P, Awaitable[R]],
    runner: TransactionRunner,
) -> Callable[P, Awaitable[R]]:
    """Wrap an async callable so every call executes via `runner.run(...)`."""

    @functools.wraps(target_fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return await runner.run(functools.partial(target_fn, *args, **kwargs))

    setattr(wrapper, "__pgretry_runner__", runner)
    return wrapper


@overload
def transaction(
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]: ...


@overload
def transaction(
    *,
    policy: Optional[RetryPolicy] = None,
    adapter: Optional[TransactionAdapter] = None,
    runner: Optional[TransactionRunner] = None,
    logger: Optional[TransactionLogger] = None,
    metrics: Optional[MetricsCollector] = None,
    diagnostics: Optional[DiagnosticCollector] = None,
    max_attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    backoff_factor: Optional[float] = None,
    jitter: Optional[bool] = None,
    retryable_sqlstates: Optional[Set[str]] = None,
    sleep_func: Optional[SleepCallable] = None,
    random_func: Optional[RandomFloatGenerator] = None,
    custom_extractor: Optional[SQLStateExtractor] = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]: ...


def transaction(
    fn: Optional[Callable[P, Awaitable[R]]] = None,
    *,
    policy: Optional[RetryPolicy] = None,
    adapter: Optional[TransactionAdapter] = None,
    runner: Optional[TransactionRunner] = None,
    logger: Optional[TransactionLogger] = None,
    metrics: Optional[MetricsCollector] = None,
    diagnostics: Optional[DiagnosticCollector] = None,
    max_attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    backoff_factor: Optional[float] = None,
    jitter: Optional[bool] = None,
    retryable_sqlstates: Optional[Set[str]] = None,
    sleep_func: Optional[SleepCallable] = None,
    random_func: Optional[RandomFloatGenerator] = None,
    custom_extractor: Optional[SQLStateExtractor] = None,
) -> Any:
    """Decorator to execute an async function with automatic whole-transaction retries.

    Delegates completely to TransactionRunner, guaranteeing that the wrapped function
    is re-executed from the very beginning upon encountering a retryable PostgreSQL error.

    Can be used with or without arguments:
        @transaction
        async def transfer_funds(account_from, account_to, amount):
            ...

        @transaction(max_attempts=3, base_delay=0.1)
        async def create_order(user_id, item_id):
            ...

    Args:
        fn: The async function to decorate (when used without parentheses).
        policy: Optional custom RetryPolicy.
        adapter: Optional TransactionAdapter to manage begin/commit/rollback boundaries.
        runner: Optional pre-configured TransactionRunner instance.
        logger: Optional TransactionLogger.
        metrics: Optional MetricsCollector.
        diagnostics: Optional DiagnosticCollector.
        max_attempts: Shorthand override for policy max_attempts.
        base_delay: Shorthand override for policy base_delay.
        max_delay: Shorthand override for policy max_delay.
        backoff_factor: Shorthand override for policy backoff_factor.
        jitter: Shorthand override for policy jitter.
        retryable_sqlstates: Shorthand override for policy retryable_sqlstates.
        sleep_func: Async sleep callable for backoff delays (useful for testing).
        random_func: Injectable random generator for backoff jitter.

    Returns:
        The wrapped async function.
    """
    effective_runner = (
        runner
        if runner is not None
        else TransactionRunner(
            policy=_build_policy(
                policy,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor,
                jitter=jitter,
                retryable_sqlstates=retryable_sqlstates,
            ),
            adapter=adapter,
            logger=logger,
            metrics=metrics,
            diagnostics=diagnostics,
            sleep_func=sleep_func,
            random_func=random_func,
            custom_extractor=custom_extractor,
        )
    )

    if fn is not None:
        return _wrap_with_runner(fn, effective_runner)

    def decorator(target_fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        return _wrap_with_runner(target_fn, effective_runner)

    return decorator


transactional = transaction
