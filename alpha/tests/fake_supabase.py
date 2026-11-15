"""A small in-memory stand-in for the Supabase client (only what the pipeline uses).

Every write is recorded in ``client.log`` as ``(op, table, detail)`` so tests can assert that
nothing was deleted or rewritten.
"""

from __future__ import annotations

import re


class FakeQuery:
    def __init__(self, client: "FakeSupabase", table: str):
        self.c, self.t = client, table
        self.op = "select"
        self.payload = None
        self.filters: list[tuple] = []
        self.lo, self.hi = 0, None

    # builders
    def select(self, *_):
        self.op = "select"
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows
        return self

    def update(self, values):
        self.op, self.payload = "update", values
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def neq(self, col, val):
        self.filters.append(("neq", col, val))
        return self

    def like(self, col, pattern):
        self.filters.append(("like", col, pattern))
        return self

    def in_(self, col, vals):
        self.filters.append(("in", col, list(vals)))
        return self

    def range(self, lo, hi):
        self.lo, self.hi = lo, hi
        return self

    # evaluation
    def _match(self, row: dict) -> bool:
        for kind, col, val in self.filters:
            cell = row.get(col)
            if kind == "eq" and cell != val:
                return False
            if kind == "neq" and cell == val:
                return False
            if kind == "in" and cell not in val:
                return False
            if kind == "like":
                rx = "^" + re.escape(val).replace("%", ".*") + "$"
                if cell is None or not re.match(rx, str(cell)):
                    return False
        return True

    def execute(self):
        if self.c.fail_on == self.op:
            raise RuntimeError(f"simulated {self.op} failure")
        rows = self.c.tables.setdefault(self.t, [])
        if self.op == "select":
            hits = [dict(r) for r in rows if self._match(r)]
            hi = len(hits) if self.hi is None else self.hi + 1
            return _Resp(hits[self.lo : hi])
        if self.op == "insert":
            new = self.payload if isinstance(self.payload, list) else [self.payload]
            rows.extend(dict(r) for r in new)
            self.c.log.append(("insert", self.t, len(new)))
        elif self.op == "update":
            hit = [r for r in rows if self._match(r)]
            for r in hit:
                r.update(self.payload)
            self.c.log.append(("update", self.t, len(hit)))
        elif self.op == "delete":
            keep = [r for r in rows if not self._match(r)]
            self.c.log.append(("delete", self.t, len(rows) - len(keep)))
            self.c.tables[self.t] = keep
        return _Resp([])


class _Resp:
    def __init__(self, data):
        self.data = data


class FakeSupabase:
    def __init__(self, fail_on: str | None = None):
        self.tables: dict[str, list[dict]] = {}
        self.log: list[tuple] = []
        self.fail_on = fail_on

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def ops(self, op: str) -> list[tuple]:
        return [e for e in self.log if e[0] == op]
