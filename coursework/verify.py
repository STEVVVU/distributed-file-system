"""Drive isolated, real SeaweedFS HTTP processes; retain proof after cleanup."""
import argparse
import datetime
import hashlib
import http.client
import json
import pathlib
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Workbench:
    def __init__(self, args):
        self.args = args
        self.out = ROOT / ".local" / args.run
        self.out.mkdir(parents=True, exist_ok=False)
        self.data = self.out / "data"
        self.data.mkdir()
        self.processes = {}
        self.logs = []
        self.result = {"passed": False, "events": [], "cleanup": False}
        with args.binary.open("rb") as binary:
            self.result["binary_sha256"] = hashlib.file_digest(binary, "sha256").hexdigest()
        self.result["upstream_sha"] = "106fd31af1c866d7ff235ade706cb4a1ba5805ba"
        self.master = args.port
        self.filer = args.port + 1
        self.volumes = [args.port + 2 + i for i in range(3)]

    def record(self, action, **state):
        self.result["events"].append({"action": action,
                                      "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), **state})
        self.save()

    def save(self):
        (self.out / "result.json").write_text(json.dumps(self.result, indent=2))

    def request(self, port, path, method="GET", data=None, headers=None, timeout=8):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data, headers or {}, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)

    def wait(self, description, probe, timeout=50):
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            try:
                value = probe()
                if value:
                    return value
            except (OSError, ValueError, KeyError) as error:
                last = str(error)
            time.sleep(0.25)
        raise AssertionError(f"{description}: deadline exceeded; last error {last}")

    def start(self, name, arguments):
        directory = self.data / name
        directory.mkdir(exist_ok=True)
        log = (self.out / f"{name}-{len(self.logs)}.log").open("wb")
        self.logs.append(log)
        command = [str(self.args.binary.resolve()), *arguments]
        process = subprocess.Popen(command, cwd=directory, stdout=log, stderr=subprocess.STDOUT)
        self.processes[name] = process
        self.record("launch", name=name, pid=process.pid, command=command)

    def stop(self, name):
        process = self.processes.pop(name)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        self.record("stop", name=name, returncode=process.returncode)

    def start_master(self):
        self.start("master", ["master", "-ip=127.0.0.1", "-ip.bind=127.0.0.1",
                   f"-port={self.master}", "-peers=none", "-mdir=.",
                   "-volumeSizeLimitMB=16", "-defaultReplication=001"])
        self.wait("master ready", lambda: self.request(self.master, "/cluster/status")[0] == 200)

    def start_filer(self):
        self.start("filer", ["filer", "-ip=127.0.0.1", "-ip.bind=127.0.0.1",
                   f"-port={self.filer}", f"-master=127.0.0.1:{self.master}",
                   "-defaultStoreDir=.", "-maxMB=1", "-defaultReplicaPlacement=001"])
        self.wait("filer ready", lambda: self.request(self.filer, "/?pretty=y")[0] == 200)

    def start_volume(self, index):
        self.start(f"volume-{index}", ["volume", "-ip=127.0.0.1", "-ip.bind=127.0.0.1",
                   f"-port={self.volumes[index]}", f"-master=127.0.0.1:{self.master}",
                   "-dir=.", "-max=8", "-dataCenter=local", "-rack=one"])
        self.wait("volume ready", lambda: self.request(self.volumes[index], "/status")[0] == 200)

    def launch(self):
        for port in [self.master, self.filer, *self.volumes]:
            for target in (port, port + 10000):
                with socket.socket() as check:
                    check.bind(("127.0.0.1", target))
        self.start_master()
        for index in range(3):
            self.start_volume(index)
        self.start_filer()
        self.record("doctor", processes={name: p.poll() for name, p in self.processes.items()},
                    master=json.loads(self.request(self.master, "/cluster/status")[1]))
        assert all(p.poll() is None for p in self.processes.values())

    def upload(self, path, payload):
        status, body, _ = self.request(self.filer, path, "PUT", payload,
                                      {"Content-Type": "application/octet-stream"}, timeout=30)
        assert status in (200, 201), (status, body)
        self.record("acknowledged-write", path=path, status=status, bytes=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest(), response=body.decode())

    def verify_bytes(self, path, expected, label):
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(f"http://127.0.0.1:{self.filer}{path}", timeout=12) as response:
            while block := response.read(65536):
                digest.update(block)
                size += len(block)
        assert size == len(expected) and digest.hexdigest() == hashlib.sha256(expected).hexdigest()
        self.record(label, path=path, bytes=size, sha256=digest.hexdigest())

    def drive(self):
        payload = b"".join(bytes((byte + index) % 256 for byte in range(256)) * 4096
                           for index in range(6)) + b"acknowledged-tail"
        path = "/coursework/ledger.bin"
        ledger = [{"offset": offset, "size": len(payload[offset:offset + 1048576]),
                   "sha256": hashlib.sha256(payload[offset:offset + 1048576]).hexdigest()}
                  for offset in range(0, len(payload), 1048576)]
        (self.out / "byte-ledger.json").write_text(json.dumps(ledger, indent=2))
        self.upload(path, payload)
        self.verify_bytes(path, payload, "read-acknowledged-bytes")
        metadata = json.loads(self.request(self.filer, path + "?metadata=true")[1])
        (self.out / "manifest.json").write_text(json.dumps(metadata, indent=2))
        chunks = metadata.get("chunks", metadata.get("Chunks", []))
        assert len(chunks) > 1, metadata
        self.record("multi-chunk-manifest", chunks=len(chunks))
        status, body, _ = self.request(self.filer, path, headers={"Range": "bytes=1048570-1048590"})
        assert status == 206 and body == payload[1048570:1048591]
        self.record("range-crossing-chunk", status=status, sha256=hashlib.sha256(body).hexdigest())
        listing = self.request(self.filer, "/coursework/?pretty=y", headers={"Accept": "application/json"})[1]
        assert b"ledger.bin" in listing
        (self.out / "listing.json").write_bytes(listing)
        self.upload("/coursework/mutable.txt", b"first")
        self.upload("/coursework/mutable.txt", b"replacement")
        self.verify_bytes("/coursework/mutable.txt", b"replacement", "overwrite")
        self.request(self.filer, "/coursework/mutable.txt", "DELETE")
        try:
            self.request(self.filer, "/coursework/mutable.txt")
        except urllib.error.HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("deleted file still readable")
        self.record("delete", status=404)
        if self.args.fail:
            raise AssertionError("deliberate verification failure")
        if self.args.scenario == "recovery":
            self.recovery(path, payload, chunks)

    def placement(self, volume_ids):
        return {vid: json.loads(self.request(self.master, f"/dir/lookup?volumeId={vid}&read=yes")[1])
                for vid in volume_ids}

    @staticmethod
    def locations(placement):
        return {vid: {location["url"] for location in info["locations"]}
                for vid, info in placement.items()}

    def snapshot(self, label, volume_ids):
        placement = self.placement(volume_ids)
        (self.out / f"placement-{label}.json").write_text(json.dumps(placement, indent=2))
        self.record(label, placement=placement)
        return self.locations(placement)

    def recovery(self, path, payload, chunks):
        volume_ids = sorted({chunk["file_id"].split(",")[0] for chunk in chunks})
        before = self.snapshot("before-loss", volume_ids)
        assert all(len(nodes) == 2 for nodes in before.values()), before
        candidates = {node for nodes in before.values() for node in nodes}
        lost = sorted(candidates)[0]
        lost_index = self.volumes.index(int(lost.rsplit(":", 1)[1]))
        self.stop(f"volume-{lost_index}")
        lost_dir = self.data / f"volume-{lost_index}"
        inventory = [{"name": item.name, "bytes": item.stat().st_size} for item in lost_dir.iterdir()]
        shutil.rmtree(lost_dir)
        self.record("permanent-replica-loss", node=lost, removed_files=inventory)
        self.wait("master removes lost replicas", lambda: all(
            lost not in nodes for nodes in self.locations(self.placement(volume_ids)).values()), timeout=80)
        degraded = self.snapshot("degraded", volume_ids)
        assert any(len(nodes) == 1 for nodes in degraded.values())
        self.verify_bytes(path, payload, "read-after-replica-loss")
        self.stop("filer")
        self.stop("master")
        self.start_master()
        self.start_filer()
        self.wait("surviving volumes rejoin restarted master", lambda: all(
            self.locations(self.placement(volume_ids)).values()), timeout=80)
        self.verify_bytes(path, payload, "read-after-master-and-filer-restart")
        restarted = json.loads(self.request(self.filer, path + "?metadata=true")[1])
        assert restarted["chunks"] == chunks
        self.record("persistent-metadata", same_chunks=True)
        spare_index = 3
        self.volumes.append(self.args.port + 5)
        for target in (self.volumes[spare_index], self.volumes[spare_index] + 10000):
            with socket.socket() as check:
                check.bind(("127.0.0.1", target))
        self.start_volume(spare_index)
        command = [str(self.args.binary.resolve()), "shell", f"-master=127.0.0.1:{self.master}",
                   f"-filer=127.0.0.1:{self.filer}"]
        shell = subprocess.run(command, input=b"lock\nvolume.fix.replication -apply -retry=0\nunlock\nexit\n",
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=150,
                               cwd=self.data)
        (self.out / "repair.log").write_bytes(shell.stdout)
        self.record("explicit-repair", command=command, returncode=shell.returncode)
        assert shell.returncode == 0
        assert b"resolves to loopback address" in shell.stdout, shell.stdout.decode(errors="replace")
        unchanged = self.snapshot("repair-blocked", volume_ids)
        assert unchanged == degraded
        self.result["repair"] = {"proved": False, "status": "blocked",
                                 "reason": "upstream replica endpoint guard rejects loopback"}
        self.record("repair-security-boundary-preserved", re_replication_proved=False)
        for index in range(3):
            name = f"volume-{index}"
            if name in self.processes:
                self.stop(name)
                self.start_volume(index)
        self.wait("retained replicas rejoin", lambda: self.locations(self.placement(volume_ids)) == degraded)
        self.verify_bytes(path, payload, "read-after-retained-volume-restarts")
        for name in list(self.processes):
            if name.startswith("volume-"):
                self.stop(name)
        for action, method, data in [("unavailable-read", "GET", None),
                                     ("unavailable-write", "PUT", b"unacknowledged")]:
            started = time.monotonic()
            try:
                status, body, _ = self.request(self.filer, path if data is None else "/coursework/uncertain.bin",
                                               method, data, timeout=3)
                self.record(action, status=status, response=body.decode(errors="replace"),
                            acknowledged=status in (200, 201), seconds=time.monotonic() - started)
                raise AssertionError(f"unexpected successful {action}: {status}")
            except urllib.error.HTTPError as error:
                self.record(action, status=error.code, acknowledged=False,
                            seconds=time.monotonic() - started)
            except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
                self.record(action, error=str(error), acknowledged=False,
                            outcome="unknown" if data is not None else "unavailable",
                            seconds=time.monotonic() - started)

    def cleanup(self):
        for name in list(self.processes):
            self.stop(name)
        for log in self.logs:
            log.close()
        shutil.rmtree(self.data)
        self.result["cleanup"] = True
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=pathlib.Path, default=ROOT / ".local/weed.exe")
    parser.add_argument("--run", required=True)
    parser.add_argument("--port", type=int, default=19370)
    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--scenario", choices=("baseline", "recovery"), default="recovery")
    args = parser.parse_args()
    if not args.run or pathlib.Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("--run must be a new directory name")
    if not 1024 <= args.port <= 55530:
        parser.error("port must leave room for HTTP and gRPC ports")
    if not args.binary.is_file():
        parser.error("build the SeaweedFS binary before verification")
    workbench = Workbench(args)
    try:
        workbench.launch()
        workbench.drive()
        workbench.result["passed"] = True
    except Exception as error:
        workbench.result["error"] = f"{type(error).__name__}: {error}"
    finally:
        workbench.cleanup()
    print(workbench.out / "result.json")
    return 0 if workbench.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
