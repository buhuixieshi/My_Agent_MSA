FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN bash scripts/gen_proto.sh

ENV ORCHESTRATOR_GRPC_PORT=5300

EXPOSE 5300

CMD ["python", "-m", "app.main"]
