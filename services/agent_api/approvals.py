import asyncio
import copy
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4


APPROVAL_TTL_SECONDS = 10 * 60
MAX_PENDING_APPROVALS = 100


@dataclass
class PendingApproval:
    state_json: dict
    project_id: str
    request_indexes: dict[str, int]
    created_at: float


class ApprovalStore:
    def __init__(self) -> None:
        self._items: dict[str, PendingApproval] = {}
        self._lock = asyncio.Lock()

    def _remove_expired(self, now: float) -> None:
        expired_ids = [
            approval_id
            for approval_id, item in self._items.items()
            if now - item.created_at > APPROVAL_TTL_SECONDS
        ]
        for approval_id in expired_ids:
            self._items.pop(approval_id, None)

    async def create(
        self,
        state_json: dict,
        project_id: str,
        interruption_count: int,
    ) -> tuple[str, list[str]]:
        now = monotonic()
        approval_id = uuid4().hex
        request_ids = [uuid4().hex for _ in range(interruption_count)]
        request_indexes = {
            request_id: index for index, request_id in enumerate(request_ids)
        }

        async with self._lock:
            self._remove_expired(now)
            if len(self._items) >= MAX_PENDING_APPROVALS:
                oldest_id = min(
                    self._items,
                    key=lambda item_id: self._items[item_id].created_at,
                )
                self._items.pop(oldest_id, None)

            self._items[approval_id] = PendingApproval(
                state_json=copy.deepcopy(state_json),
                project_id=project_id,
                request_indexes=request_indexes,
                created_at=now,
            )

        return approval_id, request_ids

    async def take(self, approval_id: str) -> PendingApproval | None:
        now = monotonic()
        async with self._lock:
            self._remove_expired(now)
            item = self._items.pop(approval_id, None)

        if item is None:
            return None

        return PendingApproval(
            state_json=copy.deepcopy(item.state_json),
            project_id=item.project_id,
            request_indexes=dict(item.request_indexes),
            created_at=item.created_at,
        )


approval_store = ApprovalStore()
