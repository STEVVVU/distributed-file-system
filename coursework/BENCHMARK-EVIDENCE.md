# Initial hosted benchmark and inventory correction

The [initial hosted run](https://github.com/STEVVVU/distributed-file-system/actions/runs/39730877652) stopped during auxiliary storage accounting. It does not establish a five-repeat performance comparison or sustained capacity. The original failed receipts remain unchanged.

| Receipt | Recorded value |
| --- | --- |
| Source | `d2fb2184af66b8c0c96f6e1a6fa623e50aa452d9` |
| Native binary SHA-256 | `ee4fc4f949c52d861aba94e6e3886aefe739c81776b64a0301305dd0dac35df3` |
| Raw campaign summary SHA-256 | `295a3a5c3f6e47077c3045e0d7a97da049b3c0d2a89e840180652d0eebc0149e` |
| Raw summary size | 422,093 bytes |
| Environment | Linux 7.0.0-1017-azure x86_64, glibc 2.39, Python 3.12.3, four visible cores |
| Missing environment fields | CPU model and total RAM were not captured |
| Complete comparison repetitions | One of five, all 27 cells |
| Second repetition | 11 of 27 cells reached |
| Logical operations offered / finished | 392 / 392 |
| Failed / rejected / timed out / generator declined | 0 / 0 / 0 / 0 |
| Trial verdicts | 37 true, one false after successful request checks |
| Owned cleanup | True for all 38 trials |
| Offered-rate, sustained and recovery cells | Not reached |

The last trial used 1 MiB files, concurrency 16 and GET, in repetition 2. All 16 GETs returned the exact byte count and SHA-256 `d1dae91fdcc08ebc4e09de48052e54f07d2c9af24fe09d637cd64e89532edfcc`. The range oracle and manifest retrieval also completed. The result contains the manifest but no storage inventory, followed by `FileNotFoundError`. The code between those recorded phases enumerated files in the live master/filer/volume tree, then called stat on previously collected paths. A temporary metadata file can be renamed or removed between enumeration and stat. A controlled temporary-file rename reproduced the same exception class. The raw error used repr and discarded the filename, so the exact disappearing native file cannot be identified.

This is a confirmed live-inventory race in the benchmark. It is not evidence of a failed GET, lost file or product bottleneck. Shutdown connection errors in node logs occur after the inventory error, when cleanup stops the owned master and other processes; they do not establish a preceding service outage.

Version 2 keeps every request, payload, concurrency, repetition and oracle unchanged. It collects storage after all owned processes are reaped, before deletion. A no-op extension hook in the existing Workbench runs after its canonical containment checks; the benchmark captures only the complete owned root. Child-volume deletion during recovery keeps the original behavior. Each entry is inspected once with lstat, and only regular files contribute. An inventory I/O failure still fails cleanup and retains the data; nothing is silently skipped or retried. New storage figures include shutdown effects and the completed fault journey, and must not be mixed with version-1 live-tree figures.

Pure controls prove the final writer can rename its temporary metadata file during shutdown, the snapshot sees only the stable result, and deletion follows capture. Negative controls reject live-writer capture, reject paths outside the owned tree before invoking the hook, and retain a failing verdict/data when capture fails. These controls use fake process handles and small temporary files. Native rerun is still required; no local build or load campaign ran for this fix.

The unchanged real-process lifecycle takes about 55 seconds per retained trial. The 135-cell comparison matrix alone therefore needs about 124 minutes, before offered-rate sweeps, stability, recovery, build and artifact upload. The prior 90-minute job budget could not complete that plan. The main-reviewed budget is now 210 minutes on the existing isolated hosted job. No new partitioning or load engine was added.

Reproduce with `python coursework/benchmark.py smoke`, then `python coursework/benchmark.py benchmark` in the workflow's isolated Linux environment. The workflow retains the campaign summary, per-trial results/resources, native root logs, placements and separate profiles. It excludes native data directories. Loopback binding, default endpoint guards and explicitly blocked repair remain unchanged.

## Completed full hosted campaign

The [full campaign](https://github.com/STEVVVU/distributed-file-system/actions/runs/39739708895) passed at source `3044ff1dbc72cb606eb39f07509ec0dffe1babf7`. The raw summary SHA-256 is `73590ebd63bdb066eac551932894a8cb9b2811d854cb1e2962e14eb88ed52176`. Its receipt is `P09-full-39739708895/storage-benchmark-benchmark-3044ff1dbc72cb606eb39f07509ec0dffe1babf7/benchmark-benchmark-1792653673243642588/summary.json` in the central evidence archive. The compact [curated metrics](benchmark-full-39739708895.json) retain all 27 five-repeat cell summaries and the audit counts.

All 140 trials passed and cleaned up their owned processes. They offered and finished 12,271 operations. Failed, rejected, timed-out and generator-declined counts were all zero. The 4 KiB, 1 MiB and 16 MiB PUT, GET and metadata cells each ran five times at concurrency settings 1, 4 and 16. Each cell reports the median and range of its five run-level p50 and p99 values below. These are repetitions of one workload, not a before-and-after comparison.

| Size | Operation | Concurrency | p50, median [range] ms | p99, median [range] ms |
|---:|---|---:|---:|---:|
| 4 KiB | GET | 1 | 6.727 [6.569-8.205] | 13.101 [12.813-14.405] |
| 4 KiB | metadata | 1 | 8.084 [7.936-8.889] | 15.606 [15.279-16.753] |
| 4 KiB | PUT | 1 | 19.262 [17.183-22.888] | 35.018 [33.161-41.927] |
| 4 KiB | GET | 4 | 4.578 [4.337-6.334] | 8.582 [7.600-10.777] |
| 4 KiB | metadata | 4 | 7.651 [7.197-8.405] | 13.030 [12.621-13.793] |
| 4 KiB | PUT | 4 | 9.462 [9.011-12.668] | 16.263 [15.864-19.316] |
| 4 KiB | GET | 16 | 4.349 [4.103-5.606] | 6.666 [5.682-12.281] |
| 4 KiB | metadata | 16 | 7.328 [6.729-8.078] | 11.353 [11.186-13.456] |
| 4 KiB | PUT | 16 | 9.051 [7.138-12.712] | 15.274 [11.799-17.533] |
| 1 MiB | GET | 1 | 20.359 [20.193-21.115] | 37.800 [36.303-39.221] |
| 1 MiB | metadata | 1 | 8.079 [7.688-8.510] | 15.825 [14.775-16.017] |
| 1 MiB | PUT | 1 | 109.617 [105.592-113.367] | 207.826 [198.837-214.512] |
| 1 MiB | GET | 4 | 12.190 [9.299-13.630] | 20.354 [18.396-20.464] |
| 1 MiB | metadata | 4 | 7.829 [7.152-8.672] | 13.510 [12.778-14.014] |
| 1 MiB | PUT | 4 | 55.297 [50.031-68.425] | 94.048 [91.294-104.433] |
| 1 MiB | GET | 16 | 13.597 [13.080-18.732] | 23.058 [21.527-25.306] |
| 1 MiB | metadata | 16 | 8.691 [7.933-9.552] | 12.113 [11.141-15.129] |
| 1 MiB | PUT | 16 | 88.258 [78.271-95.686] | 101.209 [98.228-108.729] |
| 16 MiB | GET | 1 | 67.809 [66.386-68.691] | 134.887 [133.942-136.729] |
| 16 MiB | metadata | 1 | 2.899 [2.829-3.094] | 5.115 [4.980-5.494] |
| 16 MiB | PUT | 1 | 156.196 [151.812-164.006] | 302.960 [299.762-316.449] |
| 16 MiB | GET | 4 | 76.055 [68.201-77.984] | 88.206 [84.775-100.429] |
| 16 MiB | metadata | 4 | 3.927 [3.626-4.213] | 4.624 [4.573-4.803] |
| 16 MiB | PUT | 4 | 270.509 [256.228-286.423] | 276.004 [259.198-295.724] |
| 16 MiB | GET | 16 | 78.040 [69.439-83.082] | 88.940 [87.612-91.526] |
| 16 MiB | metadata | 16 | 3.764 [3.506-4.457] | 4.886 [4.588-5.020] |
| 16 MiB | PUT | 16 | 263.719 [237.564-279.193] | 277.508 [269.031-283.673] |

At 5, 20 and 80 offered transactions per second, the 10-second sweeps finished all 50, 200 and 800 operations. The 120-second run at 80/s finished all 9,600 offers. Its transaction p99 was 5.689688 ms and dispatch-lag p99 was 0.204087 ms. The campaign did not reach saturation at 80/s, so it establishes no capacity limit. The `<100 ms` dispatch-p99 and `<5 s` transaction-p99 checks are engineering screening thresholds for choosing the stability rate, not production SLAs.

The host was Linux 7.0.0-1017-azure on x86_64 with four visible cores and Python 3.12.3. The receipt has no CPU model or RAM value. GETs read the same warm-cache file, and the timed GET includes full-byte SHA-256 verification. Each timed PUT's acknowledged file was read back and checked after timing; the campaign verified 540 PUTs. Each trial also ran a range oracle and retained its manifest. The raw receipt does not retain the range response bytes or hash, so this audit verified the pinned source's exact-byte range assertion and each passing trial receipt, but could not recompute the range results from retained bytes. Each metadata sample made a stat and listing request, with response hashes and a listing-name check.

The 16 MiB cells had four offers per repetition because the existing storage limits cap `large_count` at four. A concurrency setting of 16 therefore did not produce 16 simultaneous requests. Their p99 values summarize four samples per run and provide no tail-confidence estimate. Do not use these results to claim disk saturation, multi-host performance or 225 MB/s. All 140 storage snapshots were taken after owned processes stopped and before guarded deletion; the receipts retain each apparent and allocated byte count and the logical live payload count.

The 2 MiB recovery journey took 92.935 seconds end to end. The endpoint guard rejected explicit repair, `repair.proved` remained false, and the degraded placement was retained. The 92.935-second figure is the complete fault and restart journey, not repair latency. The previous failed campaign and its receipts remain preserved above.
