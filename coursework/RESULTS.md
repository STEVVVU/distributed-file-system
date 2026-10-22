# Local verification, October 21, 2026

Environment: Windows amd64, Python 3.11, Go 1.27.3; `CGO_ENABLED=0`, `GOTOOLCHAIN=local`. The module requires Go 1.26.6. Shared isolated tool environment:

```powershell
$env:GOTOOLCHAIN='local'
$env:CGO_ENABLED='0'
$env:GOPATH='C:\Users\steve\.codex\tools\coursework-go\gopath'
$env:GOCACHE='C:\Users\steve\.codex\tools\coursework-go\cache'
$go='C:\Users\steve\.codex\tools\coursework-go\go\bin\go.exe'
```

Passed commands:

```powershell
& $go build -o .local/weed.exe ./weed
& $go test ./weed/storage/super_block ./weed/topology/balancer
& $go mod verify
& $go vet ./weed/storage/super_block ./weed/topology/balancer ./weed/server
& $go test ./weed/shell -run 'Test.*(Replica|Replication)' -count=1
& $go build -o .local/weed-rebuild.exe ./weed
& $go test ./weed/server -run 'Test.*(ReplicaTarget|RemoteEndpoint|BlockedIP|VolumeCopy)' -count=1
& $go run golang.org/x/vuln/cmd/govulncheck@v1.9.0 -mode=binary -show verbose .local/weed.exe
python -c "import ast,pathlib; ast.parse(pathlib.Path('coursework/verify.py').read_text())"
git diff --check
python coursework/verify.py --run proof-final
```

The initial unmodified upstream build and placement tests passed before driver implementation. Initial onboarding `--run baseline` and deliberate-failure journeys proved Launch, Doctor, Drive, Evidence and Cleanup before recovery was added. The final driver run exited 0 with `passed:true`, `cleanup:true`, and separately `repair.proved:false`. `python coursework/verify.py --run failure-final --fail` exited 1 with the deliberate error, `passed:false` and `cleanup:true`; the evidence survived scratch-data removal. The dependency scanner exited 0 with no reachable symbol/package findings and three module-only findings documented in provenance.

The server test sweep initially failed inherited Windows temporary-directory cleanup. Running `& $go test ./weed/server -run '^TestVolumeCopy_KeepsExistingReplicaWhenSourceUnreachable$' -count=1` reproduced failure independently. After adding store cleanup, the full focused sweep passed. `gofmt -w weed/server/volume_grpc_copy_verify_test.go` left exactly one added cleanup line in the Git diff. Baseline `gofmt -l` on untouched placement directories listed inherited CRLF files; they were not rewritten. Only the touched Go test was formatted.

The final byte oracle is a 6,291,473-byte file in seven chunks, with distinct 1 MiB segment contents. Initial read, read after permanent replica loss, read after same-store master/filer restart, and read after retained volume restart all matched `2edcea6cb0b3a9ed03bb31b09c01cb53b9569b7603a6bff2170e07193dfc9b13`. Cross-boundary range, directory listing, overwrite and delete passed. Initially each manifest volume had two copies; after loss some had one. Actual removed files are inventoried in the result.

An explicit repair attempt ran against an empty replacement volume with the inherited default endpoint guard. It rejected loopback sources; placement remained degraded. The earlier `.local/recovery-1` run correctly failed when its then-required repair oracle could not reach two copies. The final driver reports repair as blocked rather than claiming copy success. Read availability after a further replica loss is not tested.

After all volume processes stopped, the final read returned HTTP 500 and the final write reached its three-second client deadline. The write is recorded as unknown and unacknowledged. Cleanup terminated every owned process and removed scratch data; the evidence files remain.

Retained evidence (relative to repository root):

- `.local/proof-final/result.json`, `manifest.json`, `byte-ledger.json`, `listing.json`, `placement-before-loss.json`, `placement-degraded.json`, `placement-repair-blocked.json`, `repair.log`, and per-process logs.
- `.local/failure-final/result.json`, byte ledger/manifest/listing and logs; no remaining `data` directory.
- `.local/native-cleanup-before.txt` and `.local/native-cleanup-after.txt` reproduce the inherited test cleanup failure and passing focused sweep.
- `.local/vulnerability-audit-verbose.txt` retains the binary dependency/security scan.

No remote CI run, Linux runtime, feature-tagged backend, FUSE/WinFsp mount, multi-host failure, cloud service, power loss or production durability was verified. After the recovery proof, a missing-binary preflight guard was added and checked: exit 2, no run directory created. A further `python coursework/verify.py --run postcheck --scenario baseline` run passed. The only Go source change closes a test fixture.
