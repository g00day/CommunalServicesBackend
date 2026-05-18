FROM python:3.12-slim AS deps

WORKDIR /app

COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

FROM deps AS test

WORKDIR /app

COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt

COPY . .

CMD ["pytest", "-q"]

FROM deps AS runtime

WORKDIR /app

COPY app ./app
COPY ml ./ml
COPY req.txt ./req.txt
COPY README.md ./README.md

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
