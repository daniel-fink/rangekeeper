"""Private batch worker process: it solves one leaf for each request, until input ends.

``_parallel`` starts it in a new interpreter, with the import path of the caller.
The first line on stdin is a ``Setup``; each later line is a leaf and its view.
The worker writes one line for each, in order. The lines go to a private copy of
stdout, and stdout itself goes to stderr, so that a message from an extension
cannot break the protocol.

The worker's own solver worker (``backends/_process.py``) closes when this
process exits. When the caller ends, stdin ends, so this process exits too.
"""

import os
import signal
import sys
from typing import IO

from rangekeeper.execution import _boundary, _parallel


def _setup(line: str) -> _parallel.Session | _parallel.Refused:
    """Return the Session of a Setup line, or why this process cannot make one."""
    try:
        return _parallel.start_session(_boundary.decode(line))
    except Exception as error:  # Unpickling runs the code of an extension.
        return _parallel.Refused(reason=f"{type(error).__name__}: {error}")


def _solve(
    line: str, session: _parallel.Session
) -> _parallel.Solved | _parallel.Raised:
    """Return the result of one leaf, or the error that ended it."""
    leaf, view = _boundary.decode(line)
    try:
        return _parallel.solve_leaf(
            leaf,
            view=view,
            config=session.config,
            backend=session.backend,
            resolver=session.resolver,
        )
    except Exception as error:  # The caller raises it, as a sequential solve does.
        return _parallel.raised(error)


def serve(requests: IO[str], responses: IO[str]) -> None:
    """Answer the Setup line, then each leaf line, until the requests end."""
    session = None
    for line in requests:
        reply: object
        if session is None:
            reply = _setup(line)
            if isinstance(reply, _parallel.Session):
                session, reply = reply, None
        else:
            reply = _solve(line, session)
        responses.write(_boundary.encode(reply) + "\n")
        responses.flush()
        if isinstance(reply, _parallel.Refused):
            return


def main() -> None:
    """Serve the requests on stdin. The caller owns the lifetime of this process."""
    # The caller ends this process; an interrupt reaches the caller alone.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    responses = os.fdopen(os.dup(1), "w", encoding="ascii")
    os.dup2(2, 1)
    _parallel.enter_worker()
    serve(sys.stdin, responses)
