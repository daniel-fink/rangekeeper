"""The parent side of a reusable worker process, with a deadline on each request.

A ``Worker`` is one child process that answers each JSON request line with one
JSON response line, in order. ``Workers`` keeps at most one idle worker, so that
the solves of a session reuse one process:

- a worker that has ended, that another process started, or that wrote more than
  ``STDERR_LIMIT`` bytes to stderr is not reused; the next request starts a new
  one;
- a request that passes its deadline, or that ends with an exception, ends its
  worker;
- the idle worker closes at interpreter exit.

The worker's stderr goes to a temporary file that the parent reads only after
the worker has ended, so that the parent and the worker never share a file
position.
"""

import os
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import IO

from rangekeeper.execution.errors import NumericalError

# The characters of the worker's stderr that a failure keeps, from the end.
TAIL = 2000
# A worker that wrote more bytes than this to stderr is not reused.
STDERR_LIMIT = 1 << 20
# The seconds that an ending worker has to exit before it is killed.
GRACE = 5.0


def _exchange(process: subprocess.Popen[str], *, line: str, reply: list[str]) -> None:
    """Write one request line and read one response line; an empty line at EOF."""
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(line + "\n")
        process.stdin.flush()
        reply.append(process.stdout.readline())
    except (OSError, ValueError):
        # The worker ended, or the parent closed the pipes to end it.
        reply.append("")


class Worker:
    """One child process that answers one JSON line for each JSON line it reads."""

    def __init__(
        self,
        *,
        process: subprocess.Popen[str],
        stderr: IO[bytes],
        role: str = "solver worker",
    ) -> None:
        self.process, self.stderr, self.role = process, stderr, role
        self.owner = os.getpid()
        # The size of stderr after the last response; a failure keeps what follows.
        self.mark = 0

    @classmethod
    def start(cls, command: Sequence[str], *, role: str = "solver worker") -> "Worker":
        """Start a worker process; its stderr goes to a temporary file.

        ``role`` names the worker in the error of a worker that ends.
        """
        stderr = tempfile.TemporaryFile()
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                text=True,
                encoding="utf-8",
            )
        except BaseException:
            stderr.close()
            raise
        return cls(process=process, stderr=stderr, role=role)

    @property
    def usable(self) -> bool:
        """Return whether the worker can take another request."""
        return (
            self.owner == os.getpid()
            and self.process.poll() is None
            and not self.stderr.closed
            and os.fstat(self.stderr.fileno()).st_size <= STDERR_LIMIT
        )

    def request(self, line: str, *, deadline: float) -> str | None:
        """Send one request line and return the response line.

        Return None when the monotonic ``deadline`` passes first; the worker is
        then ended. Raise NumericalError, with the exit code and the end of
        stderr, when the worker ends without a response.
        """
        reply: list[str] = []
        exchange = threading.Thread(
            target=_exchange,
            args=(self.process,),
            kwargs={"line": line, "reply": reply},
            daemon=True,
        )
        exchange.start()
        exchange.join(max(0.0, deadline - time.monotonic()))
        if exchange.is_alive():
            self.end()
            exchange.join(GRACE)
            return None
        if not reply or not reply[0].strip():
            raise self.exited()
        self.mark = os.fstat(self.stderr.fileno()).st_size
        return reply[0]

    def exited(self) -> NumericalError:
        """Wait for the ended worker; return the error with its exit code and stderr."""
        code = self._wait()
        self.stderr.seek(self.mark)
        tail = self.stderr.read().decode("utf-8", errors="replace")[-TAIL:]
        self._release()
        return NumericalError(f"{self.role} exited {code}: {tail}")

    def close(self) -> None:
        """End the worker when its input closes; kill it after ``GRACE`` seconds."""
        if self.owner != os.getpid():
            # A forked process holds a copy of the parent's worker; leave it.
            return
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        self._wait()
        self._release()

    def end(self) -> None:
        """Kill the worker and reap it."""
        if self.owner != os.getpid():
            return
        self.process.kill()
        self._wait()
        self._release()

    def _wait(self) -> int:
        """Return the exit code; kill the worker if it does not exit in time."""
        try:
            return self.process.wait(GRACE)
        except subprocess.TimeoutExpired:
            self.process.kill()
            return self.process.wait()

    def _release(self) -> None:
        """Close the pipes and the stderr file of an ended worker."""
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        self.stderr.close()


class Workers:
    """At most one idle worker for reuse, and a new worker when none is idle."""

    def __init__(self, command: Callable[[], Sequence[str]]) -> None:
        self.command = command
        self.idle: Worker | None = None
        self.lock = threading.Lock()

    @contextmanager
    def lease(self) -> Iterator[Worker]:
        """Lend a worker for one request.

        A normal exit keeps the worker for the next request when it is usable.
        An exception ends it.
        """
        with self.lock:
            worker, self.idle = self.idle, None
        if worker is None or not worker.usable:
            if worker is not None:
                worker.close()
            worker = Worker.start(self.command())
        try:
            yield worker
        except BaseException:
            worker.end()
            raise
        with self.lock:
            if self.idle is None and worker.usable:
                self.idle, worker = worker, None
        if worker is not None:
            worker.close()

    def close(self) -> None:
        """Close the idle worker."""
        with self.lock:
            worker, self.idle = self.idle, None
        if worker is not None:
            worker.close()
