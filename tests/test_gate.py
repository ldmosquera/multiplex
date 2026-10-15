import asyncio

import pytest

from multiplex.gate import Gate

pytestmark = pytest.mark.asyncio


async def test_acquire_up_to_limit():
    gate = Gate(2)
    await gate.acquire()
    await gate.acquire()
    assert gate.active == 2


async def test_release_decrements_when_no_waiters():
    gate = Gate(2)
    await gate.acquire()
    assert gate.active == 1
    gate.release()
    assert gate.active == 0


async def test_acquire_blocks_beyond_limit():
    gate = Gate(1)
    await gate.acquire()
    assert gate.active == 1

    async def second():
        await gate.acquire()

    task = asyncio.ensure_future(second())
    # Give it a chance to run; it must block, not acquire.
    await asyncio.sleep(0.01)
    assert not task.done()
    assert gate.active == 1

    gate.release()
    await task
    assert gate.active == 1  # slot handed to the waiter, not decremented


async def test_fifo_ordering():
    gate = Gate(1)
    await gate.acquire()  # hold the single slot

    order = []

    async def waiter(name):
        await gate.acquire()
        order.append(name)
        gate.release()

    tasks = [asyncio.ensure_future(waiter(n)) for n in ("a", "b", "c")]
    await asyncio.sleep(0.01)  # let all three queue up in order

    # Free the slot; waiters must be served strictly in FIFO order.
    gate.release()
    await asyncio.gather(*tasks)
    assert order == ["a", "b", "c"]


async def test_release_serves_multiple_waiters_in_order():
    gate = Gate(2)
    await gate.acquire()
    await gate.acquire()  # active == 2 (full)

    order = []

    async def waiter(name):
        await gate.acquire()
        order.append(name)
        gate.release()

    tasks = [asyncio.ensure_future(waiter(n)) for n in ("a", "b")]
    await asyncio.sleep(0.01)

    gate.release()  # wakes "a"
    await asyncio.sleep(0.01)
    gate.release()  # wakes "b"
    await asyncio.gather(*tasks)
    assert order == ["a", "b"]
    assert gate.active == 0


async def test_cancelled_waiter_does_not_leak_slot():
    gate = Gate(1)
    await gate.acquire()  # hold the slot

    async def waiter():
        await gate.acquire()

    task = asyncio.ensure_future(waiter())
    await asyncio.sleep(0.01)  # now waiting in the deque
    assert len(gate._waiting) == 1

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(gate._waiting) == 0  # stale waiter removed

    # Releasing now must decrement (no phantom waiter to hand the slot to).
    gate.release()
    assert gate.active == 0