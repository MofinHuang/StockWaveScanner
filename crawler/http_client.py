from urllib.parse import urlparse
import warnings

import requests
from urllib3.exceptions import InsecureRequestWarning


KNOWN_SSL_ERRORS = (
    "certificate_verify_failed",
    "missing subject key identifier",
    "certificate verify failed",
)


def _get_hostname(
    url: str,
) -> str:

    return (
        urlparse(url)
        .hostname
        or ""
    ).lower()


def _is_known_ssl_error(
    ex: Exception,
) -> bool:

    message = str(ex).lower()

    return any(
        keyword in message
        for keyword in KNOWN_SSL_ERRORS
    )


def _validate_tpex_url(
    url: str,
):
    hostname = _get_hostname(
        url
    )

    if not (
        hostname == "tpex.org.tw"
        or hostname.endswith(
            ".tpex.org.tw"
        )
    ):
        raise ValueError(
            "只能用於 TPEx 官方網域"
        )


def _validate_tdcc_url(
    url: str,
):
    hostname = _get_hostname(
        url
    )

    if not (
        hostname == "tdcc.com.tw"
        or hostname.endswith(
            ".tdcc.com.tw"
        )
    ):
        raise ValueError(
            "只能用於 TDCC 官方網域"
        )


def _request_with_fallback(
    request_func,
    service_name: str,
    **kwargs,
):
    try:

        return request_func(
            verify=True,
            **kwargs,
        )

    except requests.exceptions.SSLError as ex:

        if not _is_known_ssl_error(ex):
            raise

        print(
            f"[WARN] {service_name} "
            "SSL 憑證驗證失敗，"
            "使用限定網域 verify=False fallback"
        )

        with warnings.catch_warnings():

            warnings.simplefilter(
                "ignore",
                InsecureRequestWarning,
            )

            return request_func(
                verify=False,
                **kwargs,
            )


def tpex_get(
    url: str,
    **kwargs,
):
    _validate_tpex_url(
        url
    )

    return _request_with_fallback(
        request_func=requests.get,
        service_name="TPEx",
        url=url,
        **kwargs,
    )


def tpex_post(
    url: str,
    **kwargs,
):
    """
    TPEx 官方網域專用 POST。
    """

    _validate_tpex_url(
        url
    )

    return _request_with_fallback(
        request_func=requests.post,
        service_name="TPEx",
        url=url,
        **kwargs,
    )


def tdcc_get(
    url: str,
    **kwargs,
):
    _validate_tdcc_url(
        url
    )

    return _request_with_fallback(
        request_func=requests.get,
        service_name="TDCC",
        url=url,
        **kwargs,
    )


def tdcc_session_get(
    session: requests.Session,
    url: str,
    **kwargs,
):
    _validate_tdcc_url(
        url
    )

    return _request_with_fallback(
        request_func=session.get,
        service_name="TDCC",
        url=url,
        **kwargs,
    )


def tdcc_session_post(
    session: requests.Session,
    url: str,
    **kwargs,
):
    _validate_tdcc_url(
        url
    )

    return _request_with_fallback(
        request_func=session.post,
        service_name="TDCC",
        url=url,
        **kwargs,
    )