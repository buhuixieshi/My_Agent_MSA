FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN bash scripts/gen_proto.sh

ENV OPENVIKING_CONTEXT_GRPC_PORT=5301
ENV VIKING_DATA_DIR=/app/viking_data
ENV MOCK_VIKING=false

EXPOSE 5301

CMD ["python", "-m", "app.main"]
