"""
model_clientlear.py — model_client.py 的教学注释版

🧑‍🏫 这个文件是给前端开发者看懂 Python 代码用的。
    涵盖知识点：dataclass（数据类）、ABC（抽象基类）、工厂模式、重试机制。

原文功能：统一 LLM 客户端 — 工厂模式封装多模型调用。
         支持 DeepSeek、Qwen、OpenAI，通过环境变量切换。
"""

from __future__ import annotations
# ↑ 开启"前向引用类型注解"，让 Python 支持 str | None 这种简洁语法。

import os
# ↑ 操作系统接口，用来读环境变量（os.getenv）。类比 Node.js 的 process.env。

import time
# ↑ 时间相关功能。这里主要用 time.sleep() 做重试等待。类比 JS 的 setTimeout 的同步版。

import logging
# ↑ 日志库，相当于 console.log 的加强版。

from abc import ABC, abstractmethod
# ↑ Python 的"抽象基类"模块。类比 TypeScript 的 abstract class。
#   ABC          → 抽象基类的"基类"，继承它才能成为抽象类。
#   abstractmethod → 装饰器，标记一个方法是抽象的（子类必须实现）。

from dataclasses import dataclass, field
# ↑ dataclass 是 Python 3.7+ 引入的数据结构简写方式。
#   类比 TypeScript 的 interface + 一行 class。
#   写 @dataclass 装饰器后，Python 自动生成 __init__、__repr__、__eq__ 等方法。
#   field 用来给字段提供默认值或额外配置。
#
#   对比：不用 dataclass 你就要手写一个类，太啰嗦了。

from typing import Any
# ↑ Any = 任意类型，相当于 TypeScript 的 any。

import httpx
# ↑ 第三方 HTTP 客户端，类比 axios。

from dotenv import load_dotenv
# ↑ 自动加载 .env 文件到环境变量。

load_dotenv()
# ↑ 必须在任何 os.getenv() 调用之前执行。

logger = logging.getLogger(__name__)
# ↑ 创建带命名空间的日志记录器。


# =============================================================================
# 第 1 节：数据结构 —— 用 dataclass 快速定义数据模型
# =============================================================================

@dataclass
# ↑ @dataclass 是 Python 的"装饰器（Decorator）"。
#   装饰器本质上是一个函数，它接受一个类/函数作为参数，返回一个增强后的版本。
#   类比 JS 的 decorator（stage 3 proposal）或高阶函数包装。
#
#   效果：下面这个类，你只写了字段定义，Python 自动帮你生成：
#     __init__(self, prompt_tokens=0, completion_tokens=0) → 构造函数
#     __repr__(self)                                      → 调试输出（类似 console.log）
#     __eq__(self, other)                                 → 值比较（类似 deepStrictEqual）
#
#   等效于你手写：
#     class Usage:
#         def __init__(self, prompt_tokens=0, completion_tokens=0):
#             self.prompt_tokens = prompt_tokens
#             self.completion_tokens = completion_tokens

class Usage:
    """Token 用量统计
    # ↑ 这是一个文档字符串，说明类的用途。
    #   类比 JSDoc 的 @classdesc。
    """

    prompt_tokens: int = 0
    # ↑ 字段名: 类型 = 默认值
    #   Python 里 int = 0 可以直接写在类体里作为类属性+默认值。
    #   相当于 TypeScript 里的：
    #     class Usage {
    #       promptTokens: number = 0;
    #       completionTokens: number = 0;
    #     }

    completion_tokens: int = 0

    @property
    # ↑ @property 是 Python 的"属性装饰器"。
    #   它把一个方法伪装成一个属性，调用时不需要写括号。
    #   比如 usage.total_tokens（不是 usage.total_tokens()）。
    #
    #   类比 JS 的 getter：
    #     class Usage {
    #       get totalTokens() { return this.promptTokens + this.completionTokens; }
    #     }
    #   或者 Vue 里的 computed 属性。

    def total_tokens(self) -> int:
        # ↑ self 相当于 JS 里的 this，指向实例本身。
        #   Python 强制要求方法的第一个参数是 self（名字约定，必须写）。
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        # ↑ 把数据对象转成普通字典，用于序列化（json.dump）。
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMResponse:
    """统一的 LLM 响应格式
    # ↑ 把 LLM API 的原始返回包装成统一结构，
    #   这样不管用 DeepSeek、Qwen 还是 OpenAI，上层代码都不需要改。
    """

    content: str
    # ↑ LLM 返回的文本内容

    usage: Usage = field(default_factory=Usage)
    # ↑ field(default_factory=Usage) 的意思是：每次创建 LLMResponse 实例时，
    #   如果没有传 usage 参数，就调用 Usage() 创建一个新的 Usage 实例作为默认值。
    #
    #   为什么不用 usage: Usage = Usage() ？因为那会让"所有实例共享同一个 Usage 对象"，
    #   这是 Python 可变默认参数的经典坑（类比 JS 里把对象写在函数默认参数里的问题）。
    #
    #   default_factory 保证了每个实例都有独立的 Usage 副本。

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "usage": self.usage.to_dict(),
        }


# =============================================================================
# 第 2 节：费用估算 —— 根据 token 消耗算钱
# =============================================================================

PRICING: dict[str, dict[str, float]] = {
    # ↑ 嵌套字典：外层 key 是模型名，内层 key 是 "input"/"output"。
    #   价格单位：每 1000 个 token 的美元售价。
    #   比如 deepseek-chat：输入 $0.0014/K，输出 $0.0028/K。
    "deepseek-chat": {"input": 0.0014, "output": 0.0028},
    "deepseek-reasoner": {"input": 0.004, "output": 0.016},
    "qwen-plus": {"input": 0.002, "output": 0.006},
    "qwen-turbo": {"input": 0.0005, "output": 0.001},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}


def estimate_cost(model: str, usage: Usage) -> float:
    """估算单次调用成本（USD）

    公式：成本 = (输入token数 / 1000) * 输入单价 + (输出token数 / 1000) * 输出单价
    因为 PRICING 里存的单位是 美元/千token。
    """
    prices = PRICING.get(model, {"input": 0.002, "output": 0.006})
    # ↑ dict.get(key, default) 安全取值。如果模型名不在价格表里，用默认价格。
    return (
        usage.prompt_tokens / 1000 * prices["input"]
        + usage.completion_tokens / 1000 * prices["output"]
    )
    # ↑ 括号可以让长表达式换行，不影响运算。


# =============================================================================
# 第 3 节：Provider 抽象基类 —— 面向接口编程
# =============================================================================

class LLMProvider(ABC):
    # ↑ class LLMProvider(ABC) → 声明 LLMProvider 是抽象类。
    #   ABC 是 Abstract Base Class 的缩写。
    #   类比 TypeScript:
    #     abstract class LLMProvider {
    #       abstract chat(...): LLMResponse;
    #     }
    """LLM 提供商抽象基类
    # ↑ 抽象类不能直接实例化，只能被继承。
    #   它定义了所有 LLM 提供商必须遵守的接口（契约）。
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        # ↑ __init__ 是 Python 的"构造方法"。类似 JS class 的 constructor()。
        #   当你写 provider = DeepSeekProvider(key, url, model) 时，
        #   __init__ 会自动执行，把参数绑定到 self 上。
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        # ↑ .rstrip("/") → 去掉 URL 末尾可能多余的斜杠。
        #   因为拼接时会写 f"{base_url}/chat/completions"，保证不出现双斜杠。
        self.model = model
        self.client = httpx.Client(timeout=60.0)
        # ↑ 创建一个 HTTP 客户端实例，超时时间 60 秒。

    @abstractmethod
    # ↑ @abstractmethod 装饰器标记这个方法为"抽象方法"——
    #   子类必须实现它，否则子类也不能实例化。
    #   类比 TypeScript 的 abstract chat(...): LLMResponse;
    def chat(
        self,
        messages: list[dict[str, str]],
        # ↑ messages 是 OpenAI 标准格式的消息列表：
        #   [{"role": "system", "content": "你是一个助手"},
        #    {"role": "user", "content": "你好"}]
        temperature: float = 0.7,
        # ↑ temperature 控制输出随机性（0=确定, 1=平衡, 2=随机）
        max_tokens: int = 2000,
        # ↑ 最多生成多少个 token
    ) -> LLMResponse:
        """发送聊天请求，返回统一格式响应"""
        ...
        # ↑ ... 是 Python 3.10+ 的占位符（Ellipsis 字面量），语义上等于 pass。
        #   在抽象方法里写 ... 表示"这个方法没有实现，由子类负责"。

    def close(self) -> None:
        # ↑ 普通方法（不是抽象的），子类可以直接继承不用重写。
        self.client.close()
        # ↑ 关闭 HTTP 连接，释放资源。

    def __enter__(self):
        # ↑ __enter__ 是 Python 的"上下文管理器协议"。
        #   实现了 __enter__ 和 __exit__ 的对象可以用 with 语句：
        #     with LLMProvider(...) as provider:
        #         provider.chat(...)
        #   进入 with 块时自动调用 __enter__
        return self

    def __exit__(self, *args):
        # ↑ 离开 with 块时自动调用 __exit__，无论是否发生异常。
        #   *args 接收所有参数（异常类型、异常实例、traceback），这里不关心是什么异常。
        self.close()
        # ↑ 退出时自动关闭连接。


class OpenAICompatibleProvider(LLMProvider):
    # ↑ class 子类(父类) 是 Python 的继承语法。
    #   类比 JS 的 class OpenAIProvider extends LLMProvider {}
    """
    兼容 OpenAI Chat Completions API 的提供商。
    DeepSeek、Qwen、OpenAI 都使用相同的 API 格式。
    """

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        # ↑ 具体实现父类的抽象方法 chat()。
        #   没有 @abstractmethod 装饰器，但父类有，所以这里必须实现。

        url = f"{self.base_url}/chat/completions"
        # ↑ 拼接 API 端点 URL。base_url 在构造时传入（比如 "https://api.deepseek.com"）。
        #   最终 url = "https://api.deepseek.com/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            # ↑ HTTP Bearer 认证头。绝大多数 LLM API 都用这种方式认证。
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # ↑ 请求体（body），会被序列化为 JSON 发送。

        resp = self.client.post(url, json=payload, headers=headers)
        # ↑ 发送 HTTP POST 请求。
        #   json=payload  → httpx 会自动把 dict 序列化成 JSON 并设 Content-Type
        #   类比 axios.post(url, payload, { headers })

        resp.raise_for_status()
        # ↑ 如果返回码不是 2xx，抛出 HTTPStatusError 异常。

        data = resp.json()
        # ↑ 把 JSON 响应体解析成 Python 字典。

        content = data["choices"][0]["message"]["content"]
        # ↑ 从 OpenAI 格式响应中提取文本。
        #   响应结构：{ "choices": [ { "message": { "content": "..." } } ] }
        #   相当于 JS 的 data.choices[0].message.content

        usage_data = data.get("usage", {})
        # ↑ 提取 token 用量信息。如果 API 没返回 usage，用空字典兜底。

        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
        )
        # ↑ 把 token 数据封装到 Usage 对象里。

        return LLMResponse(content=content, usage=usage)
        # ↑ 返回统一格式的响应对象。


# =============================================================================
# 第 4 节：工厂函数 —— 根据配置创建对应的 LLM 客户端
# =============================================================================

PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    # ↑ 各提供商的配置映射表。
    #   对于每个提供商，定义：
    #     api_key_env      → 环境变量名（从哪里读 API Key）
    #     base_url_env     → 环境变量名（从哪里读 Base URL）
    #     model_env        → 环境变量名（从哪里读模型名）
    #     default_base_url → 如果没设环境变量，用这个兜底 URL
    #     default_model    → 如果没设环境变量，用这个兜底模型

    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "model_env": "DEEPSEEK_MODEL",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "qwen": {
        "api_key_env": "QWEN_API_KEY",
        "base_url_env": "QWEN_BASE_URL",
        "model_env": "QWEN_MODEL",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "model_env": "OPENAI_MODEL",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
}


def create_provider(provider_name: str | None = None) -> LLMProvider:
    # ↑ str | None 表示参数可以是字符串或者 None（Python 3.10+ 语法）。
    #   相当于 TypeScript 的 providerName?: string | null

    """工厂函数：根据提供商名称创建对应的 LLM 客户端。

    "工厂函数"（Factory Function）是一种设计模式：
      你告诉它你想要什么类型的对象，它帮你创建并返回。
      你不需要知道内部怎么构建的。
      类比 React 的 createElement() 或者 Vue 的 h()。
    """

    name = (provider_name or os.getenv("LLM_PROVIDER", "deepseek")).lower()
    # ↑ Python 的 or 运算符：如果左边是 Falsy（None/""/0），返回右边的值。
    #   1. 如果调用时传了 provider_name，用它
    #   2. 否则读环境变量 LLM_PROVIDER
    #   3. 如果环境变量也没设，默认用 "deepseek"
    #   4. .lower() 把字符串转成小写（统一处理 "DeepSeek"/"DEEPSEEK" 等）

    if name not in PROVIDER_CONFIG:
        # ↑ 检查配置表里有没有这个提供商。
        raise ValueError(
            f"未知的模型提供商: {name}，支持: {', '.join(PROVIDER_CONFIG.keys())}"
        )
        # ↑ raise 是 Python 抛出异常的关键字，相当于 JS 的 throw new Error(...)
        #   ValueError 是 Python 内置异常类型，表示"值不合法"。
        #   ', '.join(...) 把列表用逗号拼接成字符串，比如 "deepseek, qwen, openai"

    config = PROVIDER_CONFIG[name]
    # ↑ 拿到对应的配置字典。

    api_key = os.getenv(config["api_key_env"], "")
    # ↑ 从环境变量读取 API Key。比如 os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        # ↑ if not api_key 在 api_key 为空字符串 "" 时也是 True。
        raise RuntimeError(
            f"缺少 API Key，请设置环境变量: {config['api_key_env']}"
        )
        # ↑ RuntimeError 表示"运行时错误"，一般是程序无法继续执行的错误。

    base_url = os.getenv(config["base_url_env"], config["default_base_url"])
    # ↑ 读取环境变量中的 base_url，没有就用默认值。
    model = os.getenv(config["model_env"], config["default_model"])
    # ↑ 同理读取模型名。

    logger.info("创建 LLM 客户端: provider=%s, model=%s", name, model)
    return OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model)
    # ↑ 创建并返回一个 LLM 客户端实例。
    #   注意：所有提供商都用同一个 OpenAICompatibleProvider 类，
    #   因为它们 API 格式都是 OpenAI 兼容的，只是 base_url 和 api_key 不同。


# =============================================================================
# 第 5 节：带重试的调用封装 —— 网络不稳时自动重试
# =============================================================================

def chat_with_retry(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
    max_retries: int = 3,
    # ↑ 最多重试 3 次（加上第一次，总共 4 次尝试）
    backoff_base: float = 2.0,
    # ↑ 退避基数（秒）。等待时间 = backoff_base ^ 第几次重试。
    #   第 1 次重试等待 2^0=1 秒，第 2 次等待 2^1=2 秒，第 3 次等待 2^2=4 秒...
    #   这就是"指数退避（Exponential Backoff）"策略。
) -> LLMResponse:
    """带指数退避重试的聊天调用。

    指数退避策略：每次失败后等待越来越长的时间再重试，
    避免在服务端压力大时雪上加霜。
    """

    last_error: Exception | None = None
    # ↑ 保存最后一次异常，用于在重试耗尽后抛出。

    for attempt in range(max_retries):
        # ↑ range(max_retries) → 生成 [0, 1, 2]（共 max_retries 个数字）
        #   for attempt in range(3): → attempt 依次是 0, 1, 2
        #   类比 JS 的 for (let attempt = 0; attempt < maxRetries; attempt++)
        try:
            response = provider.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if attempt > 0:
                # ↑ 如果 attempt > 0，说明至少重试了一次才成功。
                logger.info("第 %d 次重试成功", attempt)

            return response
            # ↑ 成功就立即返回，不走后面的 except 块。

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            # ↑ 同时捕获三种 httpx 异常：
            #   HTTPStatusError   → 服务器返回了错误状态码（4xx/5xx）
            #   ConnectError      → 无法连接到服务器
            #   TimeoutException  → 请求超时
            #
            #   注意：只重试网络/服务端错误，不重试业务逻辑错误。
            last_error = e

            if attempt < max_retries - 1:
                # ↑ 还没到最后一次尝试，等待后重试。
                wait_time = backoff_base ** attempt
                # ↑ Python 的幂运算操作符是 **（不是 ^，^ 是位异或）。
                #   backoff_base ** attempt = backoff_base 的 attempt 次方。
                #   相当于 JS 的 Math.pow(backoffBase, attempt)。

                logger.warning(
                    "LLM 调用失败（第 %d/%d 次），%0.1f 秒后重试: %s",
                    attempt + 1, max_retries, wait_time, str(e),
                    # ↑ %d=整数, %0.1f=1位小数, %s=字符串。旧式格式化有时比 f-string 更清晰。
                )
                time.sleep(wait_time)
                # ↑ time.sleep(秒数) 让当前线程暂停指定秒数。
                #   这是同步阻塞操作，相当于 JS 的 Atomics.wait() 或 C 的 sleep()。

            else:
                logger.error("LLM 调用失败，已达最大重试次数: %s", str(e))
                # ↑ 最后一次尝试也失败了，记录错误。

    raise last_error  # type: ignore[misc]
    # ↑ 所有重试都失败了，抛出最后一个异常。
    #   # type: ignore[misc] 是 mypy（Python 静态类型检查工具）的注释，
    #   告诉类型检查器忽略此处的"可能为 None"警告。
    #   类似于 TypeScript 的 // @ts-ignore。


# =============================================================================
# 第 6 节：便捷函数 —— 一行代码调用 LLM
# =============================================================================

def chat(
    prompt: str,
    system: str = "你是一个 AI 技术分析助手。",
    provider: str | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """便捷调用 LLM，返回包含 content 和 usage 的字典。

    这是对 chat_with_retry + create_provider 的简单封装。
    你只需要传提示词，其他都用默认值。
    """

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    provider_name = provider or os.getenv("LLM_PROVIDER", "deepseek")
    llm = create_provider(provider_name)
    # ↑ 创建 LLM 客户端实例。

    try:
        response = chat_with_retry(llm, messages, max_retries=max_retries)
        result = response.to_dict()

        cost = estimate_cost(llm.model, response.usage)
        logger.info(
            "Token 用量: %d (prompt) + %d (completion) = %d, 估算成本: $%.6f",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.usage.total_tokens,
            cost,
        )

        return result
        # ↑ 返回字典格式的结果。

    finally:
        # ↑ finally 块无论如何都执行（即使 try 里 return 了也会先执行 finally）。
        llm.close()
        # ↑ 确保无论成功失败都关闭 HTTP 连接。


# ── 向后兼容别名 ──
quick_chat = lambda prompt, **kw: chat(prompt, **kw)["content"]
# ↑ lambda 是 Python 的"匿名函数"（一行函数）。类比 JS 的箭头函数。
#   lambda 参数: 返回值
#   相当于：
#     def quick_chat(prompt, **kw):
#         return chat(prompt, **kw)["content"]
#
#   **kw 是 Python 的"关键字参数收集"。
#   **kw 会把多余的命名参数收集成一个字典。
#   比如 quick_chat("hello", max_retries=5, temperature=0.5) 中 **kw = {"max_retries": 5, "temperature": 0.5}
#
#   ["content"] 是在 chat 返回的字典上直接取 content 字段。
#   所以 quick_chat 只返回文本，不返回 usage。


# =============================================================================
# CLI 测试入口 —— 如果直接运行这个文件就执行以下代码
# =============================================================================

if __name__ == "__main__":
    # ↑ 前面解释过：只有直接运行本文件时才进入下面的代码块。
    #   如果被 import，则不执行。

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    # ↑ 配置日志格式为只显示级别和消息。

    print("=== LLM 客户端测试 ===")
    print(f"提供商: {os.getenv('LLM_PROVIDER', 'deepseek')}")

    try:
        result = chat("用一句话介绍什么是 AI Agent。")
        # ↑ 调用便捷函数，传入一个测试提示词。
        print(f"\n回复: {result['content']}")
        print(f"用量: {result['usage']}")
    except Exception as e:
        # ↑ Exception 是所有异常的基类，捕获任何异常。
        print(f"\n错误: {e}")
        print("请检查 .env 文件中的 API Key 配置。")
