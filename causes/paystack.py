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


# The Foundation website (jancosmicfoundation.org) names every donation
# reference JCF-<timestamp>-<id>. The same Paystack account also takes
# payments on drbaffourjan.com — Inner Space memberships (IS-…) and personal
# offerings to Dr. Jan (DON-…) — and Paystack sends all of them to our
# webhook. Those are not Foundation donations, so only JCF- references are
# recorded; anything unrecognised is left out rather than guessed at.
FOUNDATION_REFERENCE_PREFIX = 'JCF-'


def is_foundation_donation(reference: str) -> bool:
    return reference.startswith(FOUNDATION_REFERENCE_PREFIX)
