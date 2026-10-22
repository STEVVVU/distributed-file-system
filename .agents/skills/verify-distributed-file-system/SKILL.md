---
name: verify-distributed-file-system
description: Launch and drive the real local SeaweedFS master, filer and volume HTTP APIs, retaining file integrity and process evidence.
---

## Launch

Build upstream with `go build -o .local/weed.exe ./weed` (Windows, Go 1.26.6 or newer; CGO_ENABLED=0 is supported by the tested build). Run `python coursework/verify.py --run baseline --scenario baseline`. The driver reserves HTTP ports 19370–19374 and corresponding gRPC ports 29370–29374, refuses occupied ports, and owns only its subprocesses and new `.local/baseline/data` tree. Recovery also uses HTTP 19375 and gRPC 29375 for an empty replacement volume process. Use `--port` for a distinct port range and a fresh `--run` name for every invocation.

## Doctor

The driver checks every owned process remains alive, records `/cluster/status`, and requires HTTP readiness for master, volumes and filer before driving. Read `.local/<run>/result.json` and per-process logs when readiness fails. Never drive an unrelated running instance.

## Drive

`python coursework/verify.py --run baseline --scenario baseline` drives the mapped HTTP file journey. `python coursework/verify.py --run recovery` adds permanent replica loss, master/filer restart, a guard-rejected explicit repair attempt, retained-volume restart, and bounded unavailable reads/writes. `python coursework/verify.py --run deliberate-failure --fail` must exit 1 with `passed:false` and `cleanup:true`. This is a real failure-path check, not a successful feature proof.

## Evidence

`.local/<run>/result.json` records actions, acknowledged lengths/hashes, resulting states and process commands/PIDs. `byte-ledger.json` contains 1 MiB segment SHA-256 values. `manifest.json` retains the actual filer chunk metadata, and `listing.json` retains listing output. Recovery retains placement snapshots and `repair.log`. Logs and evidence survive cleanup; no run artifacts belong in git. A passing run requires both `passed:true` and `cleanup:true`; it does not prove repair when the separate `repair.proved` field is false. The pinned upstream guard blocks loopback replica copy, and the driver deliberately keeps that guard enabled.

## Cleanup

The driver stops only subprocess handles it created in `finally`, waits for termination, closes logs, then deletes only its new run's scratch data. It retains manifests, ledgers, results and logs. If the Python interpreter is forcibly killed, inspect recorded PIDs and their command lines before manually terminating survivors; do not kill by process name.

## Helpers

The maintained driver is `coursework/verify.py`, using only Python's standard library and public HTTP/CLI APIs. See [feature map](features/README.md).
