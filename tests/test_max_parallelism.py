import asyncio
import os
import subprocess

import pytest
from multiplex import to_iterator
from multiplex.actions import Activate
from multiplex.gate import Gate
from multiplex.ipc import Client

pytestmark = pytest.mark.asyncio


def _ctx(gate):
    return {
        "gate": gate,
        "socket_path": "",
        "stream_id": "test",
        "cwd": None,
        "env": None,
        "handle": None,
    }


async def test_gated_command_yields_activate_then_output():
    gate = Gate(4)
    it = await to_iterator("echo hello", context=_ctx(gate))
    assert it.inner_type == "async_process"

    items = []
    async for item in it.iterator:
        items.append(item)

    assert isinstance(items[0], Activate)
    assert any("hello" in str(i) for i in items)
    assert gate.active == 0  # slot released after completion


async def test_gated_command_defers_spawn_until_admitted():
    gate = Gate(1)
    it1 = await to_iterator("sleep 0.2; echo one", context=_ctx(gate))
    it2 = await to_iterator("echo two", context=_ctx(gate))

    # it1 takes the single slot on its first step (which also spawns it).
    first1 = await it1.iterator.__anext__()
    assert isinstance(first1, Activate)
    assert gate.active == 1

    # it2 starts but must block on the gate while it1 holds the slot.
    first2 = asyncio.ensure_future(it2.iterator.__anext__())
    await asyncio.sleep(0.05)
    assert not first2.done()  # still waiting to be admitted

    # Finish it1 -> frees the slot, which is handed to it2.
    async for _ in it1.iterator:
        pass
    assert gate.active == 1  # transferred to it2, not decremented

    first2_result = await first2
    assert isinstance(first2_result, Activate)
    async for _ in it2.iterator:
        pass
    assert gate.active == 0


async def test_non_command_sources_not_gated(tmp_path):
    # A file:// source has no subprocess, so it must run even with a full gate.
    path = tmp_path / "f.txt"
    path.write_text("static")
    gate = Gate(1)
    await gate.acquire()  # hold the only slot
    it = await to_iterator(f"file://{path}", context=_ctx(gate))
    items = []
    async for item in it.iterator:
        items.append(item)
    assert items == ["static"]
    assert gate.active == 1  # the file source never touched the gate


@pytest.mark.skipif("os.environ.get('MULTIPLEX_SOCKET_PATH')", reason="Running in demo")
async def test_cli_max_parallelism_smoke(tmpdir):
    output_dir = tmpdir / "output"
    socket_echo = tmpdir / "socket_loc"
    output_dir.mkdir()
    cmd = (
        f"mp -P 1 'echo 1' 'echo 2' 'echo $MULTIPLEX_SOCKET_PATH > {socket_echo}' "
        f"-o {output_dir}"
    )
    master, slave = os.openpty()
    proc = await asyncio.subprocess.create_subprocess_shell(
        cmd,
        stdin=slave,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    await asyncio.sleep(0.5)
    socket_path = socket_echo.read_text("utf-8").strip()
    client = Client(socket_path)
    await client.save()
    await client.quit()
    await proc.wait()
    output_dir = output_dir.listdir()[0]
    listing = output_dir.listdir(sort=True)
    texts = [f.read_text("utf-8").strip() for f in listing]
    assert "1" in texts
    assert "2" in texts