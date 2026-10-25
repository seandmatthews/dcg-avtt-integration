"""Capture a golden scene fixture from a real Atlas release, with no human at the keyboard.

Drives the real Atlas VTT plugin inside a throwaway Obsidian vault: builds the
vault, installs the plugin build attached to the requested GitHub release tag,
launches an isolated Obsidian instance (its own --user-data-dir, so the owner's
running Obsidian is untouched) with a DevTools port, clicks through the vault
trust modal, opens the asset manager, and drops fixtures/sample.uvtt onto it —
the same drag a GM performs, synthesized through the plugin's own drop
handler. The written scene file becomes fixtures/golden-<version>/sample.atlasmap.

Usage (from the repo root; needs the `websocket-client` wheel):

    uv run --with websocket-client tools/capture-golden.py 0.7.1

Requires Obsidian (desktop) installed at %LOCALAPPDATA%/Programs/obsidian.
Refuses to launch when the DevTools port is already taken: the capture
drives whatever answers on it, so a foreign listener there (e.g. the
owner's own Obsidian started with remote debugging) would get clicked
instead of the throwaway instance. Kills only the Obsidian processes it
started (matched on the throwaway user-data-dir); leaves everything else
alone. With --keep the instance stays up for debugging; kill it via the
printed hint.
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket  # third-party; provided by `uv run --with websocket-client`

REPO = Path(__file__).resolve().parent.parent
CDP_PORT = 9223
CAP_DIR = Path(tempfile.gettempdir()) / "avtt-golden-capture"
OBSIDIAN_EXE = Path.home() / "AppData/Local/Programs/obsidian/Obsidian.exe"
SAMPLE = REPO / "fixtures" / "sample.uvtt"


def cdp_kill_our_obsidian() -> None:
    """Stop only Obsidian processes launched with our throwaway user-data-dir."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='Obsidian.exe'\" | "
        "Where-Object { $_.CommandLine -like '*avtt-golden-capture*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps], check=False, capture_output=True
    )


def cdp_port_taken(port: int) -> bool:
    """True when something already answers on the port.

    A connect probe, not a bind probe: this runs right after
    cdp_kill_our_obsidian(), and on Windows a just-killed listener can
    leave sockets in TIME_WAIT that still block a plain bind — a connect
    to a dead port is refused, so it fires only on a live listener.
    That is exactly the collision that matters: the launched Chromium
    binds its devtools server on 127.0.0.1 too, so anything answering
    there now would receive the clicks meant for the throwaway
    instance. Unreachable-but-not-refused (timeout and friends) also
    counts as taken — refusing is never destructive, proceeding might
    be.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return True


def clear_vault_dir(vault: Path) -> None:
    """Remove a previous vault; the killed instance's renderers can hold
    handles for a few seconds, so retry rather than fail."""
    if not vault.exists():
        return
    for attempt in range(6):
        try:
            shutil.rmtree(vault)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(2)


def build_vault(version: str) -> Path:
    vault = CAP_DIR / f"vault-{version.replace('.', '-')}"
    clear_vault_dir(vault)
    plugin = vault / ".obsidian" / "plugins" / "atlas-vtt"
    plugin.mkdir(parents=True)
    (vault / "Maps").mkdir()
    shutil.copy2(SAMPLE, vault / "Maps" / "sample.uvtt")
    for name in ("main.js", "manifest.json", "styles.css"):
        url = (
            "https://github.com/atlas-vtt/atlas-vtt/releases/download/"
            f"{version}/{name}"
        )
        dest = plugin / name
        print(f"  download {url}")
        with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
            f.write(r.read())
    (vault / ".obsidian" / "community-plugins.json").write_text(
        '["atlas-vtt"]', encoding="utf-8"
    )
    (vault / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    (vault / ".obsidian" / "appearance.json").write_text(
        '{"accentColor": ""}', encoding="utf-8"
    )
    appdata = CAP_DIR / "appdata"
    appdata.mkdir(parents=True, exist_ok=True)
    entry = json.dumps(
        {
            "vaults": {
                "a1b2c3d4e5f60718": {
                    "path": str(vault),
                    "ts": int(time.time() * 1000),
                    "open": True,
                }
            }
        }
    )
    (appdata / "obsidian.json").write_text(entry, encoding="utf-8")
    return vault


def cdp_targets() -> list[dict]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=5
    ) as r:
        return json.load(r)


class Page:
    """One Runtime.evaluate per call, over a lazily rebuilt websocket."""

    def __init__(self) -> None:
        self._ws: websocket.WebSocket | None = None
        self._id = 0

    def _connect(self) -> websocket.WebSocket:
        pages = [
            t
            for t in cdp_targets()
            if t.get("type") == "page" and t.get("url", "").startswith("app://")
        ]
        if not pages:
            raise RuntimeError("no main-window page target yet")
        ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], timeout=10, suppress_origin=True
        )
        self._id = 0
        return ws

    def eval(self, expression: str, await_promise: bool = False):
        if self._ws is None:
            self._ws = self._connect()
        self._id += 1
        msg = {
            "id": self._id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "userGesture": True,
                "awaitPromise": await_promise,
            },
        }
        try:
            self._ws.send(json.dumps(msg))
            while True:
                reply = json.loads(self._ws.recv())
                if reply.get("id") == self._id:
                    break
        except (websocket.WebSocketException, OSError, TimeoutError):
            # the window reloaded under us (trust click) — rebuild next call
            self._ws = None
            raise RuntimeError("cdp connection lost; retrying")
        result = reply.get("result", {})
        if result.get("exceptionDetails"):
            return {"__error__": result["exceptionDetails"].get("exceptionType", "exception")}
        value = result.get("result", {}).get("value")
        return value


def probe(page: Page) -> dict:
    return page.eval(
        """(() => {
  const modalBtns = [...document.querySelectorAll('.modal-container button')];
  const trust = modalBtns.find(b => /trust/i.test(b.innerText));
  const atlas = (typeof app !== 'undefined') ? app.plugins.plugins['atlas-vtt'] : null;
  const container = document.querySelector('.atlas-asset-manager-container');
  return {
    appReady: typeof app !== 'undefined',
    trustPresent: !!trust,
    atlasLoaded: !!atlas,
    managerOpen: !!container,
    containerPresent: !!container,
  };
})()"""
    ) or {}


def act_trust(page: Page) -> None:
    page.eval(
        """[...document.querySelectorAll('.modal-container button')]
     .find(b => /trust/i.test(b.innerText))?.click(); 'ok'"""
    )


def act_open_manager(page: Page) -> None:
    page.eval(
        "app.plugins.plugins['atlas-vtt']?.globalAssetManager?.open?.(); 'ok'"
    )


def act_maps_tab_and_drop(page: Page) -> str:
    result = page.eval(
        """(async () => {
  const log = [];
  try {
    // The import auto-opens the finished scene via `leaf.openFile`; the opened
    // map store then autosaves the full runtime envelope over the file. The
    // golden must stay the pure import output — `newSceneFile`'s envelope —
    // because that is what §3.3 holds the port to. Suppressing the open
    // touches nothing in the import's own write path.
    let proto = null;
    for (const t of ['empty', 'markdown']) {
      const leaf = app.workspace.getLeavesOfType(t)[0];
      if (leaf) { proto = Object.getPrototypeOf(leaf); break; }
    }
    if (proto && !proto.__goldenNoOpen) {
      proto.__goldenNoOpen = proto.openFile;
      proto.openFile = async () => {};
      log.push('leaf proto patched');
    } else if (!proto) {
      app.workspace.getLeaf = () => ({ openFile: async () => {} });
      log.push('getLeaf wrapped');
    }
  } catch (e) { log.push('open suppression skipped: ' + e.message); }
  const tab = [...document.querySelectorAll('.atlas-asset-manager-container button')]
    .find(b => /^Maps/.test(b.innerText.trim()));
  if (tab) { tab.click(); log.push('maps tab'); }
  await new Promise(r => setTimeout(r, 800));
  const buf = await app.vault.adapter.readBinary('Maps/sample.uvtt');
  const file = new File([buf], 'sample.uvtt');
  const dt = new DataTransfer();
  dt.items.add(file);
  const target = document.querySelector('.atlas-asset-manager-container');
  if (!target) return JSON.stringify({log, dropped: false, why: 'no container'});
  target.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: dt}));
  log.push('drop dispatched');
  return JSON.stringify({log, dropped: true, size: buf.byteLength});
})()""",
        await_promise=True,
    )
    print(f"  drop step: {result}")
    return str(result)


def wait_for_scene(vault: Path, deadline: float) -> Path | None:
    while time.time() < deadline:
        hits = list(vault.glob("atlas-vtt/collections/*/scenes/sample.atlasmap"))
        if hits:
            return hits[0]
        time.sleep(1.5)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version", help="Atlas release tag to capture, e.g. 0.7.1")
    ap.add_argument("--keep", action="store_true", help="leave Obsidian running")
    args = ap.parse_args()
    version = args.version

    if not OBSIDIAN_EXE.exists():
        print(f"Obsidian not found at {OBSIDIAN_EXE}", file=sys.stderr)
        return 2
    if not SAMPLE.exists():
        print(f"missing {SAMPLE}", file=sys.stderr)
        return 2

    cdp_kill_our_obsidian()
    time.sleep(3)  # let the killed instance's renderers drop their handles

    if cdp_port_taken(CDP_PORT):
        print(
            f"port {CDP_PORT} is already taken — refusing to launch anything.\n"
            "The capture clicks whatever answers on that DevTools port, and\n"
            "nothing distinguishes it from the instance this tool starts, so\n"
            "a foreign listener there (most likely your own Obsidian or\n"
            "another Chromium/Electron app started with remote debugging)\n"
            "would be driven in your real vault. Close whatever holds port\n"
            f"{CDP_PORT} and re-run.",
            file=sys.stderr,
        )
        return 2

    print(f"building vault for Atlas {version}")
    vault = build_vault(version)

    print("launching isolated Obsidian (owner's instance untouched)")
    subprocess.Popen(
        [
            str(OBSIDIAN_EXE),
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={CAP_DIR / 'appdata'}",
        ],
        cwd=str(vault),
    )
    deadline = time.time() + 120
    while time.time() < deadline:
        try:
            cdp_targets()
            break
        except Exception:
            time.sleep(2)
    else:
        print("CDP endpoint never came up", file=sys.stderr)
        return 3

    page = Page()
    dropped = False
    print("driving: trust -> asset manager -> Maps tab -> drop")
    while time.time() < deadline:
        try:
            state = probe(page)
        except RuntimeError:
            time.sleep(1.5)
            continue
        if state.get("__error__"):
            time.sleep(1.5)
            continue
        if state.get("trustPresent"):
            act_trust(page)
        elif not state.get("atlasLoaded"):
            pass  # wait for the plugin to finish loading
        elif not state.get("managerOpen"):
            act_open_manager(page)
        elif not dropped:
            # The drop handler in act_maps_tab_and_drop first no-ops
            # workspace.openFile: the UI import auto-opens the finished scene,
            # which materializes runtime state (widgets, initiative, fog…)
            # and autosaves it over the file. The golden must stay the pure
            # import output — `newSceneFile`'s envelope — because that is
            # what §3.3 holds the port to; the patch suppresses only the
            # post-import open, not the import's own write path.
            act_maps_tab_and_drop(page)
            dropped = True
        else:
            break
        time.sleep(1.5)

    scene = wait_for_scene(vault, time.time() + 60)
    if scene is None:
        print("no sample.atlasmap appeared in the vault", file=sys.stderr)
        print("vault tree was:", file=sys.stderr)
        for p in sorted(vault.rglob("*")):
            if ".obsidian" not in p.parts:
                print(f"  {p.relative_to(vault)}", file=sys.stderr)
        if not args.keep:
            cdp_kill_our_obsidian()
        return 4

    dest_dir = REPO / "fixtures" / f"golden-{version}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "sample.atlasmap"
    shutil.copy2(scene, dest)
    envelope = json.loads(dest.read_text(encoding="utf-8"))["state"]
    extra = set(envelope) - {
        "schema",
        "version",
        "background",
        "grid",
        "objects",
        "camera",
        "tokenSettings",
        "lighting",
    }
    if extra:
        dest.unlink()
        print(
            f"captured file carries non-import state keys {sorted(extra)} — "
            "the auto-open rewrote it; not committing a poisoned golden",
            file=sys.stderr,
        )
        if not args.keep:
            cdp_kill_our_obsidian()
        return 5
    print(f"captured {scene.name} -> {dest}")
    print(
        f"envelope: schema={envelope.get('schema')!r} version={envelope.get('version')!r}"
    )

    if not args.keep:
        cdp_kill_our_obsidian()
        print("isolated instance stopped")
    else:
        print(f"--keep: instance left running on :{CDP_PORT}")
    print(
        "remember: fill the fixtures/README.md capture table row "
        f"(version {version}, captured today, by tools/capture-golden.py)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
