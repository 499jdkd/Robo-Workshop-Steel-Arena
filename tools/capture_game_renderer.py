"""Capture the real GPU game client via Chrome's testing protocol (no player data)."""

import argparse
import base64
import functools
import http.server
import json
from pathlib import Path
import subprocess
import threading
import time
import psutil
from urllib.request import urlopen

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]

AUDIO_OBSERVER = r"""
(()=>{
 const events=window.__roboAudio=[];let serial=0;
 function identify(el){if(!el.__roboId){el.__roboId=++serial;el.addEventListener('ended',()=>log('ended',el));}return el.__roboId;}
 function log(kind,el,extra={}){if(events.length<4000)events.push({kind,id:identify(el),ms:performance.now(),src:el.currentSrc||el.src,pos:el.currentTime,duration:el.duration,...extra});}
 const play=HTMLMediaElement.prototype.play,pause=HTMLMediaElement.prototype.pause;
 HTMLMediaElement.prototype.play=function(...args){log('play',this);const el=this;return Promise.resolve(play.apply(this,args)).then(v=>{log('playing',el);return v;},e=>{log('blocked',el,{error:e.name});throw e;});};
 HTMLMediaElement.prototype.pause=function(...args){log('pause',this);return pause.apply(this,args);};
 const source=AudioContext.prototype.createMediaElementSource;
 AudioContext.prototype.createMediaElementSource=function(el){const n=source.call(this,el);n.__roboElement=el;return n;};
 const connect=AudioNode.prototype.connect;
 AudioNode.prototype.connect=function(dest,...args){if(this.__roboElement&&dest instanceof GainNode){dest.__roboElement=this.__roboElement;dest.gain.__roboElement=this.__roboElement;}return connect.call(this,dest,...args);};
 const value=Object.getOwnPropertyDescriptor(AudioParam.prototype,'value');
 Object.defineProperty(AudioParam.prototype,'value',{get:value.get,set:function(v){if(this.__roboElement)log('gain',this.__roboElement,{gain:v});return value.set.call(this,v);}});
})();
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="before")
    parser.add_argument("--port", type=int, default=18552)
    parser.add_argument(
        "--client", type=Path, default=ROOT / "tools/game_client/build/web"
    )
    parser.add_argument("--width", type=int, default=844)
    parser.add_argument("--height", type=int, default=390)
    parser.add_argument("--dpr", type=float, default=1)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--network", action="store_true", help="Record verbose network events for startup diagnosis")
    parser.add_argument("--audio-observe", action="store_true", help="Observe actual browser media playback without replacing the audio engine")
    args = parser.parse_args()
    out = ROOT / ".cache/rework-review" / args.name
    out.mkdir(parents=True, exist_ok=True)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    httpd = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(args.client))
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not chrome.exists():
        chrome = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    log = (out / "chrome.log").open("w")
    child = subprocess.Popen(
        [
            str(chrome),
            "--headless=new",
            "--no-first-run",
            "--remote-debugging-port=19225",
            "--remote-allow-origins=http://localhost",
            f"--user-data-dir={out.resolve() / 'chrome-profile'}",
            "--hide-scrollbars",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "about:blank",
        ],
        stdout=log,
        stderr=log,
    )
    events = []
    memory = []
    try:
        for _ in range(100):
            try:
                tabs = json.load(urlopen("http://127.0.0.1:19225/json", timeout=1))
                target = next(t for t in tabs if t["type"] == "page")
                break
            except (OSError, StopIteration):
                time.sleep(0.1)
        with connect(
            target["webSocketDebuggerUrl"],
            origin="http://localhost",
            max_size=40_000_000,
        ) as ws:
            counter = 0

            def call(method, params=None):
                nonlocal counter
                counter += 1
                identity = counter
                ws.send(
                    json.dumps(
                        {"id": identity, "method": method, "params": params or {}}
                    )
                )
                while True:
                    value = json.loads(ws.recv(timeout=30))
                    if value.get("id") == identity:
                        if "error" in value:
                            raise RuntimeError(value)
                        return value.get("result", {})
                    events.append(value)

            call("Runtime.enable")
            call("Page.enable")
            if args.network:
                call("Network.enable")
            call(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": args.width,
                    "height": args.height,
                    "deviceScaleFactor": args.dpr,
                    "mobile": False,
                },
            )
            if args.audio_observe:
                call('Page.addScriptToEvaluateOnNewDocument',{'source':AUDIO_OBSERVER})
            call(
                "Page.navigate",
                {
                    "url": f"http://127.0.0.1:{httpd.server_port}/?server=http://127.0.0.1:{args.port}"
                },
            )
            call("Performance.enable")
            capture_began = time.monotonic()
            gestures=0
            for seconds in (
                10,
                max(1, (args.seconds - 10) / 2),
                max(1, (args.seconds - 10) / 2),
            ):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if args.audio_observe and gestures<2 and time.monotonic()-capture_began>1.6+gestures:
                        call('Input.dispatchMouseEvent',{'type':'mousePressed','x':195,'y':300,'button':'left','clickCount':1,'buttons':1})
                        call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':195,'y':300,'button':'left','clickCount':1,'buttons':0})
                        gestures+=1
                    try:
                        events.append(json.loads(ws.recv(timeout=min(.2, max(.001, deadline-time.monotonic())))))
                    except TimeoutError:
                        pass
                image = call(
                    "Page.captureScreenshot",
                    {"format": "png", "captureBeyondViewport": False},
                )
                (out / f"frame-{counter}.png").write_bytes(
                    base64.b64decode(image["data"])
                )
                processes = [psutil.Process(child.pid), *psutil.Process(child.pid).children(recursive=True)]
                info = []
                for process in processes:
                    try:
                        m = process.memory_info()
                        info.append({'pid':process.pid, 'rss_bytes':m.rss, 'private_bytes':getattr(m,'private',0)})
                    except psutil.Error:
                        pass
                perf = call('Performance.getMetrics')
                values = {m['name']:m['value'] for m in perf['metrics']}
                memory.append({'elapsed_seconds':round(time.monotonic()-capture_began,2),
                               'chrome_processes':len(info),
                               'chrome_rss_bytes':sum(m['rss_bytes'] for m in info),
                               'chrome_private_bytes':sum(m['private_bytes'] for m in info),
                               'js_heap_used_bytes':values.get('JSHeapUsedSize')})
            result = call(
                "Runtime.evaluate",
                {
                    "expression": "JSON.stringify({title:document.title,resources:performance.getEntriesByType('resource').map(e=>({name:e.name,size:e.transferSize,start_ms:e.startTime,duration_ms:e.duration,decoded_bytes:e.decodedBodySize})),text:document.body.innerText})",
                    "returnByValue": True,
                },
            )
            (out / "runtime.json").write_text(
                json.dumps(
                    {"page": result, "events": events}, ensure_ascii=False, indent=2
                ),
                encoding="utf8",
            )
            if args.audio_observe:
                observed=call('Runtime.evaluate',{'expression':'JSON.stringify(window.__roboAudio)','returnByValue':True})
                (out/'audio-events.json').write_text(observed['result']['value'],encoding='utf-8')
        (out / 'memory.json').write_text(json.dumps({
            'measurement':'Windows Chrome process-tree working/private bytes and CDP JS heap snapshots; includes browser/renderer overhead, not Android or Dart-only memory',
            'samples':memory,
            'max_chrome_rss_bytes':max(s['chrome_rss_bytes'] for s in memory),
            'max_chrome_private_bytes':max(s['chrome_private_bytes'] for s in memory),
        },indent=2),encoding='utf-8')
        print(out, flush=True)
    finally:
        child.terminate()
        child.wait(timeout=10)
        httpd.shutdown()
        log.close()


if __name__ == "__main__":
    main()
