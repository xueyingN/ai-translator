import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from logger import logger


def _application_dir():
    """返回源码目录或打包后的可执行文件目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ENV_PATH = _application_dir() / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

MAX_TEXT_LENGTH = 10_000
REQUEST_TIMEOUT = 30.0


class TranslationError(Exception):
    """翻译错误基类。"""


class TranslationConfigError(TranslationError):
    """配置错误。"""


class TranslationAuthError(TranslationError):
    """认证错误。"""


class TranslationNetworkError(TranslationError):
    """网络或请求超时错误。"""


class TranslationRateLimitError(TranslationError):
    """API 限流错误。"""


class TranslationServerError(TranslationError):
    """翻译服务端错误。"""


class TranslationResponseError(TranslationError):
    """API 响应格式错误。"""


class TranslationInputError(TranslationError):
    """翻译输入错误。"""


def _validate_input(text, source_language, target_language):
    """校验翻译输入。"""
    if not isinstance(text, str) or not text.strip():
        raise TranslationInputError("翻译内容不能为空")

    if len(text) > MAX_TEXT_LENGTH:
        raise TranslationInputError(
            f"翻译内容不能超过 {MAX_TEXT_LENGTH} 个字符"
        )

    if not isinstance(source_language, str) or not source_language.strip():
        raise TranslationInputError("源语言不能为空")

    if not isinstance(target_language, str) or not target_language.strip():
        raise TranslationInputError("目标语言不能为空")


def _get_api_key():
    """读取并校验 API Key。"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

    if not api_key:
        raise TranslationConfigError(
            "未配置 DEEPSEEK_API_KEY，请将 .env.example 复制为 .env，"
            f"填写 API Key 后放在程序目录中：{ENV_PATH.parent}"
        )

    return api_key


def translate(text, source_language, target_language):
    """调用 DeepSeek API 完成翻译。"""
    logger.info("开始翻译")

    _validate_input(text, source_language, target_language)
    api_key = _get_api_key()

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=REQUEST_TIMEOUT,
        )

        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的翻译，只输出翻译结果，不要解释。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请将下面内容从{source_language.strip()}翻译成"
                        f"{target_language.strip()}:\n{text}"
                    ),
                },
            ],
            stream=False,
        )

    except AuthenticationError as exc:
        logger.error("API 认证失败")
        raise TranslationAuthError(
            "API 认证失败，请检查 DEEPSEEK_API_KEY"
        ) from exc

    except (APITimeoutError, APIConnectionError) as exc:
        logger.error("API 网络请求失败或超时")
        raise TranslationNetworkError(
            "无法连接翻译服务或请求超时"
        ) from exc

    except RateLimitError as exc:
        logger.error("API 请求被限流")
        raise TranslationRateLimitError(
            "请求过于频繁，请稍后重试"
        ) from exc

    except APIStatusError as exc:
        status_code = getattr(exc, "status_code", None)

        if status_code is not None and 500 <= status_code < 600:
            logger.error(
                "翻译服务端错误，状态码：%s",
                status_code,
            )
            raise TranslationServerError(
                "翻译服务暂时不可用，请稍后重试"
            ) from exc

        logger.error(
            "翻译 API 请求失败，状态码：%s",
            status_code,
        )
        raise TranslationError(
            "翻译 API 请求失败"
        ) from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        logger.error("API 返回结构异常")
        raise TranslationResponseError(
            "翻译服务返回了无法识别的结果"
        ) from exc

    if not isinstance(content, str) or not content.strip():
        logger.error("API 返回空翻译结果")
        raise TranslationResponseError(
            "翻译服务返回了空结果"
        )

    logger.info("翻译成功")
    return content.strip()


if __name__ == "__main__":
    pass
