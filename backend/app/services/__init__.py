"""Business-logic services for the StrideAlytics API.

One file per backend resource. Services must be HTTP‑agnostic — they take
plain Python types and return plain Python types / Pydantic models. The
endpoint layer (``app.api.v1.endpoints.*``) is the only place that imports
``fastapi`` and translates requests into service calls.

This package deliberately re-exports nothing: the scheduler imports single modules
(``app.services.greeks``, ``app.services.screener``) and must not drag in auth, the database
or FastAPI. Import from the submodule you need.
"""
