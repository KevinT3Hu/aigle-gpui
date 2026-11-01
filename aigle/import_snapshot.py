#!/usr/bin/env python3
"""Import the published GPUI packaging baseline before replaying Aigle's HDR commits."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tomllib
import urllib.request

CRATES = {
    "gpui-pre": "crates/gpui",
    "gpui-pre-linux": "crates/gpui_linux",
    "gpui-pre-wgpu": "crates/gpui_wgpu",
}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "aigle-gpui-baseline-import"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def snapshots(version):
    result = {}
    revisions = set()
    for name in CRATES:
        metadata = json.loads(fetch(f"https://crates.io/api/v1/crates/{name}/{version}"))
        checksum = metadata["version"]["checksum"]
        archive = fetch(f"https://static.crates.io/crates/{name}/{name}-{version}.crate")
        if hashlib.sha256(archive).hexdigest() != checksum:
            raise RuntimeError(f"Checksum mismatch: {name} {version}")
        files = {}
        prefix = f"{name}-{version}/"
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                if not member.name.startswith(prefix):
                    raise RuntimeError(f"Unexpected archive path: {member.name}")
                relative = Path(member.name.removeprefix(prefix))
                if relative.is_absolute() or ".." in relative.parts:
                    raise RuntimeError(f"Unsafe archive path: {relative}")
                if relative == Path("Cargo.lock"):
                    continue
                files[relative] = tar.extractfile(member).read()
        manifest = tomllib.loads(files[Path("Cargo.toml")].decode())
        if manifest["package"]["version"] != version:
            raise RuntimeError(f"Unexpected version in {name}")
        revisions.add(manifest["package"]["metadata"]["gpui-pre"]["zed-rev"])
        result[name] = (checksum, files)
    if len(revisions) != 1:
        raise RuntimeError("The published snapshots do not use the same Zed revision")
    return revisions.pop(), result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Published gpui-pre snapshot version")
    parser.add_argument("--print-revision", action="store_true", help="Print its Zed baseline without modifying files")
    args = parser.parse_args()
    revision, packages = snapshots(args.version)
    if args.print_revision:
        print(revision)
        return
    root = Path(__file__).resolve().parents[1]
    if git(root, "status", "--porcelain"):
        raise RuntimeError("Commit or stash changes before importing a baseline")
    if (root / "aigle/baseline.json").exists():
        raise RuntimeError("A baseline is already imported. Start a new branch from the new Zed revision; see aigle/README.md")
    git(root, "merge-base", "--is-ancestor", revision, "HEAD")
    if git(root, "diff", revision, "HEAD", "--", *CRATES.values()):
        raise RuntimeError("GPUI sources already differ from the Zed baseline; importing would overwrite patches")
    for name, (_, files) in packages.items():
        target = root / CRATES[name]
        for relative, contents in files.items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        with (target / "Cargo.toml").open("a") as manifest:
            manifest.write('\n# Build independently of the full Zed workspace.\n[workspace]\n')
    provenance = {
        "snapshot_version": args.version,
        "upstream": "https://github.com/zed-industries/zed.git",
        "zed_revision": revision,
        "crates": {name: {"path": CRATES[name], "sha256": checksum} for name, (checksum, _) in packages.items()},
    }
    (root / "aigle/baseline.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"Imported gpui-pre {args.version} packaging from Zed {revision}")
    print("Review and commit this baseline, tag it, then cherry-pick the HDR commits. See aigle/README.md.")


if __name__ == "__main__":
    main()
