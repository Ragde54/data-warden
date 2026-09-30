# Plain Apache Airflow (no vendor distribution) with data-warden in its own virtualenv.
# Build context is the repository root:  docker compose -f airflow/docker-compose.yml build
FROM apache/airflow:3.3.2-python3.12

# A separate virtualenv keeps data-warden's dependencies away from Airflow's pinned ones.
RUN pip install --no-cache-dir "uv==0.11.7"

WORKDIR /tmp/dw
COPY --chown=airflow:0 pyproject.toml uv.lock README.md ./
COPY --chown=airflow:0 src ./src
ENV UV_PROJECT_ENVIRONMENT=/home/airflow/dw UV_LINK_MODE=copy
# Locked versions, a real (non-editable) install. --extra demo adds Faker so `seed` works here.
RUN python -m uv sync --locked --no-dev --no-editable --extra demo && rm -rf /tmp/dw

# Created here, as the airflow user, so the named volume mounted on top keeps this owner.
RUN mkdir -p /opt/airflow/history
WORKDIR /opt/airflow
