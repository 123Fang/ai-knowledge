"""scripts/model_client.py — re-export 自 pipeline/model_client.py

真实实现在 pipeline/model_client.py 下。本文件保留 scripts/ 路径别名，
供 PPT 里按旧路径引用的代码能定位到。
"""

import importlib.util
import sys
from pathlib import Path

_real_path = Path(__file__).parent.parent / "pipeline" / "model_client.py"
_spec = importlib.util.spec_from_file_location("model_client_real", _real_path)
_real = importlib.util.module_from_spec(_spec)
sys.modules["model_client_real"] = _real
_spec.loader.exec_module(_real)

create_provider = _real.create_provider
chat_with_retry = _real.chat_with_retry
estimate_cost = _real.estimate_cost
LLMResponse = _real.LLMResponse
