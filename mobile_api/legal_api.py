"""Legal documents for the app (owner spec, welcome screen).

Terms of Use and Privacy Policy are the foundation's words, authored in
the dashboard. This endpoint serves whichever version is currently in
force; it never generates, summarises or substitutes text. When nothing
is published the app is told so plainly and shows a retry, because
showing invented legal copy would be worse than showing none.
"""
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from engagement.models import LegalDocument

from .authentication import OptionalMobileTokenAuthentication

FALLBACK_LANGUAGE = 'en'


class LegalDocumentView(APIView):
    """GET /legal/<kind>/ — the published Terms of Use or Privacy Policy.

    Public, and deliberately so: someone has to be able to read what they
    are agreeing to before they have agreed to anything.
    """

    authentication_classes = [OptionalMobileTokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, kind):
        if kind not in dict(LegalDocument.Kind.choices):
            return Response({'detail': 'Unknown document.'}, status=404)

        now = timezone.now()
        language = (request.headers.get('Accept-Language', '')
                    .split(',')[0].split('-')[0].strip().lower())

        document = self._published(kind, language, now)
        used_fallback = False
        if document is None and language != FALLBACK_LANGUAGE:
            # An unauthored translation falls back to English rather than
            # showing nothing: the English text is still the agreement.
            document = self._published(kind, FALLBACK_LANGUAGE, now)
            used_fallback = document is not None

        if document is None:
            return Response(
                {'detail': 'This document has not been published yet.',
                 'kind': kind, 'published': False},
                status=404)

        return Response({
            'kind': document.kind,
            'version': document.version,
            'language': document.language,
            'language_fallback': used_fallback,
            'title': document.title,
            'body': document.body,
            'effective_from': (document.effective_from.isoformat()
                               if document.effective_from else None),
            'updated_at': document.updated_at.isoformat(),
            'published': True,
        })

    def _published(self, kind, language, now):
        return (LegalDocument.objects
                .filter(kind=kind, language=language, is_published=True)
                .filter(effective_from__lte=now)
                .order_by('-effective_from', '-created_at')
                .first())
