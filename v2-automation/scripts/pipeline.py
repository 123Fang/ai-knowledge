"""scripts/pipeline.py — re-export 自 pipeline/pipeline.py

真实实现在 pipeline/pipeline.py 下。本文件保留 scripts/ 路径别名，
供 PPT 里按旧路径引用的代码能定位到。

也可直接运行：
    python3 scripts/pipeline.py --sources github --limit 5
"""

import importlib.util
import sys
from pathlib import Path

# 直接加载 pipeline/pipeline.py 这个具体文件，避开"pipeline 是包还是模块"的歧义
_real_path = Path(__file__).parent.parent / "pipeline" / "pipeline.py"
_spec = importlib.util.spec_from_file_location("pipeline_real", _real_path)
_real = importlib.util.module_from_spec(_spec)
sys.modules["pipeline_real"] = _real
_spec.loader.exec_module(_real)

# 重导出所有 public 符号
collect_github = _real.collect_github
collect_rss = _real.collect_rss
step_collect = _real.step_collect
step_analyze = _real.step_analyze
step_organize = _real.step_organize
step_save = _real.step_save
main = _real.main

if __name__ == "__main__":
    main()
