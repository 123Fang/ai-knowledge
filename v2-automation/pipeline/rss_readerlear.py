"""
rss_readerlear.py — rss_reader.py 的教学注释版

🧑‍🏫 这个文件是给前端开发者看懂 Python 代码用的。
    涵盖知识点：正则解析 XML、YAML 配置文件读取、HTTP 请求、文件路径处理。

原文功能：RSS 数据源采集模块。
         从配置的 RSS 源采集内容，配置文件见 pipeline/rss_sources.yaml。

什么是 RSS？
  RSS（Really Simple Syndication）是一种 XML 格式的"订阅源"协议。
  博客、新闻网站通过 RSS 提供文章标题、链接、摘要。
  类比：你订阅的微信公众号，但 RSS 是开放标准。
  一个典型的 RSS 条目长得像这样：
    <item>
      <title>用 Python 构建 AI Agent</title>
      <link>https://example.com/blog/ai-agent</link>
      <description>本文介绍如何...</description>
    </item>
"""

from __future__ import annotations
# ↑ 开启前向引用类型注解。

import logging
# ↑ 日志库。

import re
# ↑ 正则表达式库。用来从 XML 中提取标题和链接。

from datetime import datetime, timezone
# ↑ 时间和时区处理。

from pathlib import Path
# ↑ 现代文件路径处理。

from typing import Any
# ↑ 通用类型。

import httpx
# ↑ HTTP 客户端，类比 axios。

import yaml
# ↑ YAML 解析器。

logger = logging.getLogger(__name__)
# ↑ 创建日志记录器。


RSS_CONFIG = Path(__file__).parent / "rss_sources.yaml"
# ↑ 获取 RSS 源配置文件的路径。
#   __file__           → 当前文件的绝对路径
#   Path(__file__).parent → 当前文件所在目录（pipeline/）
#   最后用 / 运算符拼接上文件名
#   结果路径类似：/Users/xxx/v2-automation/pipeline/rss_sources.yaml


def collect_rss(limit: int = 10) -> list[dict[str, Any]]:
    """
    从配置的 RSS 源采集内容。

    Args:
        limit: 最大采集数量（所有源合计）

    Returns:
        原始数据列表，每条包含 id/title/source/source_url 等字段
    """

    # ── 1. 读取 RSS 源配置文件 ──
    if not RSS_CONFIG.exists():
        # ↑ Path.exists() 检查文件是否存在。
        #   如果配置文件不存在，记录警告并返回空列表。
        logger.warning("RSS 配置文件不存在: %s", RSS_CONFIG)
        return []

    with open(RSS_CONFIG, "r", encoding="utf-8") as f:
        # ↑ 用 with 语句打开文件（自动关闭），"r" = 只读模式。
        config = yaml.safe_load(f)
        # ↑ yaml.safe_load() 把 YAML 字符串解析成 Python 字典。
        #   safe_load 比 load 更安全（不会执行任意 Python 代码）。
        #   类比 JS: const config = yaml.parse(fs.readFileSync(...))

    sources = [s for s in config.get("sources", []) if s.get("enabled", True)]
    # ↑ 列表推导式 + 过滤：
    #   1. config.get("sources", [])  → 取配置中的 sources 列表，不存在返回 []
    #   2. for s in xxx               → 遍历每个源
    #   3. if s.get("enabled", True)  → 过滤：只保留 enabled 为 True 的源
    #                                     如果源对象没有 enabled 字段，默认为 True（启用）
    #   相当于 JS：
    #     const sources = (config.sources || []).filter(s => s.enabled !== false)

    results: list[dict[str, Any]] = []
    # ↑ 存放所有采集结果的列表。

    count = 0
    # ↑ 计数器，用于生成唯一 ID 和控制总数。

    # ── 2. 创建 HTTP 客户端，遍历所有 RSS 源 ──
    with httpx.Client(timeout=20.0) as client:
        # ↑ 创建一个 HTTP 客户端（复用连接池），20 秒超时。
        #   with 语句保证退出时自动关闭连接。

        for source in sources:
            # ↑ 遍历每个启用的 RSS 源。

            if count >= limit:
                # ↑ 当已采集数量达到上限时，退出循环。
                break
                # ↑ break 跳出整个 for 循环（不再处理剩余的源）。

            try:
                resp = client.get(source["url"])
                # ↑ 对每个 RSS 源发起 HTTP GET 请求。
                #   source["url"] 从配置文件中读取，比如 "https://blog.example.com/feed.xml"

                resp.raise_for_status()
                # ↑ 如果 HTTP 状态码不是 2xx，抛出异常。

                feed_text = resp.text
                # ↑ resp.text 获取响应的文本内容（XML 格式的 RSS feed）。
                #   类比 JS 的 await response.text()

                # ── 3. 用正则表达式解析 RSS XML ──
                # RSS 是 XML 格式，这里用正则而不是 XML 解析器，
                # 是为了简单和鲁棒（有些 RSS 源的 XML 格式不太标准）。
                items = re.findall(
                    # ↑ re.findall(pattern, string, flags) → 在字符串中找出所有匹配的内容。
                    #   返回一个列表，每个元素是捕获组 (title, link) 的元组。
                    #   类比 JS 的 str.matchAll() / string.match(//g)
                    #
                    # 下面这个正则的含义：
                    r"<item[^>]*>"          # 匹配 <item ...> 开头（可能带属性）
                    r".*?"                  # 非贪婪匹配中间任意内容（. = 任意字符, *? = 尽可能少）
                    r"<title[^>]*>"         # 匹配 <title ...> 开头
                    r"(?:<!\[CDATA\[)?"     # 可选：CDATA 起始标记（(?:) = 非捕获组，? = 可选）
                    r"(.*?)"                # 捕获组 1：标题文本（贪婪但下一部分会截断）
                    r"(?:\]\]>)?"           # 可选：CDATA 结束标记
                    r"</title>"             # 匹配 </title> 结束
                    r".*?"                  # 非贪婪中间内容
                    r"<link[^>]*>"          # 匹配 <link ...> 开头
                    r"(.*?)"                # 捕获组 2：链接 URL
                    r"</link>"              # 匹配 </link> 结束
                    r".*?"                  # 非贪婪中间内容
                    r"</item>",             # 匹配 </item> 结束
                    feed_text,
                    re.DOTALL,
                    # ↑ re.DOTALL 标志：让 . 也能匹配换行符 \n。
                    #   因为 RSS XML 中的 <item>...</item> 通常跨多行。
                )
                # ↑ items 的结构：[(title1, link1), (title2, link2), ...]
                #   每个元素是一个元组（tuple），类似于 JS 中不可变的数组。

                for title, link in items:
                    # ↑ Python 的"元组解包"：直接把 (title, link) 拆成两个变量。
                    #   相当于 JS 的 const [title, link] = item;

                    if count >= limit:
                        break
                        # ↑ 每次循环都检查是否已满（因为可能一个源就远超过 limit）

                    title = title.strip()
                    # ↑ .strip() 去掉首尾空白，相当于 .trim()

                    link = link.strip()

                    if not title or not link:
                        # ↑ 如果标题或链接为空，跳过这条。
                        continue
                        # ↑ continue 跳到 for 循环的下一次迭代。

                    now = datetime.now(timezone.utc).isoformat()
                    # ↑ 当前 UTC 时间的 ISO 格式字符串。
                    count += 1
                    # ↑ 计数器加 1。

                    results.append({
                        "id": f"rss-{datetime.now().strftime('%Y%m%d')}-{count:03d}",
                        # ↑ 生成唯一 ID。{count:03d} = 3 位零填充数字。
                        "title": title,
                        "source": f"rss:{source['name']}",
                        # ↑ 数据来源标注，格式："rss:源名称"
                        "source_url": link,
                        "author": source.get("name", "unknown"),
                        # ↑ 作者字段用源名称代替（RSS 条目通常没有作者字段）
                        "published_at": now,
                        "raw_description": "",
                        # ↑ 原始描述留空（当前正则没有提取 <description>）
                        "category": source.get("category", "general"),
                        # ↑ 分类标签，从配置文件读取
                        "collected_at": now,
                        # ↑ 采集时间戳
                    })

                logger.info("RSS [%s] 采集: %d 条", source["name"], len(items))
                # ↑ 每个 RSS 源处理完成后记录日志。

            except httpx.HTTPError as e:
                # ↑ 捕获 HTTP 相关异常（连接失败、超时、状态码错误等）。
                #   一个源出问题不影响其他源。
                logger.warning("RSS 源 [%s] 获取失败: %s", source["name"], e)
                # ↑ 记录警告而不是错误，因为这通常不是程序的 bug。

    logger.info("RSS 采集完成: 共 %d 条", len(results))
    return results


# =============================================================================
# 独立调试入口
# =============================================================================

if __name__ == "__main__":
    # ↑ 直接运行本文件时执行下面的调试代码。

    import argparse
    # ↑ 命令行参数解析（只在调试入口才导入，模块主体不需要它）。
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    # ↑ 配置日志：显示时间、级别和消息。

    parser = argparse.ArgumentParser(description="RSS 数据源采集调试入口")
    parser.add_argument("--limit", type=int, default=10, help="最大采集条数")
    parser.add_argument("--output", type=str, default="", help="保存到 JSON 文件（可选）")
    args = parser.parse_args()
    # ↑ 解析命令行参数：python3 -m pipeline.rss_reader --limit 5 --output result.json

    items = collect_rss(limit=args.limit)
    # ↑ 调用采集函数。

    print(f"\n采集到 {len(items)} 条 RSS 条目")
    for i, item in enumerate(items[:5], 1):
        # ↑ enumerate(items[:5], 1) → enumerate 的第二个参数是索引起始值，
        #   这里从 1 开始（而不是默认的 0），让打印的序号看起来更自然。
        print(f"  {i}. [{item['source']}] {item['title'][:60]}")
        # ↑ [:60] 截取前 60 个字符，防止标题太长。

    if len(items) > 5:
        print(f"  ... 还有 {len(items) - 5} 条")

    if args.output:
        # ↑ 如果指定了 --output 参数，把结果保存到文件。
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到: {args.output}")
