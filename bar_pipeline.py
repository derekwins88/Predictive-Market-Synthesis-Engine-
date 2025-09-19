#!/usr/bin/env python3
"""
Bar Pipeline: TCP → Parse → Normalize → Fan-out Sinks (stdout, file, sqlite, kafka*)
Run:
  python bar_pipeline.py --host 0.0.0.0 --port 9099 \
    --sink stdout,file,sqlite \
    --file-path out/bars_%Y%m%d.ndjson \
    --sqlite db/bars.db

Input (line-by-line):
  CSV:   timestamp,symbol,open,high,low,close,volume
  NDJSON: {"timestamp":"...","symbol":"ES","open":...,"high":...,"low":...,"close":...,"volume":...}

*Kafka is optional (requires confluent-kafka)
"""

import asyncio
import argparse
import csv
import json
import os
import pathlib
import sqlite3
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# -------------------------
# Schema & normalization
# -------------------------
FIELDS = [
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "delta_phi",
    "regime",
    "capsule_id",
]


def _parse_line(line: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse of a CSV or NDJSON line to the canonical bar schema."""
    line = line.strip()
    if not line:
        return None

    # NDJSON?
    if line.startswith("{") and line.endswith("}"):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        return _normalize(obj)

    # CSV fallback
    try:
        parts = next(csv.reader([line]))
    except Exception:
        parts = line.split(",")

    keys_guess = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    data = {k: (parts[i] if i < len(parts) else None) for i, k in enumerate(keys_guess)}
    return _normalize(data)


def _to_iso(ts: Any) -> Optional[str]:
    if ts is None or ts == "":
        return None
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(float(ts)).isoformat() + "Z"
    s = str(ts)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "").replace("z", ""))
        return dt.isoformat() + "Z"
    except Exception:
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y%m%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.isoformat() + "Z"
            except Exception:
                pass
    return None


def _fnum(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None


def _normalize(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize arbitrary field names into the canonical schema."""
    out: Dict[str, Any] = {}
    out["timestamp"] = _to_iso(
        obj.get("timestamp")
        or obj.get("time")
        or obj.get("date")
        or obj.get("datetime")
    )
    symbol = obj.get("symbol") or obj.get("sym") or ""
    out["symbol"] = str(symbol).strip().upper()
    out["open"] = _fnum(obj.get("open"))
    out["high"] = _fnum(obj.get("high"))
    out["low"] = _fnum(obj.get("low"))
    out["close"] = _fnum(obj.get("close"))
    out["volume"] = _fnum(obj.get("volume"))
    out["delta_phi"] = _fnum(obj.get("delta_phi"))
    out["regime"] = obj.get("regime") or None
    out["capsule_id"] = obj.get("capsule_id") or None

    required = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    if any(out[k] in (None, "") for k in required):
        return None
    return out


# -------------------------
# Sinks
# -------------------------


class Sink:
    def write(self, row: Dict[str, Any]) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class StdoutSink(Sink):
    def write(self, row: Dict[str, Any]) -> None:
        print(json.dumps(row, separators=(",", ":")))


class RotatingFileSink(Sink):
    def __init__(self, path_pattern: str):
        self.path_pattern = path_pattern
        self.fp: Optional[Any] = None
        self.current_path: Optional[str] = None
        directory = os.path.dirname(self._render_path())
        if directory:
            os.makedirs(directory, exist_ok=True)

    def _render_path(self) -> str:
        return datetime.utcnow().strftime(self.path_pattern)

    def _ensure_fp(self) -> None:
        path = self._render_path()
        if path != self.current_path:
            if self.fp:
                self.fp.close()
            self.current_path = path
            self.fp = open(path, "a", buffering=1, encoding="utf-8")

    def write(self, row: Dict[str, Any]) -> None:
        self._ensure_fp()
        assert self.fp is not None
        self.fp.write(json.dumps(row, separators=(",", ":")) + "\n")

    def close(self) -> None:
        if self.fp:
            self.fp.close()
            self.fp = None


class SQLiteSink(Sink):
    def __init__(self, db_path: str):
        directory = os.path.dirname(db_path) or "."
        pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_schema()
        self._batch: List[Dict[str, Any]] = []
        self._last_flush = time.time()

    def _ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS bars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            delta_phi REAL,
            regime TEXT,
            capsule_id TEXT
        );
        """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_bars_ts_sym ON bars(timestamp, symbol);"
        )
        self.conn.commit()

    def write(self, row: Dict[str, Any]) -> None:
        self._batch.append(row)
        if len(self._batch) >= 250 or (time.time() - self._last_flush) > 1.0:
            self.flush()

    def flush(self) -> None:
        if not self._batch:
            return
        cur = self.conn.cursor()
        cur.executemany(
            """
        INSERT INTO bars (timestamp,symbol,open,high,low,close,volume,delta_phi,regime,capsule_id)
        VALUES (:timestamp,:symbol,:open,:high,:low,:close,:volume,:delta_phi,:regime,:capsule_id)
        """,
            self._batch,
        )
        self.conn.commit()
        self._batch.clear()
        self._last_flush = time.time()

    def close(self) -> None:
        self.flush()
        self.conn.close()


class KafkaSink(Sink):
    def __init__(self, brokers: str, topic: str):
        try:
            from confluent_kafka import Producer  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            print(
                "⚠️ KafkaSink requires confluent-kafka. pip install confluent-kafka",
                file=sys.stderr,
            )
            raise exc
        self.topic = topic
        self.producer = Producer({"bootstrap.servers": brokers})

    def write(self, row: Dict[str, Any]) -> None:
        self.producer.produce(self.topic, json.dumps(row).encode("utf-8"))
        self.producer.poll(0)

    def close(self) -> None:
        self.producer.flush(5)


# -------------------------
# Metrics
# -------------------------


class Metrics:
    def __init__(self) -> None:
        self.received = 0
        self.parsed = 0
        self.dropped = 0
        self.last_log = time.time()

    def bump_recv(self) -> None:
        self.received += 1

    def bump_parsed(self) -> None:
        self.parsed += 1

    def bump_dropped(self) -> None:
        self.dropped += 1

    def maybe_log(self) -> None:
        now = time.time()
        if now - self.last_log >= 10:
            print(
                f"📊 bars recv={self.received} ok={self.parsed} dropped={self.dropped}"
            )
            self.last_log = now


# -------------------------
# Server
# -------------------------


async def serve(host: str, port: int, sinks: List[Sink], max_queue: int) -> None:
    queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=max_queue)
    metrics = Metrics()

    async def writer() -> None:
        while True:
            row = await queue.get()
            try:
                for sink in sinks:
                    sink.write(row)
            except Exception as exc:
                print(f"⚠️ sink error: {exc}", file=sys.stderr)
            finally:
                queue.task_done()
                metrics.maybe_log()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        print(f"✅ connection {addr}")
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                metrics.bump_recv()
                msg = line.decode("utf-8", errors="ignore")
                row = _parse_line(msg)
                if row is None:
                    metrics.bump_dropped()
                    continue
                metrics.bump_parsed()
                await queue.put(row)
        except asyncio.QueueFull:
            metrics.bump_dropped()
        except Exception as exc:
            print(f"⚠️ conn error {addr}: {exc}")
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"❌ disconnected {addr}")

    workers = [asyncio.create_task(writer()) for _ in range(2)]

    server = await asyncio.start_server(handle, host, port)
    print(f"📡 listening on {host}:{port}")
    async with server:
        await server.serve_forever()

    for worker in workers:
        worker.cancel()


# -------------------------
# CLI
# -------------------------


def build_sinks(args: argparse.Namespace) -> List[Sink]:
    sinks: List[Sink] = []
    for name in args.sink.split(","):
        n = name.strip().lower()
        if n == "stdout":
            sinks.append(StdoutSink())
        elif n == "file":
            sinks.append(RotatingFileSink(args.file_path))
        elif n == "sqlite":
            sinks.append(SQLiteSink(args.sqlite))
        elif n == "kafka":
            sinks.append(KafkaSink(args.kafka_brokers, args.kafka_topic))
        elif n == "":
            continue
        else:
            print(f"⚠️ unknown sink: {n}", file=sys.stderr)
    if not sinks:
        sinks.append(StdoutSink())
    return sinks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9099)
    parser.add_argument(
        "--sink", default="stdout,file", help="comma list: stdout,file,sqlite,kafka"
    )
    parser.add_argument("--file-path", default="out/bars_%Y%m%d.ndjson")
    parser.add_argument("--sqlite", default="db/bars.db")
    parser.add_argument("--kafka-brokers", default="localhost:9092")
    parser.add_argument("--kafka-topic", default="bars.ndjson")
    parser.add_argument("--max-queue", type=int, default=5000)
    args = parser.parse_args()

    for path in [args.file_path, args.sqlite]:
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)

    sinks = build_sinks(args)
    try:
        asyncio.run(serve(args.host, args.port, sinks, args.max_queue))
    except KeyboardInterrupt:
        print("\n👋 shutting down…")
    finally:
        for sink in sinks:
            try:
                sink.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
