"""scripts/rss_reader.py — re-export 自 pipeline/rss_reader.py

真实实现在 pipeline/rss_reader.py 下。本文件保留 scripts/ 路径别名，
供 PPT 里按旧路径引用的代码能定位到。
"""

import importlib.util
import sys
from pathlib import Path

_real_path = Path(__file__).parent.parent / "pipeline" / "rss_reader.py"
_spec = importlib.util.spec_from_file_location("rss_reader_real", _real_path)
_real = importlib.util.module_from_spec(_spec)
sys.modules["rss_reader_real"] = _real
_spec.loader.exec_module(_real)

collect_rss = _real.collect_rss
RSS_CONFIG = _real.RSS_CONFIG

if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    items = collect_rss(limit=10)
    print(f"采集到 {len(items)} 条 RSS 条目")
    for i, item in enumerate(items[:5], 1):
        print(f"  {i}. [{item['source']}] {item['title'][:60]}")
