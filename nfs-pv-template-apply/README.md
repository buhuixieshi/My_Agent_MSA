# nfs-pv-template-apply-v2

修正点：

```yaml
storageClassName: ""
```

已添加到所有 PV 和 PVC，避免 PVC 被默认 StorageClass `standard` 接管，导致：

```text
Cannot bind to requested volume: storageClassName does not match
```

使用前，如已有错误创建的 PVC/PV，先删除：

```bash
kubectl delete pvc my-agent-config-pvc my-agent-openviking-pvc my-agent-assets-pvc my-agent-workspace-pvc my-agent-timer-tasks-pvc -n agent
kubectl delete pv my-agent-config-pv my-agent-openviking-pv my-agent-assets-pv my-agent-workspace-pv my-agent-timer-tasks-pv
```

再执行：

```bash
chmod +x apply-nfs-pv.sh
./apply-nfs-pv.sh
```
