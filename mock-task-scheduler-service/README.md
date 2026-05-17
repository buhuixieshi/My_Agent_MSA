# mock-task-scheduler-service

这是一个用于测试 `gateway-backend-service` 连通性的假后端。

它长期运行，模拟真实 `task-scheduler-service`：

- 接收 `CreateTask`
- 通过 `SubscribeEvents` 把事件流推回 gateway
- 最终发送 `assistant_message`，内容会回声返回前端输入

## 构建镜像

```bash
docker build -t agent/mock-task-scheduler-service:local .
```

## 部署到 K8s

```bash
kubectl apply -f k8s/mock-task-scheduler-service.yaml
```

这个 YAML 创建的 Service 名叫：

```text
task-scheduler-service
```

所以你的 `gateway-backend-service` 可以直接用：

```text
SCHEDULER_CLIENT_MODE=grpc
SCHEDULER_GRPC_TARGET=task-scheduler-service.agent.svc.cluster.local:5100
```

## gateway-backend-service 需要设置

把 gateway 的环境变量改成：

```yaml
- name: SCHEDULER_CLIENT_MODE
  value: "grpc"
- name: SCHEDULER_GRPC_TARGET
  value: "task-scheduler-service.agent.svc.cluster.local:5100"
```

## 测试链路

访问前端：

```text
http://localhost/chat.html
```

发送任意消息后，如果看到类似下面的回复，说明链路通了：

```text
Mock 后端回声测试成功。
收到用户：xxx
收到内容：你输入的内容
task_id：task-xxxx
```

链路为：

```text
frontend → gateway-backend-service → mock-task-scheduler-service
        ← gateway-backend-service ← mock-task-scheduler-service
```
