from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import os
import time
import platform

from app.config import settings
from app.utils.runtime import get_rss_mb, get_loadavg
from app.utils.capacity import CapacityManager

router = APIRouter()

def _check_admin(request: Request) -> None:
    if not settings.admin_key:
        raise HTTPException(status_code=404, detail="Not found")
    key = request.query_params.get("key") or request.headers.get("X-Admin-Key")
    if key != settings.admin_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _get_capacity(request: Request) -> CapacityManager:
    mgr = getattr(request.app.state, "capacity_manager", None)
    if mgr is None:
        mgr = CapacityManager(max_concurrent=settings.max_concurrent_jobs, max_queue=settings.max_job_queue)
        request.app.state.capacity_manager = mgr
    return mgr

@router.get("/admin/status")
async def admin_status(request: Request):
    _check_admin(request)
    mgr = _get_capacity(request)
    snap = mgr.snapshot()
    uptime_s = int(time.time() - snap.started_at)
    return JSONResponse({
        "service": settings.api_title,
        "version": settings.api_version,
        "pid": os.getpid(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "uptime_seconds": uptime_s,
        "rss_mb": get_rss_mb(),
        "loadavg": get_loadavg(),
        "capacity": {
            "max_concurrent_jobs": snap.max_concurrent,
            "active_jobs": snap.active,
            "queued_jobs": snap.queued,
            "max_queue": snap.max_queue,
            "total_started": snap.total_started,
            "total_finished": snap.total_finished,
            "total_rejected": snap.total_rejected,
            "last_started_at": snap.last_started_at,
            "last_finished_at": snap.last_finished_at,
        }
    })

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    _check_admin(request)
    mgr = _get_capacity(request)
    snap = mgr.snapshot()
    rss = get_rss_mb()
    load1, load5, load15 = get_loadavg()
    uptime_s = int(time.time() - snap.started_at)

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{settings.api_title} • Admin</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; background:#0b1220; color:#e5e7eb; margin:0; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
    .card {{ background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.10); border-radius:16px; padding:16px; }}
    .grid {{ display:grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }}
    .span4 {{ grid-column: span 4; }}
    .span6 {{ grid-column: span 6; }}
    .span12 {{ grid-column: span 12; }}
    .k {{ color:#9ca3af; font-size:12px; text-transform: uppercase; letter-spacing:.12em; }}
    .v {{ font-size:28px; font-weight:700; margin-top:6px; }}
    .h1 {{ font-size: 22px; font-weight:700; margin: 8px 0 18px; }}
    .row {{ display:flex; justify-content:space-between; gap:10px; padding:10px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }}
    .row:last-child {{ border-bottom: none; }}
    .badge {{ display:inline-flex; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:600; background: rgba(0,184,212,0.18); color: #a5f3fc; border: 1px solid rgba(0,184,212,0.25); }}
    a {{ color:#7dd3fc; text-decoration:none; }}
    .muted {{ color:#9ca3af; font-size:13px; }}
    @media (max-width: 900px) {{
      .span4, .span6 {{ grid-column: span 12; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="h1">{settings.api_title} <span class="muted">v{settings.api_version}</span> <span class="badge">admin</span></div>

    <div class="grid">
      <div class="card span4">
        <div class="k">Active jobs</div>
        <div class="v">{snap.active}</div>
        <div class="muted">Max concurrent: {snap.max_concurrent}</div>
      </div>
      <div class="card span4">
        <div class="k">Queued jobs</div>
        <div class="v">{snap.queued}</div>
        <div class="muted">Max queue: {snap.max_queue}</div>
      </div>
      <div class="card span4">
        <div class="k">RSS memory</div>
        <div class="v">{rss:.0f} MB</div>
        <div class="muted">Watchdog: {'on' if settings.max_rss_mb else 'off'}</div>
      </div>

      <div class="card span6">
        <div class="k">System</div>
        <div class="row"><div>PID</div><div>{os.getpid()}</div></div>
        <div class="row"><div>Uptime</div><div>{uptime_s}s</div></div>
        <div class="row"><div>Load avg</div><div>{load1:.2f}, {load5:.2f}, {load15:.2f}</div></div>
        <div class="row"><div>Python</div><div>{platform.python_version()}</div></div>
      </div>

      <div class="card span6">
        <div class="k">Capacity counters</div>
        <div class="row"><div>Total started</div><div>{snap.total_started}</div></div>
        <div class="row"><div>Total finished</div><div>{snap.total_finished}</div></div>
        <div class="row"><div>Total rejected</div><div>{snap.total_rejected}</div></div>
        <div class="row"><div>Last started</div><div>{snap.last_started_at or '-'}</div></div>
        <div class="row"><div>Last finished</div><div>{snap.last_finished_at or '-'}</div></div>
      </div>

      <div class="card span12">
        <div class="k">Useful links</div>
        <div class="row"><div>JSON status</div><div><a href="/admin/status?key={settings.admin_key}">/admin/status</a></div></div>
        <div class="row"><div>Health</div><div><a href="/health">/health</a></div></div>
        <div class="row"><div>Docs</div><div><a href="/docs">/docs</a></div></div>
      </div>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(html)
