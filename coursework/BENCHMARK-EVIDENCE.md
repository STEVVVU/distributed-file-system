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
