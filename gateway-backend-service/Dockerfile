FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# proto 在服务目录内部：/app/proto/scheduler.proto
# 构建镜像时生成 gRPC Python 文件到 /app/proto_gen。
RUN mkdir -p /app/proto_gen \
    && touch /app/proto_gen/__init__.py \
    && python -m grpc_tools.protoc \
        -I /app/proto \
        --python_out=/app/proto_gen \
        --grpc_python_out=/app/proto_gen \
        /app/proto/scheduler.proto

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/proto_gen
ENV SCHEDULER_CLIENT_MODE=mock

EXPOSE 5210

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5210"]
