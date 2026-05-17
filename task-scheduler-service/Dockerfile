FROM python:3.11-slim

WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN bash scripts/gen_proto.sh

ENV SCHEDULER_HOST=0.0.0.0
ENV SCHEDULER_PORT=5300
ENV ORCHESTRATOR_TARGET=agent-orchestrator-service:5400

EXPOSE 5300
CMD ["python", "-m", "app.main"]
