# Repository commands and boundaries

This repository retains the full Apache-2.0 SeaweedFS application at upstream base `106fd31af1c866d7ff235ade706cb4a1ba5805ba`. Read `README.md`, `README.upstream.md` and `coursework/PROVENANCE.md` before changing scope or attribution. Preserve upstream APIs, notices and source; do not claim GFS primary leases, atomic append, Stanford completion or automatic repair.

## Build and verify

Use Go 1.26.6 or newer with `GOTOOLCHAIN=local`, `CGO_ENABLED=0`; Python 3.11 or newer. This workspace uses Go 1.27.3 at `C:/Users/steve/.codex/tools/coursework-go/go/bin/go.exe`, isolated GOPATH `C:/Users/steve/.codex/tools/coursework-go/gopath` and GOCACHE `C:/Users/steve/.codex/tools/coursework-go/cache`. Preserve shared caches.

```text
go build -o .local/weed.exe ./weed
go mod verify
go vet ./weed/storage/super_block ./weed/topology/balancer ./weed/server
go test ./weed/storage/super_block ./weed/topology/balancer
go test ./weed/shell -run 'Test.*(Replica|Replication)' -count=1
go test ./weed/server -run 'Test.*(ReplicaTarget|RemoteEndpoint|BlockedIP|VolumeCopy)' -count=1
python -m unittest discover -s coursework -p test_verify.py -v
python coursework/verify.py --run fresh-name
python coursework/verify.py --run fresh-failure-name --fail
```

Use [.agents/skills/verify-distributed-file-system/SKILL.md](.agents/skills/verify-distributed-file-system/SKILL.md) and its feature map for Launch, Doctor, Drive, Evidence and Cleanup. Intentional failure must exit 1 with `passed:false`, `cleanup:true` and the deliberate error. Never invoke Python with `-O`; assertions are verification oracles.

## Protected defaults and scratch ownership

Keep loopback binding and default replica endpoint guards enabled. Repair is explicitly blocked by the guard in this local setup; do not enable `volume.allowUntrustedRemoteEndpoints`, expose private/public listeners or claim re-replication to make a check pass. Broader network experiments require separate authorization and appropriate authentication/endpoint policy.

Every run needs a fresh directory name and free port range (default HTTP 19370–19375, gRPC 29370–29375). Before recursive deletion, resolve the final target and verify containment within that run's freshly created `.local/<run>/data`. Preserve process handles until confirmed termination; attempt cleanup for all owned processes/logs, retain unresolved ownership/data, and save a failing final verdict on cleanup errors. Evidence survives cleanup. Never kill by process name or delete unrelated temporary directories, caches or user files.

Only `coursework.yml` is active CI, with read-only contents permission and no secrets, release uploads or deployments. Keep inherited `*.yml.upstream` workflow content intact and inactive. Format only touched Go files; avoid unrelated CRLF churn. Reproduce real failures before changing their cause-dependent code and retain focused regression evidence.
