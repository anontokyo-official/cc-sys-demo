#!/usr/bin/env python3
"""Import document chunks into a Chroma server (optionally via kubectl port-forward)."""

from __future__ import annotations

import argparse
import hashlib
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import chromadb
from chromadb.api import ClientAPI


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import one document into Chroma with auto chunking, or reset all Chroma data."
    )

    parser.add_argument(
        "--chroma-url",
        default=os.getenv("CHROMA_URL", "http://127.0.0.1:8001"),
        help="Chroma HTTP URL, default: %(default)s",
    )
    parser.add_argument(
        "--port-forward",
        action="store_true",
        help="Auto start/stop kubectl port-forward for svc/chroma before running command.",
    )
    parser.add_argument(
        "--namespace",
        default=os.getenv("CHROMA_NAMESPACE", "default"),
        help="Kubernetes namespace for port-forward, default: %(default)s",
    )
    parser.add_argument(
        "--service",
        default=os.getenv("CHROMA_SERVICE", "chroma"),
        help="Kubernetes service name for port-forward, default: %(default)s",
    )
    parser.add_argument(
        "--local-port",
        type=int,
        default=int(os.getenv("CHROMA_LOCAL_PORT", "8000")),
        help="Local port used by port-forward, default: %(default)s",
    )
    parser.add_argument(
        "--remote-port",
        type=int,
        default=int(os.getenv("CHROMA_REMOTE_PORT", "8000")),
        help="Remote service port used by port-forward, default: %(default)s",
    )
    parser.add_argument(
        "--pf-timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for port-forward readiness, default: %(default)s",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import one document into a Chroma collection.")
    import_parser.add_argument("--file", required=True, help="Path to the source document.")
    import_parser.add_argument(
        "--collection",
        default=os.getenv("CHROMA_COLLECTION", "rag_docs"),
        help="Collection name, default: %(default)s",
    )
    import_parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Chunk size in characters, default: %(default)s",
    )
    import_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=120,
        help="Chunk overlap in characters, default: %(default)s",
    )
    import_parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Upsert batch size, default: %(default)s",
    )
    import_parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding for text documents, default: %(default)s",
    )
    import_parser.add_argument(
        "--source-id",
        default="",
        help="Logical source id written to metadata (default: file name).",
    )

    reset_parser = subparsers.add_parser("reset", help="Clear ALL Chroma data in current server.")
    reset_parser.add_argument(
        "--yes",
        action="store_true",
        help="Required safety flag to perform destructive reset.",
    )

    return parser.parse_args()


def build_http_client(chroma_url: str) -> ClientAPI:
    normalized = chroma_url if "://" in chroma_url else f"http://{chroma_url}"
    parsed = urlparse(normalized)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 8000)
    return chromadb.HttpClient(host=host, port=port, ssl=parsed.scheme == "https")


@contextmanager
def maybe_port_forward(args: argparse.Namespace) -> Iterator[None]:
    if not args.port_forward:
        yield
        return

    cmd = [
        "kubectl",
        "port-forward",
        f"svc/{args.service}",
        f"{args.local_port}:{args.remote_port}",
        "-n",
        args.namespace,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        wait_for_local_port(args.local_port, args.pf_timeout, proc)
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def wait_for_local_port(port: int, timeout: float, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("kubectl port-forward exited before becoming ready.")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for local port {port}.")


def read_document(path: Path, encoding: str) -> str:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Document not found: {path}")
    return path.read_text(encoding=encoding)


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    length = len(normalized)

    while start < length:
        end = min(start + chunk_size, length)

        if end < length:
            best_break = max(
                normalized.rfind("\n\n", start, end),
                normalized.rfind("\n", start, end),
                normalized.rfind(" ", start, end),
            )
            if best_break > start + max(50, chunk_size // 3):
                end = best_break

        if end <= start:
            end = min(start + chunk_size, length)

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        start = max(0, end - chunk_overlap)

    return chunks


def upsert_chunks(
    client: ClientAPI,
    collection_name: str,
    source_id: str,
    chunks: list[str],
    batch_size: int,
) -> None:
    collection = client.get_or_create_collection(name=collection_name)

    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        ids: list[str] = []
        metadatas: list[dict[str, object]] = []

        for index, chunk in enumerate(batch, start=offset):
            digest = hashlib.sha1(f"{source_id}:{index}:{chunk}".encode("utf-8")).hexdigest()
            ids.append(f"{source_id}-{index}-{digest[:12]}")
            metadatas.append(
                {
                    "source": source_id,
                    "chunk_index": index,
                    "total_chunks": len(chunks),
                }
            )

        collection.upsert(ids=ids, documents=batch, metadatas=metadatas)


def reset_all_data(client: ClientAPI) -> tuple[int, str]:
    try:
        client.reset()
        return (0, "reset")
    except Exception:
        collections = client.list_collections()
        names = [item.name if hasattr(item, "name") else str(item) for item in collections]
        for name in names:
            client.delete_collection(name=name)
        return (len(names), "delete-collections")


def resolve_chroma_url(args: argparse.Namespace) -> str:
    if args.port_forward:
        return f"http://127.0.0.1:{args.local_port}"
    return args.chroma_url


def run_import(args: argparse.Namespace) -> int:
    if args.chunk_size <= 0:
        raise ValueError("--chunk-size must be > 0")
    if args.chunk_overlap < 0:
        raise ValueError("--chunk-overlap must be >= 0")
    if args.chunk_overlap >= args.chunk_size:
        raise ValueError("--chunk-overlap must be smaller than --chunk-size")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")

    file_path = Path(args.file).expanduser().resolve()
    source_id = args.source_id.strip() or file_path.name

    text = read_document(file_path, args.encoding)
    chunks = chunk_text(text, args.chunk_size, args.chunk_overlap)
    if not chunks:
        raise ValueError("Document is empty after normalization; nothing imported.")

    client = build_http_client(resolve_chroma_url(args))
    upsert_chunks(client, args.collection, source_id, chunks, args.batch_size)

    print(
        f"Imported {len(chunks)} chunks from {file_path} into collection '{args.collection}' at {resolve_chroma_url(args)}"
    )
    return 0


def run_reset(args: argparse.Namespace) -> int:
    if not args.yes:
        raise ValueError("reset is destructive; re-run with --yes")

    client = build_http_client(resolve_chroma_url(args))
    deleted_count, mode = reset_all_data(client)

    if mode == "reset":
        print(f"Reset completed via client.reset() on {resolve_chroma_url(args)}")
    else:
        print(
            f"Reset completed by deleting {deleted_count} collections on {resolve_chroma_url(args)}"
        )
    return 0


def main() -> int:
    args = parse_args()

    with maybe_port_forward(args):
        if args.command == "import":
            return run_import(args)
        if args.command == "reset":
            return run_reset(args)

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
