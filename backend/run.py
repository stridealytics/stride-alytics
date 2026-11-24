import uvicorn

from app.utils.asyncio_utils import psycopg_loop_factory


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        loop=psycopg_loop_factory() or "auto",
    )


if __name__ == "__main__":
    main()
