FROM python:3.11-slim AS runtime

# Mencegah penulisan bytecode .pyc dan memastikan output log unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Buat non-root user untuk menjalankan aplikasi
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Salin dan pasang dependensi runtime
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Salin source code backend, file dashboard, dan skrip utilitas
COPY backend/app /app/app
COPY dashboard /app/dashboard
COPY scripts /app/scripts

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# Stage test: diturunkan dari runtime untuk menjalankan test suite dengan dependensi dev
FROM runtime AS test
USER root
COPY backend/requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt
COPY backend/tests /app/backend/tests
COPY firmware/test /app/firmware/test
COPY pyproject.toml /app/pyproject.toml
USER appuser
ENV DATABASE_URL="sqlite:///:memory:" \
    APP_ENV="test" \
    JWT_SECRET="test_jwt_secret_at_least_32_chars_1234567890" \
    DASHBOARD_PASSWORD="test_password_12chars"
CMD ["pytest", "-v", "-m", "not perf"]

