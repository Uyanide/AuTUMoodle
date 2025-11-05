'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-29 10:07:02
LastEditTime: 2025-11-05 13:58:45
Description: Authentication helper for "requests" session implementation
'''

import httpx

from .log import Logger
from . import request_helper


AUTH_URL = "https://www.moodle.tum.de/Shibboleth.sso/Login?providerId=https://tumidp.lrz.de/idp/shibboleth&target=https://www.moodle.tum.de/auth/shibboleth/index.php"
IDP_BASE_URL = "https://login.tum.de"
SUCCESS_URL = "https://www.moodle.tum.de/my"


def format_idp_url(relative_url: str) -> str:
    if relative_url.startswith("http"):
        return relative_url
    return f"{IDP_BASE_URL}{relative_url}"


async def auth(client: httpx.AsyncClient, username: str, password: str) -> None:
    Logger.d("Authentication", "Fetching SAML request URL...")
    response = await client.get(AUTH_URL,
                                headers=request_helper.GENERAL_HEADERS,
                                follow_redirects=False)
    Logger.d("Authentication", f"Received response: {response.status_code}")

    if response.status_code != 302:
        raise RuntimeError(f"Unexpected status code: {response.status_code}")

    saml_request_url = response.headers.get('Location')
    if not saml_request_url:
        raise RuntimeError("No Location header found in the response")
    Logger.d("Authentication", f"SAML Request URL: {saml_request_url}")

    Logger.d("Authentication", "Fetching SAML request page...")
    response = await client.get(saml_request_url,
                                headers=request_helper.GENERAL_HEADERS,
                                follow_redirects=False)
    Logger.d("Authentication", f"Received response: {response.status_code}")

    if response.status_code != 302:
        raise RuntimeError(f"Unexpected status code: {response.status_code}")

    sso_relative_url = response.headers.get('Location')
    if not sso_relative_url:
        raise RuntimeError("No Location header found in the response")
    sso_url = format_idp_url(sso_relative_url)
    Logger.d("Authentication", f"SSO URL: {sso_url}")

    Logger.d("Authentication", "Fetching SSO page...")
    response = await client.get(sso_url, headers={
        **request_helper.GENERAL_HEADERS,
        **request_helper.ADDITIONAL_HEADERS,
        "Referer": sso_url,
    }, follow_redirects=True)
    Logger.d("Authentication", f"Received response: {response.status_code}")

    parser = request_helper.FormParser(response.text)
    action_url = format_idp_url(parser.action_url)
    parser.ensure_have_inputs({
        'csrf_token',
        'shib_idp_ls_supported',
    })
    parser.update_inputs({
        'shib_idp_ls_supported': 'false'
    })

    Logger.d("Authentication", "Submitting intermediate form...")
    response = await client.post(action_url, data=parser.encode_inputs(), headers={  # type: ignore
        **request_helper.GENERAL_HEADERS,
        **request_helper.ADDITIONAL_HEADERS,
        "Referer": sso_url,
    }, follow_redirects=True)
    Logger.d("Authentication", f"Received response: {response.status_code}")
    # print(response.text)
    # return

    parser = request_helper.FormParser(response.text)
    action_url = format_idp_url(parser.action_url)
    parser.ensure_have_inputs({
        'csrf_token',
        'j_username',
        'j_password',
    })
    parser.update_inputs({
        'j_username': username,
        'j_password': password,
        'donotcache': '',
        'donotcache-dummy': '1',
        '_eventId_proceed': '',
    })

    Logger.d("Authentication", "Submitting credentials form...")
    response = await client.post(action_url, data=parser.encode_inputs(), headers={  # type: ignore
        **request_helper.GENERAL_HEADERS,
        **request_helper.ADDITIONAL_HEADERS,
        "Referer": action_url,
    }, follow_redirects=True)
    Logger.d("Authentication", f"Received response: {response.status_code}")

    parser = request_helper.FormParser(response.text)
    action_url = format_idp_url(parser.action_url)

    if parser.do_have_input('j_username'):
        raise RuntimeError("Authentication failed: possibly wrong username or password")

    if parser.do_have_input('_shib_idp_consentOptions'):
        Logger.d("Authentication", "Giving consent...")
        parser.ensure_have_inputs({
            'csrf_token',
        })
        parser.remove_inputs({
            '_eventId_AttributeReleaseRejected',
            '_shib_idp_consentOptions',
        })
        parser.update_inputs({
            '_shib_idp_consentOptions': '_shib_idp_rememberConsent',
            '_eventId_proceed': 'Accept',
        })
        response = await client.post(action_url, data=parser.encode_inputs(), headers={  # type: ignore
            **request_helper.GENERAL_HEADERS,
            **request_helper.ADDITIONAL_HEADERS,
            "Referer": action_url,
        }, follow_redirects=True)
        Logger.d("Authentication", f"Received response: {response.status_code}")
        parser = request_helper.FormParser(response.text)
        action_url = format_idp_url(parser.action_url)

    parser.ensure_have_inputs({
        'SAMLResponse',
        'RelayState',
    })

    Logger.d("Authentication", "Submitting SAML response form...")
    response = await client.post(action_url, data=parser.encode_inputs(), headers={  # type: ignore
        **request_helper.GENERAL_HEADERS,
        **request_helper.ADDITIONAL_HEADERS,
        "Referer": action_url,
    }, follow_redirects=True)
    Logger.d("Authentication", f"Received response: {response.status_code}")

    if response.status_code != 200:
        raise RuntimeError(f"Unexpected status code: {response.status_code}")
    if not str(response.url).startswith(SUCCESS_URL):
        Logger.w("Authentication", f"Unexpected final URL: {response.url}, login may have failed")
    else:
        Logger.i("Authentication", "Authentication was successful!")


if __name__ == "__main__":
    import asyncio

    async def main():
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
            await auth(client, "abcdedg", "NeverGonnaGiveYouUp")
    asyncio.run(main())
