import asyncio
import collections


class Gate:
    """Admits up to ``limit`` units of work concurrently, FIFO by request order.

    Callers ``await acquire()`` before starting a unit of work and call
    ``release()`` when it finishes. Requests beyond the limit block until a
    slot frees, served in the exact order they were made.

    Unlike ``asyncio.Semaphore`` (which gives no ordering guarantee for its
    waiters), this keeps a FIFO queue so admission order is deterministic.
    """

    def __init__(self, limit):
        assert limit > 0
        self.limit = limit
        self._active = 0
        self._waiting = collections.deque()

    @property
    def active(self):
        return self._active

    async def acquire(self):
        if self._active < self.limit:
            self._active += 1
            return
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._waiting.append(future)
        try:
            await future
        except asyncio.CancelledError:
            # We were cancelled while waiting (e.g. the box was closed on quit).
            # Drop our stale waiter so a later release() doesn't hand a slot to a
            # dead task and leak the active count.
            try:
                self._waiting.remove(future)
            except ValueError:
                pass
            raise

    def release(self):
        if self._waiting:
            # Hand the slot straight to the next waiter; the active count is
            # unchanged (one unit finished, one is starting).
            self._waiting.popleft().set_result(None)
        else:
            self._active -= 1