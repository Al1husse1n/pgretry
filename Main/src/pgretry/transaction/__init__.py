"""Transaction management and execution layer for PGRetry.

Provides:
- TransactionRunner: Central execution engine for whole-transaction retries (runner.py)
- TransactionAdapter & NullTransactionAdapter: Protocols for transaction boundaries (runner.py)
- TransactionResult: Result metadata container (runner.py)
- TransactionContext & AttemptRecord: Execution context and attempt history (context.py)
- get_current_context(): Active context accessor (context.py)
- @transaction & @transactional: Declarative retry decorators (decorator.py)
"""

from pgretry.transaction.context import (
    AttemptRecord,
    TransactionContext,
    get_current_context,
)
from pgretry.transaction.decorator import (
    transaction,
    transactional,
)
from pgretry.transaction.runner import (
    NullTransactionAdapter,
    TransactionAdapter,
    TransactionResult,
    TransactionRunner,
)

__all__ = [
    "TransactionRunner",
    "TransactionAdapter",
    "NullTransactionAdapter",
    "TransactionResult",
    "TransactionContext",
    "AttemptRecord",
    "get_current_context",
    "transaction",
    "transactional",
]
