"""
Mobile payments API: causes + Paystack donations.

Flow (mirrors the website): the app collects payment with the Paystack public
key (card + MoMo via flutter_paystack), gets a transaction `reference`, then
calls `donations/verify/`. We verify server-side with the secret key and record
the Donation. The shared Paystack webhook remains a safety net. Donations made
by a logged-in member are attributed to their Contact.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from decimal import Decimal, InvalidOperation

from causes.models import Cause, Donation
from causes.paystack import initialize_transaction, verify_transaction
from causes.serializers import CauseListSerializer, CauseSerializer, DonationSerializer
from .authentication import IsMember, MobileTokenAuthentication


class PaymentConfigView(APIView):
    """Public Paystack key + currency for the client SDK."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
            'currency': 'GHS',
        })


class CauseListView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = CauseListSerializer
    queryset = Cause.objects.filter(is_active=True).select_related('category')


class CauseDetailView(generics.RetrieveAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = CauseSerializer
    lookup_field = 'slug'
    queryset = Cause.objects.filter(is_active=True).select_related('category')


class DonationInitializeView(APIView):
    """POST {amount, email, cause_id?} -> Paystack authorization_url + reference."""

    authentication_classes = [MobileTokenAuthentication]  # optional
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get('email', '')).strip()
        if request.auth and not email:
            email = request.auth.contact.email or ''
        if not email:
            return Response({'email': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(str(request.data.get('amount', '0')))
        except (InvalidOperation, TypeError):
            amount = Decimal('0')
        if amount <= 0:
            return Response({'amount': 'Enter a valid amount.'},
                            status=status.HTTP_400_BAD_REQUEST)

        metadata = {}
        cause_id = request.data.get('cause_id')
        if cause_id:
            metadata['custom_fields'] = [
                {'display_name': 'Cause', 'variable_name': 'cause_id', 'value': cause_id}
            ]

        data = initialize_transaction(email, int(amount * 100), metadata=metadata)
        if data is None:
            return Response({'detail': 'Could not start payment.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response({
            'authorization_url': data['authorization_url'],
            'reference': data['reference'],
        })


class DonationVerifyView(APIView):
    """POST {reference, cause_id?, is_anonymous?} -> verify + record a donation."""

    authentication_classes = [MobileTokenAuthentication]  # optional
    permission_classes = [AllowAny]

    def post(self, request):
        reference = str(request.data.get('reference', '')).strip()
        if not reference:
            return Response({'reference': 'This field is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        existing = Donation.objects.filter(paystack_reference=reference).first()
        if existing:
            return Response(
                {'status': 'already_processed', 'donation': DonationSerializer(existing).data}
            )

        tx = verify_transaction(reference)
        if tx is None:
            return Response({'detail': 'Payment verification failed.'},
                            status=status.HTTP_400_BAD_REQUEST)

        cause = None
        cause_id = request.data.get('cause_id')
        if cause_id:
            cause = Cause.objects.filter(id=cause_id, is_active=True).first()

        contact = request.auth.contact if request.auth else None
        customer = tx.get('customer', {})
        donor_name = (contact.full_name if contact
                      else customer.get('first_name', '') or customer.get('email', ''))
        donor_email = (contact.email if contact else customer.get('email', '')) or ''

        donation = Donation.objects.create(
            cause=cause,
            contact=contact,
            donor_name=donor_name,
            donor_email=donor_email,
            amount=tx['amount'] / 100,  # pesewas -> GHS
            currency=tx.get('currency', 'GHS'),
            method=Donation.Method.ONLINE,
            status=Donation.Status.COMPLETED,
            paystack_reference=reference,
            is_anonymous=bool(request.data.get('is_anonymous', False)),
            donated_at=tx.get('paid_at') or timezone.now(),
        )
        return Response(
            {'status': 'success', 'donation': DonationSerializer(donation).data},
            status=status.HTTP_201_CREATED,
        )


class MyDonationsView(generics.ListAPIView):
    """A logged-in member's donation history."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]
    serializer_class = DonationSerializer

    def get_queryset(self):
        return Donation.objects.filter(contact=self.request.auth.contact)
