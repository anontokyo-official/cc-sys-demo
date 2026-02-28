# chroma_ingestor

用于把单个文档自动切片后导入 K8s 集群中的 Chroma，并提供 `reset` 清空数据命令。

## 安装

```bash
cd apps/chroma_ingestor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 导入文档

方式 1：手动 port-forward 后导入。

```bash
kubectl port-forward -n default svc/chroma 8000:8000
python chroma_ingest.py import --file /path/to/doc.md --collection rag_docs
```

方式 2：脚本自动 port-forward。

```bash
python chroma_ingest.py --port-forward import --file /path/to/doc.md --collection rag_docs
```

可调切片参数：

```bash
python chroma_ingest.py import \
  --file /path/to/doc.md \
  --chunk-size 800 \
  --chunk-overlap 120 \
  --batch-size 64
```

## 清空所有数据

```bash
python chroma_ingest.py --port-forward reset --yes
```

如果 Chroma 服务端不允许 `client.reset()`，脚本会自动回退为逐个删除 collection。
