FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY proto /app/proto
COPY proto_gen /app/proto_gen
COPY generate_proto.sh /app/generate_proto.sh
COPY server.py /app/server.py

RUN chmod +x /app/generate_proto.sh && /app/generate_proto.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/proto_gen
ENV PORT=5100

EXPOSE 5100

CMD ["python", "server.py"]
