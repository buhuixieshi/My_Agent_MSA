#!/usr/bin/env bash
set -e
mkdir -p app/generated
python -m grpc_tools.protoc \
  -I proto \
  --python_out=app/generated \
  --grpc_python_out=app/generated \
  proto/task_scheduler.proto \
  proto/agent_orchestrator.proto
touch app/generated/__init__.py
