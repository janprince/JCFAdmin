"""
cuid generation.

The Innerspace database is owned by Prisma, whose models declare
`@id @default(cuid())`. Prisma generates those ids in the application layer —
the columns are plain `TEXT NOT NULL` with no database default — so any row we
insert from Django has to bring its own id.

This is a Python port of cuid v1 (the version Prisma's `cuid()` emits), so ids
written by the admin are indistinguishable from ids written by the website.

Format: 'c' + timestamp + counter + fingerprint + 2 random blocks (25 chars).
"""

import os
import socket
import string
import threading
import time
from random import SystemRandom

BASE36 = string.digits + string.ascii_lowercase
BLOCK_SIZE = 4
DISCRETE_VALUES = 36 ** BLOCK_SIZE

_random = SystemRandom()
_counter = 0
_counter_lock = threading.Lock()


def _to_base36(number, pad=0):
    if number == 0:
        digits = '0'
    else:
        digits = ''
        while number:
            number, remainder = divmod(number, 36)
            digits = BASE36[remainder] + digits
    return digits.rjust(pad, '0')


def _next_counter():
    """Rolling counter so ids created in the same millisecond stay distinct."""
    global _counter
    with _counter_lock:
        value = _counter
        _counter = (_counter + 1) % DISCRETE_VALUES
    return value


def _random_block():
    return _to_base36(_random.randrange(DISCRETE_VALUES), BLOCK_SIZE)


def _fingerprint():
    """Host + process identity, so two servers never collide."""
    pid = _to_base36(os.getpid(), 2)[-2:]
    hostname = socket.gethostname()
    host_id = len(hostname) + 36 + sum(ord(char) for char in hostname)
    return pid + _to_base36(host_id, 2)[-2:]


def cuid():
    """Return a new cuid v1, matching what Prisma would have generated."""
    timestamp = _to_base36(int(time.time() * 1000))
    counter = _to_base36(_next_counter(), BLOCK_SIZE)
    return 'c' + timestamp + counter + _fingerprint() + _random_block() + _random_block()
