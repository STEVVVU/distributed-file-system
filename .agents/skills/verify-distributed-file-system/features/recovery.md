# Failure and recovery

## Sub-features

Inspect two-copy `001` placement; stop a replica process and erase its own data; read acknowledged bytes from survivors; restart master and filer against unchanged stores; restart retained volume processes; bound unavailable requests.

## How to get to it (user POV)

Run the storage workbench with the default recovery scenario. This is destructive only to the fresh, isolated run data created by the driver.

## Driving it with Python

`python coursework/verify.py --run recovery` requires matching file SHA-256 after replica loss, master/filer restart and retained volume restart. Chunk metadata must persist unchanged. `placement-before-loss.json`, `placement-degraded.json` and `placement-repair-blocked.json` expose actual placement. The driver invokes `lock`, `volume.fix.replication -apply -retry=0`, `unlock`, and `exit` through the inherited shell; its zero process status alone is insufficient. The actual server response must show loopback rejection and placement must remain degraded. `repair.proved:false` is required in this local scenario. Requests after all volume processes stop have three-second client deadlines; timeout writes are recorded as unknown, never acknowledged.

## Gotchas

Re-replication to changed placement and survival of a further replica loss remain unproved. Upstream's default VolumeCopy endpoint guard rejects loopback. This workbench neither disables that guard nor exposes listeners on a private interface. The existing `-volume.allowUntrustedRemoteEndpoints` option disables a broader endpoint policy and is not used or recommended here. A separately authorized isolated multi-host/private-network environment with appropriate authentication and endpoint policy is a prerequisite for a successful copy experiment. One master and one local LevelDB filer are availability bottlenecks. Process termination does not simulate power loss or fsync durability.
