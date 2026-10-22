# Distributed File System

A fault-recovery coursework workbench built around the full Apache-2.0 [SeaweedFS](https://github.com/seaweedfs/seaweedfs) application. SeaweedFS supplies the master, filer, volume servers, HTTP APIs, replication and persistent metadata. This repository adds a maintained real-process experiment driver, byte-integrity evidence, a verification skill and a focused Windows test-cleanup fix. The original documentation is preserved in [README.upstream.md](README.upstream.md).

Upstream is pinned to [`106fd31af1c866d7ff235ade706cb4a1ba5805ba`](https://github.com/seaweedfs/seaweedfs/commit/106fd31af1c866d7ff235ade706cb4a1ba5805ba), with its complete Git history and license notices. This is an adaptation of an existing application, not an original implementation of SeaweedFS or a claim to have completed Stanford's GoLFS project.

## Run the experiment

Requirements: Go 1.26.6 or newer, Python 3.11 or newer, and six free loopback HTTP ports plus their gRPC counterparts. Tested locally on Windows amd64 with Go 1.27.3, Python 3.11, and CGO disabled. No Docker, FUSE driver, cloud account or API keys are needed.

```powershell
$env:CGO_ENABLED='0'
$env:GOTOOLCHAIN='local'
go build -o .local/weed.exe ./weed
python coursework/verify.py --run recovery
```

Use a new `--run` name for each invocation. The default ports are HTTP 19370–19375 and gRPC 29370–29375; use `--port 19400` to choose another range. The driver owns only its fresh `.local/<run>/data` directory and subprocess handles. It removes that data and stops its processes in `finally`; evidence remains under `.local/<run>/`. Do not use Python's `-O` option: the driver uses assertions as verification oracles.

For just the file lifecycle, run `python coursework/verify.py --run files --scenario baseline`. To check failure handling, run `python coursework/verify.py --run intentional-failure --fail`: exit 1, `passed:false`, and `cleanup:true` are expected.

## What is proved

The driver starts a master, one filer with its own embedded LevelDB store, and three distinct volume processes using replication `001` (two copies on different servers in the same rack). It uploads a 6,291,473-byte file with different contents in each 1 MiB segment, retains the actual seven-chunk manifest and segment SHA-256 ledger, streams the downloaded bytes through SHA-256, reads a range crossing a chunk boundary, lists the file, overwrites a separate file, and deletes it.

The recovery journey erases one stopped replica's actual data, proves the acknowledged file remains readable, restarts the master and filer against their unchanged stores, requires unchanged chunk metadata, and restarts the surviving volume processes before checking the same file again. After all volume processes stop, it records bounded unavailable reads and writes. A write whose client deadline expires is **unknown**, never counted as acknowledged.

The retained local run on October 21, 2026 (`.local/proof-final/result.json`) passed these checks and cleanup. All four full-file reads matched SHA-256 `2edcea6cb0b3a9ed03bb31b09c01cb53b9569b7603a6bff2170e07193dfc9b13`. The final unavailable read returned HTTP 500; the unavailable write reached its three-second client deadline and was recorded as unknown. See [results and commands](coursework/RESULTS.md) and the [verification skill](.agents/skills/verify-distributed-file-system/SKILL.md) for reproducible checks.

## Repair boundary and research question

The experiment asks how a GFS-style system preserves acknowledged bytes after replica failure and how an operator restores replica count. SeaweedFS's [official replication documentation](https://github.com/seaweedfs/seaweedfs/wiki/Replication) describes volume replication and explicit `volume.fix.replication` repair. Its semantics differ from GFS primary leases and atomic record append; this workbench makes no claim to implement those GFS contracts.

The driver starts an empty replacement volume and invokes the inherited shell's `volume.fix.replication -apply -retry=0`. At the pinned revision, the default replica endpoint guard rejects loopback source addresses. The shell can still exit zero, so the driver checks the actual rejection and unchanged degraded placement, retaining `repair.log` and `repair.proved:false`. A passing workbench run therefore **does not prove re-replication or survival after another replica loss**.

The guard remains enabled. Successful copy requires a separately authorized, suitably isolated multi-host/private-network experiment with appropriate authentication and endpoint policy. The inherited `-volume.allowUntrustedRemoteEndpoints` flag broadly disables endpoint checks; the driver does not use it. See the [recovery feature map](.agents/skills/verify-distributed-file-system/features/recovery.md).

One local filer store and one master remain availability bottlenecks. Process restarts and same-host copies do not prove power-loss, fsync, multi-host durability, POSIX/FUSE correctness or production readiness. The [GoLFS paper](https://www.scs.stanford.edu/24sp-cs244b/projects/GoLFS_A_Fault-tolerant_GFS_Implementation.pdf) supplies research context only; no unlicensed student source was copied.

## Checks and provenance

The full upstream default Windows binary builds with `CGO_ENABLED=0`; no source subset, overlay, installers or dependency changes were needed. Feature-tagged backends and native mounts were not exercised. Existing placement, replica-repair shell, server endpoint and copy tests pass after a one-line cleanup fix that closes a test store before Windows removes its temporary directory. [Provenance and audit](coursework/PROVENANCE.md) documents the license, dependency scan, original workflows and limitations.

The sole active [coursework CI](.github/workflows/coursework.yml) has read-only contents permission and performs build, static checks and real-process verification. The 74 original workflows remain unchanged as `*.yml.upstream`, which GitHub Actions does not execute. No release uploads, deployment jobs or secret references are active. CI has been authored and locally inspected; a remote Actions run is not claimed.

See [LICENSE](LICENSE) and the original [upstream README](README.upstream.md) for the inherited application's documentation and attribution.
