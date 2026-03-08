"""
持久化适配器：实现领域端口 IRecordApplier、IDuplicateChecker、ISessionStore、IQueryRunner、IEditDeleteRunner。
"""

from src.infra.persistence.mysql_record_applier import MySQLRecordApplier
from src.infra.persistence.mysql_duplicate_checker import MySQLDuplicateChecker
from src.infra.persistence.mysql_session_store import (
    MySQLSessionStore,
    MySQLUserSession,
    PendingConfirm,
)
from src.infra.persistence.mysql_query_runner import MySQLQueryRunner
from src.infra.persistence.mysql_edit_delete_runner import MySQLEditDeleteRunner

__all__ = [
    "MySQLRecordApplier",
    "MySQLDuplicateChecker",
    "MySQLSessionStore",
    "MySQLUserSession",
    "PendingConfirm",
    "MySQLQueryRunner",
    "MySQLEditDeleteRunner",
]
