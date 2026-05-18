#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# apply-nfs-pv.sh
#
# 用途：
#   只在这里配置一次 NFS_SERVER / NFS_ROOT，
#   自动渲染 my-agent-nfs-pv-pvc.yaml.tpl，
#   然后 kubectl apply。
#
# 注意：
#   如果之前已经用错误 StorageClass 创建过 PVC/PV，
#   请先执行：
#
#   kubectl delete pvc my-agent-config-pvc my-agent-openviking-pvc my-agent-assets-pvc my-agent-workspace-pvc my-agent-timer-tasks-pvc -n agent
#   kubectl delete pv my-agent-config-pv my-agent-openviking-pv my-agent-assets-pv my-agent-workspace-pv my-agent-timer-tasks-pv
#
# 再执行本脚本。
# ============================================================

# 只需要改这里两项。
NFS_SERVER="${NFS_SERVER:-172.29.219.49}"
NFS_ROOT="${NFS_ROOT:-/srv/nfs/my-agent}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="$SCRIPT_DIR/my-agent-nfs-pv-pvc.yaml.tpl"
OUTPUT_FILE="$SCRIPT_DIR/my-agent-nfs-pv-pvc.generated.yaml"

if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "[ERROR] 找不到模板文件：$TEMPLATE_FILE"
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "[ERROR] 找不到 kubectl，请先安装或确认 PATH。"
  exit 1
fi

echo "[INFO] NFS_SERVER=$NFS_SERVER"
echo "[INFO] NFS_ROOT=$NFS_ROOT"

if command -v envsubst >/dev/null 2>&1; then
  NFS_SERVER="$NFS_SERVER" NFS_ROOT="$NFS_ROOT" \
    envsubst < "$TEMPLATE_FILE" > "$OUTPUT_FILE"
else
  echo "[WARN] 找不到 envsubst，使用 sed fallback。"
  sed \
    -e "s#\${NFS_SERVER}#$NFS_SERVER#g" \
    -e "s#\${NFS_ROOT}#$NFS_ROOT#g" \
    "$TEMPLATE_FILE" > "$OUTPUT_FILE"
fi

echo "[OK] generated: $OUTPUT_FILE"

if grep -q '\${NFS_SERVER}\|\${NFS_ROOT}' "$OUTPUT_FILE"; then
  echo "[ERROR] 模板变量没有被完全替换，请检查文件：$OUTPUT_FILE"
  exit 1
fi

echo "[INFO] applying..."
kubectl apply -f "$OUTPUT_FILE"

echo
echo "[DONE] NFS PV/PVC 已应用。"
echo
echo "检查："
echo "  kubectl get pv"
echo "  kubectl get pvc -n agent"
