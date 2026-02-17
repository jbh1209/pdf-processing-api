import os

def get_rss_mb() -> float:
    """Best-effort RSS memory in MB for the current process (Linux containers)."""
    # Try /proc/self/status
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    # VmRSS: <kB>
                    kb = float(parts[1])
                    return kb / 1024.0
    except Exception:
        pass
    # Fallback: statm
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
            rss_pages = int(parts[1])
        page_size = os.sysconf("SC_PAGE_SIZE")
        return (rss_pages * page_size) / (1024.0 * 1024.0)
    except Exception:
        return 0.0

def get_loadavg():
    try:
        return os.getloadavg()
    except Exception:
        return (0.0, 0.0, 0.0)
