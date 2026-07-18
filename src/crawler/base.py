# -*- coding: utf-8 -*-
"""
爬虫基类
提供：限速器、重试机制、UA 管理、统计信息
"""
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 常用 User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


class RateLimiter:
    """请求频率限制器

    - 支持每秒请求数限制
    - 支持请求间隔（秒）
    - 线程安全（基于 time.monotonic）
    """

    def __init__(self, requests_per_sec: float = 3.0, min_interval: float = 0.3):
        """
        Args:
            requests_per_sec: 每秒最大请求数（NCBI 建议无 API Key 时 ≤ 3）
            min_interval: 两次请求间最小间隔（秒）
        """
        self.interval = max(1.0 / requests_per_sec, min_interval)
        self._last_request: float = 0.0

    def wait(self) -> None:
        """必要时等待以遵守频率限制"""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last_request = time.monotonic()

    def reset(self) -> None:
        self._last_request = 0.0


@dataclass
class CrawlStats:
    """爬取统计信息"""

    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    skipped: int = 0
    start_time: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        if self.start_time == 0:
            return 0.0
        return time.monotonic() - self.start_time

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful / self.total_requests

    def reset(self) -> None:
        self.total_requests = 0
        self.successful = 0
        self.failed = 0
        self.retried = 0
        self.skipped = 0
        self.start_time = time.monotonic()
        self.errors.clear()

    def report(self) -> str:
        lines = [
            "=" * 50,
            "爬取统计报告",
            "=" * 50,
            f"总请求数:     {self.total_requests}",
            f"成功:         {self.successful}",
            f"失败:         {self.failed}",
            f"重试次数:     {self.retried}",
            f"跳过:         {self.skipped}",
            f"成功率:       {self.success_rate:.1%}",
            f"总耗时:       {self.elapsed:.1f}s",
            "=" * 50,
        ]
        if self.errors:
            lines.append(f"错误数: {len(self.errors)}")
            for err in self.errors[-5:]:  # 只显示最近5个
                lines.append(f"  - {err}")
        return "\n".join(lines)


class BaseCrawler:
    """爬虫基类

    提供：User-Agent 轮换、请求重试（指数退避）、频率限制、统计。
    子类只需实现 _fetch、_parse 等具体逻辑。
    """

    def __init__(
        self,
        requests_per_sec: float = 3.0,
        max_retries: int = 3,
        user_agent: Optional[str] = None,
    ):
        """
        Args:
            requests_per_sec: 每秒最大请求数
            max_retries: 最大重试次数
            user_agent: 自定义 UA，为 None 则每次随机选取
        """
        self.limiter = RateLimiter(requests_per_sec)
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.stats = CrawlStats()
        self._session = None

    def get_ua(self) -> str:
        """获取 User-Agent"""
        if self.user_agent:
            return self.user_agent
        return random.choice(USER_AGENTS)

    def request_with_retry(
        self,
        url: str,
        method: str = "GET",
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: int = 30,
        **kwargs,
    ) -> Optional["requests.Response"]:
        """带重试的 HTTP 请求

        Returns:
            Response 对象，失败返回 None
        """
        import requests

        self.stats.start_time = self.stats.start_time or time.monotonic()

        default_headers = {"User-Agent": self.get_ua()}
        if headers:
            default_headers.update(headers)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                self.limiter.wait()
                self.stats.total_requests += 1

                if method.upper() == "GET":
                    resp = requests.get(
                        url, params=params, headers=default_headers,
                        timeout=timeout, **kwargs,
                    )
                else:
                    resp = requests.post(
                        url, params=params, headers=default_headers,
                        timeout=timeout, **kwargs,
                    )

                resp.raise_for_status()
                self.stats.successful += 1
                return resp

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                last_error = f"HTTP {status}: {url} (attempt {attempt+1})"

                # 429 (Too Many Requests) 或 5xx → 可重试
                if status in (429, 502, 503, 504) and attempt < self.max_retries:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning("%s → 等待 %.1fs 后重试...", last_error, wait)
                    time.sleep(wait)
                    self.stats.retried += 1
                    continue
                else:
                    self.stats.failed += 1
                    self.stats.errors.append(last_error)
                    logger.error(last_error)
                    return None

            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError) as e:
                last_error = f"{type(e).__name__}: {url} (attempt {attempt+1})"
                if attempt < self.max_retries:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning("%s → 等待 %.1fs 后重试...", last_error, wait)
                    time.sleep(wait)
                    self.stats.retried += 1
                    continue
                else:
                    self.stats.failed += 1
                    self.stats.errors.append(last_error)
                    logger.error(last_error)
                    return None

            except Exception as e:
                self.stats.failed += 1
                self.stats.errors.append(f"{type(e).__name__}: {url}")
                logger.exception("请求异常: %s", url)
                return None

        return None

    def reset_stats(self) -> None:
        self.stats.reset()
