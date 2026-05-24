"""
pipelinelear.py — pipeline.py 的教学注释版

🧑‍🏫 这个文件是给前端开发者看懂 Python 流水线代码用的。
    每一行都加了详细注释，把 Python 语法类比到你熟悉的 JavaScript/TypeScript。

原文功能：AI 知识库四步流水线 — 采集 → 分析 → 整理 → 保存

运行方式（在终端里执行）：
    python3 pipeline/pipeline.py --sources github,rss --limit 20
    python3 pipeline/pipeline.py --sources github --limit 5 --dry-run
"""

# =============================================================================
# 第 0 节：导入库（import）—— 类比 JS 的 import
# =============================================================================

# Python 的 import 类似于 JS 的 import，但语法不同：
#   JS:  import fs from 'fs'
#   Python: import os       ← 导入整个模块（相当于 import * as os from 'os'）
#   Python: from datetime import datetime  ← 只导入某个成员（相当于 import { datetime } from 'datetime'）

from __future__ import annotations
# ↑ 开启"前向引用类型注解"，让 Python 可以用 str | None 这种简洁语法写类型。
#    类比：JS 用 JSDoc @type 写类型注释，Python 用类型注解（Type Hints）。

import argparse
# ↑ argparse 是 Python 内置的命令行参数解析库。
#    类比：JS 的 commander 或 yargs lib。
#    用它来解析 `--sources github,rss --limit 20` 这些参数。

import json
# ↑ Python 内置的 JSON 库，相当于 JS 的 JSON.parse() / JSON.stringify()

import logging
# ↑ Python 内置的日志库，相当于 JS 的 console.log，但更强大（可控制级别 INFO/WARNING/ERROR）

import os
# ↑ 操作系统接口库，用来读环境变量（os.getenv），类比 Node.js 的 process.env

import re
# ↑ 正则表达式库，相当于 JS 的 new RegExp() 和 .match()/.replace()

import sys
# ↑ 系统相关功能，这里主要用来修改模块搜索路径（sys.path）

from datetime import datetime, timezone
# ↑ datetime 是处理日期时间的类，相当于 JS 的 new Date()。
#    timezone 用来标记时区（UTC 等）。

from pathlib import Path
# ↑ Path 是处理文件路径的现代方式。
#    类比：Node.js 的 path.join() + fs.stat() 的结合体。
#    比如 Path("/foo/bar.txt").parent → "/foo"

from typing import Any
# ↑ typing 是 Python 的类型工具包。
#    Any 表示"任意类型"，相当于 TypeScript 的 any。

import httpx
# ↑ httpx 是一个第三方 HTTP 客户端库（需要 pip install httpx）。
#    类比：JS 的 axios 或 fetch。
#    支持同步请求、超时、连接池等。

import yaml
# ↑ PyYAML 库，用来解析 YAML 配置文件。
#    类比：JS 的 js-yaml 库。YAML 是 JSON 的"可读写法"。

from dotenv import load_dotenv
# ↑ python-dotenv 库，自动把 .env 文件里的配置加载成环境变量。
#    类比：Node.js 的 dotenv 包。

# =============================================================================
# sys.path 操作 —— 让 Python 能找到同级目录下的模块
# =============================================================================

sys.path.insert(0, str(Path(__file__).parent))
# ↑ __file__ 是 Python 的内置变量，始终等于当前文件的绝对路径。
#    Path(__file__).parent 就拿到了"当前文件所在的目录"。
#    sys.path.insert(0, ...) 把这个目录加到模块搜索路径的最前面。
#    效果：接下来 `from xxx import yyy` 会优先在这个目录找。
#    类比：Node.js 里用 require() 时，Node 自动搜索当前目录和 node_modules。

from model_client import create_provider, chat_with_retry, estimate_cost, LLMResponse
# ↑ 从同目录下的 model_client.py 导入几个函数/类。
#    create_provider   —— 工厂函数，创建 LLM 客户端
#    chat_with_retry   —— 带重试的聊天调用
#    estimate_cost     —— 估算 API 调用费用
#    LLMResponse       —— LLM 响应的数据类

from rss_reader import collect_rss  # noqa: F401 — 重导出供内部使用
# ↑ 从 rss_reader.py 导入 collect_rss 函数。
#    # noqa: F401 是告诉 lint 工具"不要报 F401 未使用的警告"。

load_dotenv()
# ↑ 加载 .env 文件的环境变量到 os.environ（即 process.env）
#    必须在使用 os.getenv() 之前调用。

logger = logging.getLogger(__name__)
# ↑ 创建一个日志记录器。__name__ 在直接运行此文件时是 "__main__"，被导入时是 "pipeline.pipeline"。
#    类比：创建了一个带命名空间的 console 对象。


# =============================================================================
# 项目路径常量 —— 相当于 JS 里的路径常量
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
# ↑ Path(__file__).parent          → 当前文件所在目录（pipeline/）
#   .parent                        → 再上一级（v2-automation/，即项目根目录）
#   PROJECT_ROOT 就是一个 Path 对象，代表项目根目录的路径

RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"
# ↑ Path 对象用 / 运算符拼接路径（Python 重载了 / 运算符）。
#    等价于 Node.js 的 path.join(projectRoot, "knowledge", "raw")
#    RAW_DIR 是原始数据的存放目录

ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"
# ↑ 标准化文章 JSON 文件的存放目录

RSS_CONFIG = Path(__file__).parent / "rss_sources.yaml"
# ↑ RSS 数据源配置文件路径


# =============================================================================
# Step 1: 采集（Collect）—— 从 GitHub API 拉取热门仓库
# =============================================================================

def collect_github(limit: int = 10) -> list[dict[str, Any]]:
    # ↑ def 是 Python 定义函数的关键字，相当于 JS 的 function 或 const fn = () => {}
    #   limit: int = 10              ← 参数名: 类型 = 默认值，相当于 TypeScript 的 limit: number = 10
    #   -> list[dict[str, Any]]      ← 返回类型注解，返回一个列表，每个元素是字典
    #   这里 list[dict[str, Any]] 相当于 TypeScript 的 Array<Record<string, any>>
    """
    从 GitHub 搜索 API 采集 AI 相关热门仓库。

    Args:
        limit: 最大采集数量

    Returns:
        原始数据列表
    """
    # ↑ 函数体内的三引号字符串叫 docstring（文档字符串），类似于 JSDoc 注释
    #   用 help(collect_github) 或 collect_github.__doc__ 就能看到它

    token = os.getenv("GITHUB_TOKEN", "")
    # ↑ 读取环境变量 GITHUB_TOKEN，如果没有就返回空字符串 ""
    #    类比：const token = process.env.GITHUB_TOKEN || ""
    #    这是用来访问 GitHub API 的认证令牌（不传也能用，但有速率限制）

    headers = {"Accept": "application/vnd.github.v3+json"}
    # ↑ Python 的字典（dict）用 {} 表示，类比 JS 的对象 {}
    #    这是 HTTP 请求头，告诉 GitHub 我们要 v3 版本的 JSON API

    if token:
        headers["Authorization"] = f"token {token}"
    # ↑ Python 的 if 语句不需要括号，用冒号和缩进来表示代码块
    #    类比：
    #      JS:  if (token) { headers["Authorization"] = `token ${token}`; }
    #      Python: if token:
    #                  headers["Authorization"] = f"token {token}"
    #
    #    f"token {token}" 是 Python 的 f-string（格式化字符串），
    #    相当于 JS 的 `token ${token}`（模板字符串）

    # 构造搜索的时间范围（最近一周）
    one_week_ago = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=7)).strftime("%Y-%m-%d")
    # ↑ 拆解一下这一行：
    #   datetime.now(timezone.utc)  → 获取当前 UTC 时间（类比 new Date() 但有时区）
    #   - timedelta(days=7)         → 减去 7 天（timedelta 是"时间差"）
    #   .strftime("%Y-%m-%d")       → 格式化成 "2026-05-17" 这样的字符串
    #   整个表达式 = "今天的日期 - 7天，格式化成 YYYY-MM-DD"
    #   __import__('datetime') 是动态导入 datetime 模块的写法

    query = f"ai agent llm stars:>100 pushed:>{one_week_ago}"
    # ↑ GitHub 搜索 API 的查询语法：
    #   "ai agent llm"    → 关键词匹配
    #   stars:>100        → 至少 100 个 star
    #   pushed:>2026-05-17 → 在此日期之后有推送（即最近一周活跃）

    url = "https://api.github.com/search/repositories"
    # ↑ GitHub 的仓库搜索 API 端点

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30),
    }
    # ↑ 查询参数：
    #   q          → 搜索查询字符串
    #   sort/order → 按 star 数降序排列
    #   per_page   → 每页返回条数，min(limit, 30) 是取 limit 和 30 中较小的值
    #   min(a, b) 是 Python 内置函数，返回较小的值。类比 JS 的 Math.min(a, b)

    results: list[dict[str, Any]] = []
    # ↑ 初始化一个空列表 []，用来存放采集结果
    #   类型注解 : list[dict[str, Any]] 表示"这是一个列表，每个元素是一个字典"

    try:
        # ↑ try...except 是 Python 的异常处理，类比 JS 的 try...catch
        #   try:      ← JS 的 try {
        #   except:   ← JS 的 } catch {
        #   具体异常类型写在 except 后面，如 except httpx.HTTPError as e:
        #       相当于 JS 的 catch(e) { if (e instanceof HTTPError) { ... } }

        with httpx.Client(timeout=30.0) as client:
            # ↑ with...as 是 Python 的"上下文管理器"（context manager）。
            #   这相当于 JS 里用 try { const client = new HttpClient(); ... } finally { client.close(); }
            #   httpx.Client 是一个 HTTP 客户端实例（可以复用连接）。
            #   timeout=30.0 表示 30 秒超时。
            #   走出 with 代码块后，client 会自动关闭释放资源。

            resp = client.get(url, params=params, headers=headers)
            # ↑ 发送 HTTP GET 请求。参数会自动拼接到 URL 上形成查询字符串。
            #    类比：axios.get(url, { params, headers })
            #    返回一个 Response 对象

            resp.raise_for_status()
            # ↑ 如果 HTTP 状态码是 4xx 或 5xx，自动抛出异常。
            #    类比 axios 里给 validateStatus 设了只接受 2xx。

            data = resp.json()
            # ↑ 把响应体解析成 Python 字典（因为返回的是 JSON）。
            #    类比 axios 自动解析的 response.data，或 fetch 后 await res.json()

            for i, repo in enumerate(data.get("items", [])[:limit]):
                # ↑ Python 的 for 循环：
                #   for i, repo in enumerate(xxx):
                #       ↓
                #   enumerate() 相当于给列表的每个元素加上索引。
                #   类比 JS 的：arr.forEach((repo, i) => { ... })
                #
                #   data.get("items", [])
                #       ↓
                #   字典的 .get() 方法：取 key="items" 的值，如果不存在则返回 []（默认值）。
                #   相当于 JS 的 data?.items ?? []
                #
                #   [:limit] 是 Python 的"切片（slice）"语法，取列表的前 limit 个元素。
                #   类比 JS 的 arr.slice(0, limit)
                #
                #   所以整个 for 行的含义：
                #   "遍历 items 数组的前 limit 个，i 是索引（从 0 开始），repo 是元素"

                now = datetime.now(timezone.utc).isoformat()
                # ↑ 获取当前 UTC 时间的 ISO 8601 格式字符串。
                #    比如 "2026-05-24T08:30:00.123456+00:00"
                #    .isoformat() 就相当于 JS 的 new Date().toISOString()

                results.append({
                    "id": f"github-{datetime.now().strftime('%Y%m%d')}-{i+1:03d}",
                    # ↑ f-string 里的 {i+1:03d} 格式化：数字 +1，用 0 补齐到 3 位
                    #    比如 i=0 → "001"，i=1 → "002"，i=99 → "100"
                    #    strftime('%Y%m%d')  → "20260524"（年月日紧凑格式）
                    "title": repo["full_name"],
                    # ↑ 字典取值用方括号 repo["key"]，相当于 JS 的 repo.key 或 repo["key"]
                    "source": "github",
                    "source_url": repo["html_url"],
                    "author": repo["owner"]["login"],
                    # ↑ 嵌套取值：repo["owner"] 返回一个字典，再取 ["login"]
                    #    相当于 JS: repo.owner.login
                    "published_at": repo.get("pushed_at", ""),
                    # ↑ .get("key", default) 安全取值，不存在就返回默认值
                    "raw_description": repo.get("description", "") or "",
                    # ↑ or "" 是为了把 None（Python 的 null）也转成空字符串
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "topics": repo.get("topics", []),
                    "collected_at": now,
                    # ↑ 采集时间戳
                })
                # ↑ list.append(item) 向列表末尾添加一个元素。相当于 JS 的 arr.push(item)

            logger.info("GitHub 采集完成: %d 条", len(results))
            # ↑ 记录一条 INFO 级别的日志。
            #    %d 是旧式字符串格式化（C 风格），会被 len(results) 替换。
            #    相当于 console.log(`GitHub 采集完成: ${results.length} 条`)
            #    推荐写法：logger.info("GitHub 采集完成: %d 条", len(results))

        except httpx.HTTPError as e:
            # ↑ 捕获所有 httpx 的 HTTP 错误。as e 相当于 JS 的 catch(e)。
            logger.error("GitHub API 调用失败: %s", e)
            # ↑ 记录错误日志。%s 会被 str(e) 替换。

        return results
        # ↑ Python 用 return 返回值，和 JS 一样。
        #    如果没有 return 或只写 return，函数默认返回 None（相当于 JS 的 undefined）


# =============================================================================
# collect_rss 已抽取到 pipeline/rss_reader.py
#   （详见 rss_readerlear.py 里的注释）
# =============================================================================


def step_collect(sources: list[str], limit: int) -> list[dict[str, Any]]:
    """
    Step 1: 按数据源采集原始数据。

    Args:
        sources: 数据源列表 ["github", "rss"]
        limit: 每个源的最大采集数

    Returns:
        合并后的原始数据列表
    """
    print(f"\n{'='*60}")
    # ↑ print() 相当于 console.log()
    #   {'='*60}   → 在 f-string 里，字符串 * 数字 = 重复拼接
    #   所以 '='*60 = "============================================================"
    #   相当于 JS 的 "=".repeat(60)

    print(f"📥 Step 1: 采集（sources={sources}, limit={limit}）")
    print(f"{'='*60}")

    all_items: list[dict[str, Any]] = []
    # ↑ 初始化总结果列表，后面会把 github 和 rss 的结果合并到这里

    if "github" in sources:
        # ↑ Python 的 in 运算符用于检查元素是否在列表中。
        #    相当于 JS 的 sources.includes("github")
        all_items.extend(collect_github(limit))
        # ↑ list.extend(other_list) 把另一个列表的所有元素追加到当前列表
        #    相当于 JS 的 arr.push(...otherArr)
        #    注意：extend vs append
        #      append(x) → 把 x 当作一个元素加进去 [1,2,[3,4]]
        #      extend(x) → 把 x 的元素逐个加进去     [1,2,3,4]

    if "rss" in sources:
        all_items.extend(collect_rss(limit))
        # ↑ collect_rss 是从 rss_reader.py 导入的函数

    # 保存原始数据到文件
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    # ↑ 创建目录。mkdir 是 make directory 的缩写。
    #   parents=True   → 递归创建父目录（类似 mkdir -p）
    #   exist_ok=True  → 如果目录已存在不报错

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # ↑ 格式化时间戳。%Y=年, %m=月, %d=日, %H=时, %M=分, %S=秒
    #    比如 "20260524_143000"

    raw_file = RAW_DIR / f"raw_{timestamp}.json"
    # ↑ Path 对象拼接。RAW_DIR / "xxx.json" 等价于 path.join(RAW_DIR, "xxx.json")

    with open(raw_file, "w", encoding="utf-8") as f:
        # ↑ 用 with 打开文件写入。as f 把文件对象赋值给变量 f。
        #   "w"     → write 模式（覆盖写入，不存在则创建）
        #   encoding="utf-8" → UTF-8 编码（确保中文不乱码）
        #   走出 with 块后，f 自动关闭。类比 JS 的 fs.writeFileSync 但异步关闭的。
        json.dump(all_items, f, ensure_ascii=False, indent=2)
        # ↑ 把 all_items（列表字典）序列化成 JSON 写入文件。
        #   ensure_ascii=False → 不转码非 ASCII 字符（保留中文）
        #   indent=2           → 缩进 2 空格，生成格式化的 JSON（pretty-print）
        #   类比：fs.writeFileSync("file.json", JSON.stringify(allItems, null, 2))

    print(f"  采集到 {len(all_items)} 条原始数据")
    # ↑ len() 返回列表/字符串的长度，相当于 JS 的 .length 属性
    print(f"  保存到 {raw_file}")

    return all_items
    # ↑ 返回采集到的所有原始数据，传给下一步


# =============================================================================
# Step 2: 分析（Analyze）—— 调用 LLM 对每条内容进行智能分析
# =============================================================================

ANALYZE_PROMPT_TEMPLATE = """请分析以下 AI 技术内容，返回 JSON 格式的分析结果。
# ↑ 三引号字符串可以跨多行，保留换行符。
#   变量名全大写是 Python 的命名习惯，表示这是一个"常量"（虽然 Python 没有真正的常量）。
#   这里的 {title}、{source}、{description} 是占位符，后面用 .format() 方法填充。

内容信息：
- 标题：{title}
- 来源：{source}
- 描述：{description}

请返回以下格式的 JSON（不要包含 markdown 代码块标记）：
{{
  "summary": "2-3 句话的技术摘要，说明核心内容和价值",
  "score": 7,
  "tags": ["tag1", "tag2"],
  "audience": "intermediate"
}}
# ↑ 注意：{ { 和 } }  是 Python 的转义写法。
#   f-string 里 {{ 表示输出一个字面的 {，所以在模板字符串里要双写。

评分标准（1-10）：
- 9-10: 突破性创新
- 7-8: 优秀技术分享
- 5-6: 普通有用信息
- 3-4: 内容较浅
- 1-2: 低质量

可用标签：agent, rag, mcp, llm, fine-tuning, prompt-engineering, multi-agent,
tool-use, evaluation, deployment, security, reasoning, code-generation, vision, audio

audience 可选值：beginner, intermediate, advanced"""


def step_analyze(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Step 2: 调用 LLM 对每条内容进行分析。

    Args:
        items: 原始数据列表

    Returns:
        带分析结果的数据列表
    """
    print(f"\n{'='*60}")
    print(f"🔍 Step 2: 分析（{len(items)} 条内容）")
    print(f"{'='*60}")

    provider = create_provider()
    # ↑ 调用工厂函数创建一个 LLM 提供商实例（DeepSeek/Qwen/OpenAI）
    #    类似 JS 的 const provider = createLLMClient()

    analyzed: list[dict[str, Any]] = []
    # ↑ 存放分析结果的列表

    total_cost = 0.0
    # ↑ 累计 API 调用费用（美元）。float 类型初始化为 0.0

    try:
        for i, item in enumerate(items):
            # ↑ 遍历每一条原始数据，enumerate 同时给出索引和元素
            print(f"  [{i+1}/{len(items)}] 分析: {item['title'][:50]}...")
            # ↑ item['title'][:50] → 取标题前 50 个字符（切片语法）
            #    防止标题太长塞满终端

            prompt = ANALYZE_PROMPT_TEMPLATE.format(
                title=item["title"],
                source=item["source"],
                description=item.get("raw_description", "无描述"),
            )
            # ↑ .format() 是 Python 的字符串格式化方法（Python 2 时代留下的，比 f-string 更灵活）。
            #   它会用括号里的参数替换模板中的 {title}、{source}、{description} 占位符。
            #   类比 JS 的模板字符串：
            #     const prompt = analyzePrompt
            #       .replace('{title}', item.title)
            #       .replace('{source}', item.source) ...
            #   或者用 lodash 的 _.template()

            try:
                # ↑ 内层 try，给每条目单独做异常处理——某一条失败不影响其他条

                response = chat_with_retry(
                    provider,
                    messages=[
                        {"role": "system", "content": "你是一个 AI 技术分析专家。请严格按要求返回 JSON。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    # ↑ temperature（温度）控制输出的随机性。范围 0-2。
                    #   0 = 确定性最高（总是选概率最高的词），1 = 平衡，2 = 很随机
                    #   这里设 0.3 表示希望输出稳定、格式规整
                    max_tokens=500,
                    # ↑ 最多生成 500 个 token（输出的文本长度上限）
                )
                # ↑ chat_with_retry 会调用 LLM API。如果网络失败会自动重试（最多 3 次）。

                cost = estimate_cost(provider.model, response.usage)
                # ↑ 根据用了多少 token 估算本次调用的费用
                total_cost += cost
                # ↑ 累加总费用（a += b 相当于 JS 的 a = a + b）

                # ── 解析 LLM 返回的 JSON ──
                content = response.content.strip()
                # ↑ .strip() 去掉字符串首尾的空白字符（空格、换行等）
                #    相当于 JS 的 str.trim()

                # 去除 LLM 返回里可能夹带的 markdown 代码块标记 ```json ... ```
                content = re.sub(r"^```json\s*", "", content)
                # ↑ re.sub 是正则替换，相当于 JS 的 str.replace(/^```json\s*/, "")
                content = re.sub(r"\s*```$", "", content)
                # ↑ 去掉末尾的 ```

                analysis = json.loads(content)
                # ↑ json.loads() → JSON 字符串 → Python 字典，相当于 JSON.parse()
                #   记忆口诀：loads = LOAD String，dumps = DUMP String

                # ── 合并原始数据和分析结果 ──
                enriched = {**item, **analysis}
                # ↑ {**a, **b} 是 Python 3.5+ 的"字典解包合并"语法。
                #    效果：把 a 和 b 的所有键值对合并到一个新字典。后面覆盖前面。
                #    相当于 JS 的 { ...item, ...analysis }
                #    比如：{**{"a":1}, **{"a":2, "b":3}} → {"a":2, "b":3}

                enriched["status"] = "review"
                # ↑ 给字典加一个新键值对，相当于 JS 的 enriched.status = "review"
                enriched["analyzed_at"] = datetime.now(timezone.utc).isoformat()
                analyzed.append(enriched)
                # ↑ 把分析完的数据加入结果列表

            except (json.JSONDecodeError, KeyError) as e:
                # ↑ except 后面跟元组 () 可以捕获多种异常类型
                #   json.JSONDecodeError → JSON 解析失败（LLM 返回了非法 JSON）
                #   KeyError            → 字典取不存在的 key（比如 item 里缺了 title）
                #   as e → 把异常对象赋值给 e
                logger.warning("分析结果解析失败: %s — %s", item["title"], e)

                # 解析失败时使用默认值（兜底策略）
                enriched = {
                    **item,
                    "summary": item.get("raw_description", "")[:200],
                    # ↑ 取原始描述的前 200 字符作为摘要
                    "score": 5,
                    # ↑ 默认给 5 分（中等）
                    "tags": ["llm"],
                    # ↑ 默认标签
                    "audience": "intermediate",
                    # ↑ 默认标注为中级
                    "status": "draft",
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
                analyzed.append(enriched)

    finally:
        # ↑ finally 块无论如何都会执行（无论是否有异常）
        #    类比 JS 的 try { ... } finally { ... }
        provider.close()
        # ↑ 关闭 HTTP 客户端连接，释放资源

    print(f"  分析完成: {len(analyzed)} 条")
    print(f"  估算总成本: ${total_cost:.6f}")
    # ↑ :.6f → 浮点数格式化成 6 位小数，比如 $0.002400

    return analyzed


# =============================================================================
# Step 3: 整理（Organize）—— 去重、格式化、质量把关
# =============================================================================

def step_organize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Step 3: 去重、格式化、校验。

    Args:
        items: 带分析结果的数据列表

    Returns:
        整理后的数据列表
    """
    print(f"\n{'='*60}")
    print(f"📋 Step 3: 整理（{len(items)} 条内容）")
    print(f"{'='*60}")

    # ── 去重：按 source_url 去重 ──
    seen_urls: set[str] = set()
    # ↑ set 是 Python 的"集合"类型（无序、不重复的元素集合）。
    #    相当于 JS 的 new Set()
    #    用 set 来记住已经见过的 URL，重复的就跳过。

    unique: list[dict[str, Any]] = []

    # 先读取已有文章的 URL（避免写入重复数据）
    if ARTICLES_DIR.exists():
        # ↑ Path.exists() 检查目录是否存在
        for f in ARTICLES_DIR.glob("*.json"):
            # ↑ .glob("*.json") → 匹配目录下所有 .json 文件
            #    类比 Node.js 的 glob 模式匹配，或 fs.readdirSync + filter
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    # ↑ "r" = read 模式（只读），fh 是文件句柄
                    existing = json.load(fh)
                    # ↑ json.load() → 从文件读取并解析 JSON
                    #    记忆口诀：load = LOAD from file，loads = LOAD from String
                    if "source_url" in existing:
                        # ↑ in 字典时检查 key 是否存在
                        seen_urls.add(existing["source_url"])
                        # ↑ set.add() 向集合添加元素。重复添加无效果。
            except (json.JSONDecodeError, IOError):
                pass
                # ↑ pass 是 Python 的空语句（什么都不做），占位用。
                #    遇到解析失败的文件跳过就行，不中断流程。

    dedup_count = 0
    # ↑ 记录去重掉了多少条

    for item in items:
        url = item.get("source_url", "")
        if url in seen_urls:
            # ↑ 检查 url 是否在 seen_urls 集合中
            dedup_count += 1
            continue
            # ↑ continue 跳过当前循环迭代，进入下一个 item
            #    相当于 JS 的 continue
        seen_urls.add(url)
        unique.append(item)
        # ↑ 不是重复的，加入去重后的结果列表

    # ── 格式标准化 ──
    organized: list[dict[str, Any]] = []
    for item in unique:
        article = {
            "id": item.get("id", "unknown-000"),
            "title": item.get("title", ""),
            "source": item.get("source", "unknown"),
            "source_url": item.get("source_url", ""),
            "author": item.get("author", "unknown"),
            "published_at": item.get("published_at", ""),
            "collected_at": item.get("collected_at", ""),
            "summary": item.get("summary", ""),
            "score": max(1, min(10, item.get("score", 5))),
            # ↑ max(1, min(10, score)) → 把 score 钳制在 1-10 范围
            #   min(10, score)  → 如果 score > 10，返回 10
            #   max(1, min_ed)  → 如果 min_ed < 1，返回 1
            #   最终 score 范围 [1, 10]
            #   相当于 JS 的 Math.max(1, Math.min(10, score))
            "tags": item.get("tags", []),
            "audience": item.get("audience", "intermediate"),
            "status": item.get("status", "draft"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        organized.append(article)

    print(f"  去重: 移除 {dedup_count} 条重复")
    print(f"  整理后: {len(organized)} 条")

    return organized


# =============================================================================
# Step 4: 保存（Save）—— 把文章写入独立 JSON 文件
# =============================================================================

def step_save(items: list[dict[str, Any]], dry_run: bool = False) -> list[Path]:
    """
    Step 4: 将文章保存为独立 JSON 文件。

    Args:
        items: 整理后的文章列表
        dry_run: 仅模拟，不实际写入

    Returns:
        已保存的文件路径列表
    """
    print(f"\n{'='*60}")
    print(f"💾 Step 4: 保存（{len(items)} 条内容，dry_run={dry_run}）")
    print(f"{'='*60}")

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    # ↑ 确保目录存在

    saved_files: list[Path] = []
    # ↑ 用 Path 对象列表来记录保存的文件路径

    for item in items:
        filename = f"{item['id']}.json"
        # ↑ 文件名 = 文章 ID + ".json"，比如 "github-20260524-001.json"
        filepath = ARTICLES_DIR / filename
        # ↑ 拼接完整路径

        if dry_run:
            print(f"  [DRY RUN] 将保存: {filepath}")
            # ↑ dry_run=True 时只打印，不写文件（模拟运行模式）
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(item, f, ensure_ascii=False, indent=2)
            print(f"  已保存: {filepath}")

        saved_files.append(filepath)

    print(f"\n  共 {'模拟' if dry_run else ''}保存 {len(saved_files)} 个文件")
    # ↑ Python 的三元表达式：A if condition else B
    #    相当于 JS 的 condition ? A : B

    return saved_files


# =============================================================================
# 主流程：把四个步骤串起来
# =============================================================================

def run_pipeline(
    sources: list[str],
    limit: int = 20,
    dry_run: bool = False,
    steps: list[int] | None = None,
    # ↑ list[int] | None 表示参数要么是整数列表，要么是 None（Python 3.10+ 语法）。
    #   相当于 TypeScript 的 steps?: number[] | null
) -> dict[str, Any]:
    """
    运行完整的四步流水线。

    Args:
        sources: 数据源列表
        limit: 每个源的最大采集数
        dry_run: 仅模拟运行
        steps: 要执行的步骤列表（1-4），默认全部执行

    Returns:
        运行统计信息
    """
    run_steps = set(steps) if steps else {1, 2, 3, 4}
    # ↑ Python 的三元表达式：X if 条件 else Y
    #   set(steps) → 把 list 转成 set（顺便去重）
    #   {1, 2, 3, 4} → 这是集合字面量（set literal），注意和字典的区别
    #      {}       → 空字典
    #      {1,2,3}  → 集合（三个元素）
    #      {"a":1}  → 字典（有冒号的键值对）

    start_time = datetime.now()
    # ↑ 记录流水线开始时间，用于最后计算耗时

    print(f"\n{'#'*60}")
    print(f"# AI 知识库流水线 — {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# 数据源: {', '.join(sources)} | 限制: {limit} | DryRun: {dry_run}")
    # ↑ ', '.join(sources) → 用逗号+空格把列表拼接成字符串
    #    相当于 JS 的 sources.join(', ')
    print(f"# 执行步骤: {sorted(run_steps)}")
    # ↑ sorted() 返回排序后的列表
    print(f"{'#'*60}")

    # 初始化各步骤的结果变量
    raw_items: list[dict] = []
    analyzed_items: list[dict] = []
    organized_items: list[dict] = []
    saved_files: list[str] = []

    # Step 1: 采集
    if 1 in run_steps:
        raw_items = step_collect(sources, limit)
        if not raw_items:
            # ↑ Python 的空列表/空字符串/None/0 在 if 中都算 Falsy
            #    if not raw_items 的意思是"如果 raw_items 是空的"
            #    相当于 JS 的 if (!rawItems.length)
            print("\n⚠️  没有采集到任何数据，流水线结束。")
            return {"collected": 0, "analyzed": 0, "saved": 0}
            # ↑ Python 可以直接 return 一个字典字面量，不需要先声明变量

    # Step 2: 分析
    if 2 in run_steps and raw_items:
        # ↑ and 是短路运算：只有左边为 True 才评估右边
        #    保证了 raw_items 非空才进入分析
        analyzed_items = step_analyze(raw_items)

    # Step 3: 整理
    if 3 in run_steps and analyzed_items:
        organized_items = step_organize(analyzed_items)

    # Step 4: 保存
    if 4 in run_steps and organized_items:
        saved_files = step_save(organized_items, dry_run=dry_run)

    # ── 统计汇总 ──
    elapsed = (datetime.now() - start_time).total_seconds()
    # ↑ (结束时间 - 开始时间) 返回 timedelta 对象，.total_seconds() 转成秒
    #    相当于 JS 的 (Date.now() - startTime) / 1000

    stats = {
        "collected": len(raw_items),
        "analyzed": len(analyzed_items),
        "organized": len(organized_items),
        "saved": len(saved_files),
        "elapsed_seconds": round(elapsed, 1),
        # ↑ round(数字, 小数点位数) → 四舍五入
        #    相当于 JS 的 Math.round(elapsed * 10) / 10 或 Number(elapsed.toFixed(1))
        "dry_run": dry_run,
    }

    print(f"\n{'#'*60}")
    print(f"# 流水线完成！耗时 {elapsed:.1f} 秒")
    # ↑ :.1f → 格式化为 1 位小数
    print(f"# 采集: {stats['collected']} → 分析: {stats['analyzed']} "
          f"→ 整理: {stats['organized']} → 保存: {stats['saved']}")
    # ↑ 两个相邻的 f-string 会被 Python 自动拼接成一个字符串
    print(f"{'#'*60}\n")

    return stats


# =============================================================================
# CLI 入口 —— 让脚本可以从命令行运行
# =============================================================================

def main() -> None:
    # ↑ -> None 表示这个函数不返回任何有意义的值（类似 TypeScript 的 void）

    parser = argparse.ArgumentParser(
        # ↑ 创建命令行参数解析器
        description="AI 知识库采集流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # ↑ 让帮助文本保留原始格式（不自动折行）
        epilog="""
示例:
    python3 pipeline/pipeline.py --sources github,rss --limit 20
    python3 pipeline/pipeline.py --sources github --limit 5 --dry-run
    python3 pipeline/pipeline.py --sources rss --limit 10
        """,
        # ↑ epilog 是帮助信息的末尾附加文本
    )

    parser.add_argument(
        "--sources",
        type=str,
        # ↑ 参数类型是字符串
        default="github,rss",
        # ↑ 默认值：同时采集 GitHub 和 RSS
        help="数据源，逗号分隔（默认: github,rss）",
    )

    parser.add_argument(
        "--limit",
        type=int,
        # ↑ 参数类型是整数。argparse 会自动把 "20" 转成 int 20
        default=20,
        help="每个源的最大采集数量（默认: 20）",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        # ↑ action="store_true" 表示这是一个布尔开关 —— 写了这个参数就设为 True，不写就 False
        #    `--dry-run` 出现在命令行 → args.dry_run = True
        #    `--dry-run` 不出现      → args.dry_run = False
        help="仅模拟运行，不实际保存文件",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细日志",
    )

    parser.add_argument(
        "--step",
        type=int,
        action="append",
        # ↑ action="append" 表示可以多次使用这个参数，值会累积到列表里
        #    比如 --step 1 --step 2 → args.step = [1, 2]
        help="指定执行的步骤（1-4），可多次使用，如 --step 1 --step 2",
    )

    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        # ↑ 默认 None，表示如果没有指定就用环境变量的值
        help="LLM 提供商（deepseek/qwen/openai），覆盖环境变量 LLM_PROVIDER",
    )

    args = parser.parse_args()
    # ↑ parse_args() 解析 sys.argv（命令行参数列表），返回一个 Namespace 对象
    #    然后可以用 args.sources, args.limit 等来取参数值
    #    类比 JS：const args = commander.parse(process.argv)

    # 如果命令行指定了 --provider，就覆盖到环境变量
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
        # ↑ os.environ 是一个字典，操作它就像操作 process.env

    # 配置日志级别和格式
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        # ↑ verbose 开启时用 DEBUG 级别（输出所有日志），否则用 INFO 级别
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        # ↑ 日志格式模板。%(xxx)s 是旧式占位符：
        #   %(asctime)s   → 时间戳
        #   %(levelname)s → 日志级别（INFO/WARNING/ERROR）
        #   %(name)s      → 日志记录器名称（"pipeline.pipeline"）
        #   %(message)s   → 日志消息主体
        datefmt="%H:%M:%S",
        # ↑ 时间格式：只显示时:分:秒
    )

    sources = [s.strip() for s in args.sources.split(",")]
    # ↑ 这行是 Python 的"列表推导式（List Comprehension）"，一步完成拆分+去除空白：
    #   1. args.sources.split(",")  → 按逗号分割字符串，得到 ["github", " rss"]
    #   2. for s in ["github", " rss"]  → 遍历每个元素
    #   3. s.strip()  → 去掉首尾空白（" rss" 变成 "rss"）
    #   4. [s.strip() for s in ...]  → 收集到一个新列表
    #
    #   相当于 JS 的：
    #     args.sources.split(",").map(s => s.trim())

    run_pipeline(
        sources=sources,
        limit=args.limit,
        dry_run=args.dry_run,
        steps=args.step,
    )
    # ↑ 调用主流程函数，传入解析好的参数


if __name__ == "__main__":
    # ↑ __name__ 是 Python 的内置变量，表示当前模块的名字。
    #   当这个文件被直接运行时（比如 python3 pipeline.py），__name__ 等于 "__main__"
    #   当这个文件被 import 导入时，__name__ 等于模块名（比如 "pipeline.pipeline"）
    #
    #   所以这个 if 语句的作用：只有直接运行本文件时才执行 main()，被 import 时不执行。
    #
    #   类比 JS 中这个常见模式：
    #     if (require.main === module) { main(); }
    #   或者今天更常见的 cli 入口文件分离做法。
    main()
