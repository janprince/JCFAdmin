"""
Paystack API integration helpers.
"""
import hashlib
import hmac
import logging
from urllib.request import Request, urlopen
from urllib.error import URLError
import json

from django.conf import settings

logger = logging.getLogger(__name__)

PAYSTACK_API_BASE = 'https://api.paystack.co'


def _get_secret_key():
    key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    if not key:
        raise ValueError('PAYSTACK_SECRET_KEY is not configured')
    return key


def initialize_transaction(email, amount_pesewas, reference=None,
                           metadata=None, callback_url=None) -> dict | None:
    """
    Initialize a Paystack transaction (server-side; secret stays here).
    Returns {authorization_url, access_code, reference} on success, else None.
    https://paystack.com/docs/api/transaction/#initialize
    """
    payload = {
        'email': email,
        'amount': int(amount_pesewas),
        'currency': 'GHS',
    }
    if reference:
        payload['reference'] = reference
    if metadata:
        payload['metadata'] = metadata
    if callback_url:
        payload['callback_url'] = callback_url

    req = Request(
        f'{PAYSTACK_API_BASE}/transaction/initialize',
        data=json.dumps(payload).encode(),
        method='POST',
    )
    req.add_header('Authorization', f'Bearer {_get_secret_key()}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except (URLError, json.JSONDecodeError):
        logger.exception('Paystack initialize failed')
        return None

    if body.get('status') is True:
        return body['data']
    logger.warning('Paystack initialize: %s', body.get('message'))
    return None


def verify_transaction(reference: str) -> dict | None:
    """
    Verify a transaction with Paystack.
    Returns the full `data` dict on success, or None on failure.
    https://paystack.com/docs/api/transaction/#verify
    """
    url = f'{PAYSTACK_API_BASE}/transaction/verify/{reference}'
    req = Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {_get_secret_key()}')

    try:
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except (URLError, json.JSONDecodeError):
        logger.exception('Paystack verify request failed for ref=%s', reference)
        return None

    if body.get('status') is True and body.get('data', {}).get('status') == 'success':
        return body['data']

    logger.warning(
        'Paystack verify: transaction %s not successful — status=%s',
        reference,
        body.get('data', {}).get('status'),
    )
    return None


def validate_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Validate the X-Paystack-Signature header using HMAC SHA-512
    """
    expected = hmac.new(
        _get_secret_key().encode(),
        payload,
        digestmod=hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
