# File lifecycle

## Sub-features

Create, read, range, list, overwrite and delete through the filer HTTP API; retain chunk metadata and byte ledger.

## How to get to it (user POV)

Upload to the local filer at `/coursework/ledger.bin`; fetch the same path and directory listing.

## Driving it with Python

Run `python coursework/verify.py --run files`. Acknowledged 6 MiB plus tail must return the same streaming SHA-256, have multiple chunk entries, and return exact bytes for a range crossing a 1 MiB boundary. A separate mutable file must show replacement bytes and return 404 after delete.

## Gotchas

One host and one filer store; no POSIX mount, host crash, power loss, or remote durability claim. File chunking is configured to 1 MiB. HTTP timeouts fail the run rather than count as acknowledged writes.
