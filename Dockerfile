# AEGIS API + dashboard — lightweight image (no Spark/Java).
# Spark-backed stages (detection, recovery_verifier, post_execution_data_verifier)
# are run via the CLI/orchestrator on a host with Java 17 + Hadoop winutils,
# not inside this container.

FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV AEGIS_ENV=production \
    AEGIS_PRODUCTION_EXECUTION_ENABLED=false

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
