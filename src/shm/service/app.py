from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import threading
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from zoneinfo import ZoneInfo

from shm.personal.api import PrivateAPI, private_path
from shm.personal.domain import Invalid, Conflict, encoded

from shm.service.dashboard import build_dashboard, read_report
from shm.service.store import ServiceStore
from shm.service.workflow import MissedForwardWindow, latest_completed_session, run_daily_workflow
from shm.v04.profiles import STRATEGY_IDS


_TIME = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_STATIC = Path(__file__).with_name("static")


class RunService:
    def __init__(
        self,
        store: ServiceStore,
        repo_root: Path,
        *,
        timezone_name: str,
        retry_attempts: int,
        retry_delay_seconds: int,
        poll_seconds: int = 20,
    ) -> None:
        self.store = store
        self.repo_root = repo_root
        self.timezone_name = timezone_name
        self.retry_attempts = max(1, retry_attempts)
        self.retry_delay_seconds = max(0, retry_delay_seconds)
        self.poll_seconds = max(5, poll_seconds)
        self._guard = threading.Lock()
        self._active_run_id: int | None = None
        self._stop = threading.Event()
        self.personal = None

    def start(self) -> None:
        self.store.mark_interrupted_runs()
        threading.Thread(target=self._scheduler_loop, name="shm-scheduler", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        if self.personal:
            self.personal.ai.stop_event.set()

    def trigger(
        self,
        trigger: str,
        *,
        scheduled_for: str | None = None,
        parent_run_id: int | None = None,
    ) -> int:
        with self._guard:
            if self._active_run_id is not None:
                raise RuntimeError(f"run {self._active_run_id} is already active")
            if trigger == "scheduled" and scheduled_for:
                existing = self.store.find_scheduled_run(scheduled_for)
                if existing is not None:
                    return existing.id
            market_session = str(latest_completed_session().date())
            run_id = self.store.create_run(
                trigger=trigger,
                scheduled_for=scheduled_for,
                market_session=market_session,
                parent_run_id=parent_run_id,
            )
            self._active_run_id = run_id
            threading.Thread(
                target=self._execute,
                args=(run_id,),
                name=f"shm-run-{run_id}",
                daemon=True,
            ).start()
            return run_id

    def retry_failed(self, run_id: int) -> int:
        original = self.store.get_run(run_id)
        if original is None:
            raise ValueError("run not found")
        if original.status != "failed":
            raise ValueError("only failed runs can be retried")
        current_session = str(latest_completed_session().date())
        if original.market_session != current_session:
            raise ValueError(
                "this run is stale after a newer market close; use Run now for the current session"
            )
        return self.trigger("manual-retry", parent_run_id=run_id)

    def _execute(self, run_id: int) -> None:
        self.store.mark_running(run_id)
        last_error = ""
        try:
            for _ in range(self.retry_attempts):
                attempt = self.store.increment_attempt(run_id)

                def report(name, status, output, started_at, finished_at) -> None:
                    self.store.add_step(
                        run_id=run_id,
                        attempt=attempt,
                        name=name,
                        status=status,
                        started_at=started_at,
                        finished_at=finished_at,
                        output=output,
                    )

                try:
                    result = run_daily_workflow(self.repo_root, reporter=report)
                except MissedForwardWindow as exc:
                    self.store.finish_run(run_id, "failed", error=str(exc))
                    return
                except Exception as exc:
                    last_error = str(exc)
                    if attempt >= self.retry_attempts:
                        break
                    if self._stop.wait(self.retry_delay_seconds):
                        last_error = "service stopped during retry delay"
                        break
                else:
                    self.store.finish_run(run_id, "success", summary=result.summary)
                    return
            self.store.finish_run(run_id, "failed", error=last_error or "workflow failed")
        finally:
            if self.personal and self.personal.enabled:
                # The daily personal update follows all strategy attempts, including failures.
                try:
                    self.personal.refresh_after_strategy()
                except Exception:
                    try:
                        with self.personal.store.connection(True) as private_db:
                            private_db.execute('INSERT INTO audit(kind,payload,at) VALUES(?,?,?)', ('market_refresh_failed', '{}', datetime.now().isoformat()))
                    except Exception:
                        pass
            with self._guard:
                self._active_run_id = None

    def _scheduler_loop(self) -> None:
        timezone = ZoneInfo(self.timezone_name)
        while not self._stop.is_set():
            now = datetime.now(timezone)
            daily_time = self.store.get_setting("daily_time", "05:30") or "05:30"
            if _TIME.fullmatch(daily_time):
                hour, minute = (int(value) for value in daily_time.split(":"))
                if (now.hour, now.minute) >= (hour, minute):
                    scheduled_for = str(now.date())
                    if self.store.find_scheduled_run(scheduled_for) is None:
                        try:
                            self.trigger("scheduled", scheduled_for=scheduled_for)
                        except RuntimeError:
                            pass
            self._stop.wait(self.poll_seconds)


def _page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; background: #f4f6f8; color: #17202a; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 28px 18px 48px; }}
    h1 {{ margin: 0 0 20px; }} h2 {{ margin-top: 0; font-size: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(260px,1fr)); gap: 16px; }}
    .card {{ background: white; border-radius: 12px; padding: 18px; box-shadow: 0 2px 12px #17202a12; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th,td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid #e6e9ed; vertical-align: top; }}
    .success {{ color: #0a7a3d; }} .failed {{ color: #b42318; }} .running,.queued {{ color: #9a6700; }}
    .muted {{ color: #667085; }} .error {{ color: #b42318; white-space: pre-wrap; }}
    code,pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #101828; color: #f2f4f7; padding: 14px; border-radius: 8px; }}
    input,button {{ font: inherit; padding: 8px 10px; }} button {{ cursor: pointer; }}
    form.inline {{ display: inline-block; margin-right: 8px; }}
    a {{ color: #175cd3; text-decoration: none; }}
  </style>
</head>
<body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>""".encode()


def _handler(service: RunService):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def _send(self, status: HTTPStatus, body: bytes, content_type: str = "text/html") -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return  # A page reload can cancel an in-flight dashboard read.

        def _json(self, status: HTTPStatus, value) -> None:
            self._send(
                status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode(),
                "application/json",
            )

        def _redirect(self, message: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/?message=" + quote(message))
            self.end_headers()

        def _form(self) -> dict[str, str]:
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            return {key: items[-1] for key, items in values.items()}

        def _private(self, method):
            parsed = urlparse(self.path)
            if not private_path(parsed.path):
                return False
            private = service.personal
            if not private or not private.enabled:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "私人功能尚未启用：等待 HTTPS 认证网关配置及绕过验证"})
                return True
            if not private.authorized(self.headers, method):
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "请通过已认证的 HTTPS 入口访问"})
                return True
            try:
                payload = None
                if method == 'POST':
                    if parsed.path == '/api/personal/quotes/refresh' and service._active_run_id is not None:
                        raise Invalid('模拟任务正在更新行情；完成后会自动更新个人持仓，也可稍后重试')
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 1_000_000:
                        raise Invalid('请求长度无效或超过 1 MB')
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise Invalid('请求须为 JSON 对象')
                value = private.dispatch(method, parsed.path, parse_qs(parsed.query), payload)
                self._send(HTTPStatus.OK, encoded(value).encode(), 'application/json')
            except Conflict as exc:
                self._json(HTTPStatus.CONFLICT, {"error": str(exc)})
            except (Invalid, ValueError, KeyError, TypeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc) if isinstance(exc, Invalid) else "输入字段缺失或格式无效"})
            except Exception:
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "私人服务暂时不可用；账本未确认提交时请使用原提交编号重试"})
            return True

        def do_GET(self) -> None:
            if self._private('GET'):
                return
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/api/dashboard":
                try:
                    strategy_id = query.get("strategy_id", ["V04"])[-1]
                    cost_bps = int(query.get("cost_bps", ["10"])[-1])
                    if strategy_id not in ("V04", *STRATEGY_IDS) or cost_bps not in (10, 25):
                        raise ValueError("invalid strategy or cost scenario")
                except ValueError as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                try:
                    data = build_dashboard(service.repo_root, service.store, service.timezone_name,
                                           strategy_id=strategy_id, cost_bps=cost_bps)
                except (OSError, ValueError, KeyError) as exc:
                    self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
                else:
                    self._json(HTTPStatus.OK, data)
                return
            match = re.fullmatch(r"/api/runs/(\d+)", parsed.path)
            if match:
                run = service.store.get_run(int(match[1]))
                if run is None:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "运行记录不存在"})
                else:
                    self._json(HTTPStatus.OK, {
                        "run": asdict(run),
                        "steps": [asdict(step) for step in service.store.list_steps(run.id)],
                    })
                return
            if parsed.path.startswith("/api/reports/"):
                try:
                    report = read_report(service.repo_root, parsed.path.removeprefix("/api/reports/"),
                                         strategy_id=query.get("strategy_id", ["V04"])[-1])
                except FileNotFoundError:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "报告不存在"})
                except ValueError as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                else:
                    self._json(HTTPStatus.OK, report)
                return
            assets = {
                "/static/dashboard.js": "text/javascript",
                "/static/dashboard.css": "text/css",
                "/static/portfolio.js": "text/javascript",
                "/static/portfolio.css": "text/css",
            }
            if parsed.path in assets:
                self._send(
                    HTTPStatus.OK, (_STATIC / Path(parsed.path).name).read_bytes(),
                    assets[parsed.path],
                )
                return
            if parsed.path == "/favicon.ico":
                self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
                return
            if parsed.path == "/healthz":
                self._send(HTTPStatus.OK, b"ok\n", "text/plain")
                return
            if parsed.path == "/":
                self._send(HTTPStatus.OK, self._dashboard(parse_qs(parsed.query).get("message", [""])[-1]))
                return
            match = re.fullmatch(r"/runs/(\d+)", parsed.path)
            if match:
                self._send(HTTPStatus.OK, self._run_detail(int(match.group(1))))
                return
            self._send(HTTPStatus.NOT_FOUND, _page("Not found", "<p>页面不存在。</p>"))

        def do_POST(self) -> None:
            if self._private('POST'):
                return
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                self._json(HTTPStatus.FORBIDDEN, {"error": "请在当前仪表盘页面修改设置"})
                return
            if self.path == "/api/settings":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 4096 or self.headers.get_content_type() != "application/json":
                        raise ValueError("请提交 JSON 格式的时间设置")
                    payload = json.loads(self.rfile.read(length))
                    daily_time = payload["daily_time"]
                    if not isinstance(daily_time, str) or not _TIME.fullmatch(daily_time):
                        raise ValueError("执行时间格式必须是 HH:MM")
                except (ValueError, KeyError, TypeError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                service.store.set_setting("daily_time", daily_time)
                self._json(HTTPStatus.OK, {"daily_time": daily_time, "timezone": service.timezone_name})
                return
            if self.path == "/settings":
                daily_time = self._form().get("daily_time", "")
                if not _TIME.fullmatch(daily_time):
                    self._redirect("执行时间格式必须是 HH:MM")
                    return
                service.store.set_setting("daily_time", daily_time)
                self._redirect(f"每日执行时间已改为 {daily_time}")
                return
            if self.path == "/run-now":
                try:
                    run_id = service.trigger("manual")
                except Exception as exc:
                    self._redirect(str(exc))
                else:
                    self._redirect(f"已启动运行 #{run_id}")
                return
            match = re.fullmatch(r"/runs/(\d+)/rerun", self.path)
            if match:
                try:
                    run_id = service.retry_failed(int(match.group(1)))
                except Exception as exc:
                    self._redirect(str(exc))
                else:
                    self._redirect(f"已启动重跑 #{run_id}")
                return
            self._send(HTTPStatus.NOT_FOUND, _page("Not found", "<p>页面不存在。</p>"))

        def _dashboard(self, message: str) -> bytes:
            page = (_STATIC / "index.html").read_text()
            for name in ('dashboard.js', 'dashboard.css', 'portfolio.js', 'portfolio.css'):
                version = hashlib.sha256((_STATIC / name).read_bytes()).hexdigest()[:12]
                page = page.replace(f'/static/{name}"', f'/static/{name}?v={version}"')
            return page.encode()

        def _run_detail(self, run_id: int) -> bytes:
            run = service.store.get_run(run_id)
            if run is None:
                return _page("运行不存在", "<p><a href='/'>返回</a></p>")
            steps = service.store.list_steps(run_id)
            step_rows = "".join(
                f"<tr><td>{step.attempt}</td><td>{html.escape(step.name)}</td>"
                f"<td class='{html.escape(step.status)}'>{html.escape(step.status)}</td>"
                f"<td>{html.escape(step.started_at)}</td><td><pre>{html.escape(step.output or '')}</pre></td></tr>"
                for step in steps
            ) or "<tr><td colspan='5' class='muted'>尚无步骤记录</td></tr>"
            rerun = ""
            if run.status == "failed":
                rerun = (
                    f"<form class='inline' action='/runs/{run.id}/rerun' method='post'>"
                    "<button type='submit'>重跑此失败任务</button></form>"
                )
            body = f"""
<p><a href="/">← 返回</a></p>
<section class="card">
  <p><b>状态：</b><span class="{html.escape(run.status)}">{html.escape(run.status)}</span></p>
  <p><b>触发：</b>{html.escape(run.trigger)} · <b>市场日：</b>{html.escape(run.market_session or '-')}</p>
  <p><b>摘要：</b>{html.escape(run.summary or '-')}</p>
  <p class="error">{html.escape(run.error or '')}</p>{rerun}
</section>
<section class="card" style="margin-top:16px"><h2>步骤</h2>
<table><thead><tr><th>尝试</th><th>步骤</th><th>状态</th><th>开始</th><th>输出</th></tr></thead>
<tbody>{step_rows}</tbody></table></section>"""
            return _page(f"运行 #{run.id}", body)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shm-service")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(os.environ.get("SHM_REPO_ROOT", "/var/lib/shm/repository")).resolve()
    db_path = Path(os.environ.get("SHM_DB_PATH", "/var/lib/shm/service.sqlite3")).resolve()
    new_database = not db_path.exists()
    store = ServiceStore(db_path)
    store.initialize()
    default_time = os.environ.get("SHM_DAILY_TIME", "05:30")
    if new_database and _TIME.fullmatch(default_time):
        store.set_setting("daily_time", default_time)
    service = RunService(
        store,
        repo_root,
        timezone_name=os.environ.get("TZ", "Asia/Shanghai"),
        retry_attempts=int(os.environ.get("SHM_RETRY_ATTEMPTS", "3")),
        retry_delay_seconds=int(os.environ.get("SHM_RETRY_DELAY_SECONDS", "300")),
        poll_seconds=int(os.environ.get("SHM_SCHEDULER_POLL_SECONDS", "20")),
    )
    service.personal = PrivateAPI.from_environment(db_path, repo_root)
    if service.personal and service.personal.enabled:
        service.personal.ai.start()
    service.start()
    server = ThreadingHTTPServer((args.host, args.port), _handler(service))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
