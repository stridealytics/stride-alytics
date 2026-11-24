FROM python:3.15.2-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv sync

COPY . .

CMD ["python", "app/main.py"]
