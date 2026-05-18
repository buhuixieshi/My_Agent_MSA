FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY proto /app/proto
COPY proto_gen /app/proto_gen
COPY generate_proto.sh /app/generate_proto.sh
COPY app.py /app/app.py
COPY schemas.py /app/schemas.py
COPY sse_hub.py /app/sse_hub.py
COPY scheduler_client.py /app/scheduler_client.py

RUN sed -i 's/\r$//' /app/generate_proto.sh && \
    chmod +x /app/generate_proto.sh && \
    /app/generate_proto.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/proto_gen
ENV SCHEDULER_CLIENT_MODE=grpc
ENV SCHEDULER_GRPC_TARGET=task-scheduler-service.agent.svc.cluster.local:5100

EXPOSE 5210

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5210"]