# utils/updater.py
"""
Apply a staged GitHub zipball over this install.

The running monitor only downloads the zip and writes updates/pending.json.
The next process start runs this module before native libraries are imported,
then replaces itself so serial ports and the web server are not held during
the file swap or pip install.

Preserved in place: config.ini, display settings, SQLite databases, logs,
the virtual environment, and the updates directory.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.request import Request, urlopen

INSTALL_ROOT = Path(__file__).resolve().parent.parent
UPDATES_DIRNAME = "updates"
PENDING_NAME = "pending.json"
APPLIED_NAME = "applied.json"
BACKUP_DIRNAME = "backup"

PRESERVE_TOP = {
    "config.ini",
    "display_config.json",
    "data",
    "logs",
    "venv",
    UPDATES_DIRNAME,
    ".git",
    "solar_monitoring.lock",
    ".solar_monitoring_restart_state",
}
DOWNLOAD_TIMEOUT_S = 120


def updates_dir(root: Path) -> Path:
    return root / UPDATES_DIRNAME


def pending_path(root: Path) -> Path:
    return updates_dir(root) / PENDING_NAME


def applied_path(root: Path) -> Path:
    return updates_dir(root) / APPLIED_NAME


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def read_applied(root: Path) -> Optional[Dict[str, Any]]:
    return read_json(applied_path(root))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def is_preserved_rel(rel: str) -> bool:
    """True for user data and installer state that must survive a tree swap."""
    if not rel or rel == ".":
        return False
    name = rel.split("/", 1)[0]
    if name in PRESERVE_TOP:
        return True
    if name.startswith("solar_monitoring.log"):
        return True
    if name.endswith(".db") or name.endswith(".db-wal") or name.endswith(".db-shm"):
        return True
    return False


def _venv_python(root: Path) -> Path:
    if sys.platform == "win32":
        candidate = root / "venv" / "Scripts" / "python.exe"
    else:
        candidate = root / "venv" / "bin" / "python"
    return candidate if candidate.is_file() else Path(sys.executable)


def _iter_unpreserved(root: Path):
    """Yield (path, relative posix, is_dir) without descending into preserved dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        dirnames[:] = [
            name
            for name in dirnames
            if not is_preserved_rel(f"{rel_dir}/{name}" if rel_dir else name)
        ]
        if rel_dir and not is_preserved_rel(rel_dir):
            yield Path(dirpath), rel_dir, True
        for name in filenames:
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if not is_preserved_rel(rel):
                yield Path(dirpath) / name, rel, False


def _copy_unpreserved(src: Path, dest: Path) -> None:
    for path, rel, is_dir in _iter_unpreserved(src):
        target = dest / rel
        if is_dir:
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _delete_stale(dest: Path, keep_rels: set) -> None:
    paths = [(path, rel, is_dir) for path, rel, is_dir in _iter_unpreserved(dest)]
    for path, rel, is_dir in sorted(paths, key=lambda item: len(item[1]), reverse=True):
        if rel in keep_rels:
            continue
        if is_dir:
            try:
                path.rmdir()
            except OSError:
                pass
        elif path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)


def swap_install_tree(install_root: Path, new_tree: Path) -> Path:
    """
    Replace install files with ``new_tree``, keeping preserved paths.

    Returns the backup directory used for rollback.
    """
    backup = updates_dir(install_root) / BACKUP_DIRNAME
    if backup.exists():
        shutil.rmtree(backup)
    backup.mkdir(parents=True)
    _copy_unpreserved(install_root, backup)

    new_rels = {rel for _path, rel, _is_dir in _iter_unpreserved(new_tree)}
    _copy_unpreserved(new_tree, install_root)
    _delete_stale(install_root, new_rels)
    return backup


def restore_install_tree(install_root: Path, backup: Path) -> None:
    """Put the pre-update tree back. Preserved user files are left alone."""
    if not backup.is_dir():
        raise OSError(f"Update backup is missing: {backup}")
    keep = {rel for _path, rel, _is_dir in _iter_unpreserved(backup)}
    _delete_stale(install_root, keep)
    _copy_unpreserved(backup, install_root)


def _safe_extract(zip_path: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        root = dest.resolve()
        for info in archive.infolist():
            target = (dest / info.filename).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Unsafe path in update zip: {info.filename}") from exc
        archive.extractall(dest)
    children = [p for p in dest.iterdir() if p.name != "__MACOSX"]
    dirs = [p for p in children if p.is_dir()]
    if len(dirs) == 1 and not any(p.is_file() for p in children):
        return dirs[0]
    return dest


def _pip_install(install_root: Path) -> None:
    requirements = install_root / "requirements.txt"
    if not requirements.is_file():
        raise OSError("requirements.txt is missing from the update")
    python = _venv_python(install_root)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(requirements)],
        cwd=str(install_root),
        check=True,
    )


def download_zip(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    request = Request(url, headers={"User-Agent": "solar-monitoring"})
    try:
        with urlopen(request, timeout=DOWNLOAD_TIMEOUT_S) as response, tmp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink()


def stage_auto_update(install_root: Path, channel: str, current_version: str) -> Optional[Dict[str, str]]:
    """
    Download the selected channel when it is newer than the applied marker.

    Returns the staged target, or None when there is nothing to install.
    """
    from utils.update_checker import lookup_update_target, should_auto_install

    if pending_path(install_root).is_file():
        return None
    target = lookup_update_target(channel)
    if not should_auto_install(target, current_version, read_applied(install_root)):
        return None
    assert target is not None
    safe_ref = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in target["ref"])[:80]
    zip_path = updates_dir(install_root) / "staging" / f"{safe_ref}.zip"
    download_zip(target["zipball_url"], zip_path)
    payload = dict(target)
    payload["zip_path"] = str(zip_path)
    _write_json(pending_path(install_root), payload)
    return target


def apply_pending(install_root: Path) -> int:
    """Install updates/pending.json. Returns a process exit code."""
    pending = pending_path(install_root)
    payload = read_json(pending)
    if not payload:
        print("Staged update file is invalid. Removing it.")
        pending.unlink(missing_ok=True)
        return 1
    zip_path = Path(str(payload.get("zip_path") or ""))
    if not zip_path.is_file():
        print(f"Staged update zip is missing: {zip_path}")
        pending.unlink(missing_ok=True)
        return 1

    extracted = updates_dir(install_root) / "staging" / "unpacked"
    backup = updates_dir(install_root) / BACKUP_DIRNAME
    try:
        new_tree = _safe_extract(zip_path, extracted)
        backup = swap_install_tree(install_root, new_tree)
        _pip_install(install_root)
    except Exception as exc:
        print(f"Update failed: {exc}")
        if backup.is_dir():
            try:
                restore_install_tree(install_root, backup)
                print("Restored the previous version.")
            except Exception as restore_exc:
                print(f"Rollback failed: {restore_exc}")
        pending.unlink(missing_ok=True)
        return 1

    _write_json(
        applied_path(install_root),
        {"channel": payload.get("channel"), "ref": payload.get("ref")},
    )
    pending.unlink(missing_ok=True)
    print(f"Update applied: {payload.get('channel')} {payload.get('label') or payload.get('ref')}")
    return 0


def apply_pending_and_reexec() -> None:
    """Apply a staged update in a child process, then replace this process."""
    root = INSTALL_ROOT
    if not pending_path(root).is_file():
        return
    print("Applying staged Solar Monitoring update...")
    completed = subprocess.run(
        [sys.executable, "-m", "utils.updater", "apply"],
        cwd=str(root),
    )
    if completed.returncode != 0 or pending_path(root).is_file():
        print("Staged update failed. Starting the current version.")
        return
    if sys.platform == "win32":
        # Let start_with_restart.bat start the new code. os.execv would detach
        # from that script and keep the old process's config loaded.
        print("Update applied. Exiting so the restart script can load it.")
        raise SystemExit(0)
    script = str(INSTALL_ROOT / "main.py")
    try:
        os.execv(sys.executable, [sys.executable, script] + sys.argv[1:])
    except OSError as exc:
        print(f"Update applied but restart failed: {exc}. Exiting so it can be started again.")
        raise SystemExit(0)


def main(argv: Optional[list] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["apply"]:
        print("usage: python -m utils.updater apply")
        return 2
    return apply_pending(INSTALL_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
