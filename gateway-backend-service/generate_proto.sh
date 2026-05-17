#!/usr/bin/env sh
set -eu

mkdir -p proto_gen
touch proto_gen/__init__.py

python -m grpc_tools.protoc \
  -I proto \
  --python_out=proto_gen \
  --grpc_python_out=proto_gen \
  proto/scheduler.proto

echo "generated proto_gen/scheduler_pb2.py and proto_gen/scheduler_pb2_grpc.py"
