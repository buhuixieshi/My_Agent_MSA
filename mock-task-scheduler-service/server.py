import asyncio
import os
import uuid
from dataclasses import dataclass
from typing import Dict, Set

import grpc

try:
    from proto_gen import scheduler_pb2, scheduler_pb2_grpc
except ImportError:
    import scheduler_pb2
    import scheduler_pb2_grpc


@dataclass
class StoredTask:
    task_id: str
    user_id: str
    session_id: str
    channel: str
    content: str
    status: str = "queued"
    waiting: int = 0
    error: str = ""


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, subscriber_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[subscriber_id] = queue
        print(f"[mock-scheduler] subscriber connected: {subscriber_id}", flush=True)
        return queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        async with self._lock:
            self._subscribers.pop(subscriber_id, None)
        print(f"[mock-scheduler] subscriber disconnected: {subscriber_id}", flush=True)

    async def publish(self, event) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.items())

        if not subscribers:
            print(f"[mock-scheduler] no subscribers; event dropped: {event.type} task={event.task_id}", flush=True)
            return

        for subscriber_id, queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    print(f"[mock-scheduler] subscriber queue full: {subscriber_id}", flush=True)


class MockTaskSchedulerService(scheduler_pb2_grpc.TaskSchedulerServiceServicer):
    def __init__(self) -> None:
        self.event_bus = EventBus()
        self.tasks: Dict[str, StoredTask] = {}

    async def CreateTask(self, request, context):
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        session_id = request.session_id or f"{request.channel}_{request.user_id}"
        channel = request.channel or "web"

        self.tasks[task_id] = StoredTask(
            task_id=task_id,
            user_id=request.user_id,
            session_id=session_id,
            channel=channel,
            content=request.content,
            status="queued",
            waiting=0,
        )

        print(
            f"[mock-scheduler] CreateTask received: task_id={task_id}, user_id={request.user_id}, "
            f"channel={channel}, content={request.content!r}",
            flush=True,
        )

        asyncio.create_task(self._simulate_task(task_id, request))

        return scheduler_pb2.CreateTaskResponse(
            ok=True,
            task_id=task_id,
            status="queued",
            waiting=0,
            error="",
        )

    async def SubscribeEvents(self, request, context):
        subscriber_id = request.subscriber_id or f"subscriber-{uuid.uuid4().hex[:8]}"
        channels: Set[str] = set(request.channels)
        queue = await self.event_bus.subscribe(subscriber_id)

        try:
            yield scheduler_pb2.TaskEvent(
                event_id=f"event-{uuid.uuid4().hex[:12]}",
                task_id="",
                user_id="",
                session_id="",
                channel="system",
                type="subscriber_connected",
                text=f"{subscriber_id} subscribed to channels: {','.join(channels) or '*'}",
            )

            while True:
                event = await queue.get()
                if channels and event.channel not in channels:
                    continue
                yield event

        finally:
            await self.event_bus.unsubscribe(subscriber_id)

    async def GetTaskStatus(self, request, context):
        task = self.tasks.get(request.task_id)
        if not task:
            return scheduler_pb2.GetTaskStatusResponse(
                ok=False,
                task_id=request.task_id,
                status="not_found",
                waiting=0,
                error="task not found",
            )

        return scheduler_pb2.GetTaskStatusResponse(
            ok=True,
            task_id=task.task_id,
            status=task.status,
            waiting=task.waiting,
            error=task.error,
        )

    async def _simulate_task(self, task_id: str, request) -> None:
        task = self.tasks[task_id]
        session_id = task.session_id
        channel = task.channel
        user_id = task.user_id

        target = scheduler_pb2.DeliveryTarget(
            channel=channel,
            user_id=user_id,
            conversation_id=session_id,
            reply_to=request.client_message_id or "",
        )

        async def emit(event_type: str, text: str = "", waiting: int = 0, error: str = "", images=None):
            images = images or []
            event = scheduler_pb2.TaskEvent(
                event_id=f"event-{uuid.uuid4().hex[:12]}",
                task_id=task_id,
                user_id=user_id,
                session_id=session_id,
                channel=channel,
                type=event_type,
                text=text,
                waiting=waiting,
                error=error,
                delivery_target=target,
                metadata={
                    "mock": "true",
                    "source": "mock-task-scheduler-service",
                },
            )
            event.images.extend(images)
            print(f"[mock-scheduler] emit: type={event_type}, task_id={task_id}, user_id={user_id}", flush=True)
            await self.event_bus.publish(event)

        await emit("task_queued", waiting=0)
        await asyncio.sleep(0.3)

        task.status = "running"
        await emit("task_started", text="Mock scheduler 已接收任务，开始模拟后端处理。")
        await asyncio.sleep(0.5)

        await emit("model_call_started", text="Mock: 正在模拟模型调用。")
        await asyncio.sleep(0.8)

        reply = (
            "Mock 后端回声测试成功。\\n"
            f"收到用户：{user_id}\\n"
            f"收到内容：{request.content}\\n"
            f"task_id：{task_id}"
        )
        await emit("assistant_message", text=reply)
        await asyncio.sleep(0.2)

        task.status = "finished"
        await emit("task_finished", text="Mock 任务已完成。", waiting=0)


async def serve() -> None:
    port = int(os.getenv("PORT", "5100"))
    server = grpc.aio.server()
    scheduler_pb2_grpc.add_TaskSchedulerServiceServicer_to_server(
        MockTaskSchedulerService(),
        server,
    )
    listen_addr = f"0.0.0.0:{port}"
    server.add_insecure_port(listen_addr)
    print(f"[mock-scheduler] listening on {listen_addr}", flush=True)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
