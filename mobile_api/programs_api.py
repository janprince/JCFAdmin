"""
Mobile programs API: list/detail (audience-gated), register (dynamic pricing),
verify payment (atomic room allocation + QR), and my registrations.
"""
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from causes.paystack import initialize_transaction, verify_transaction
from programs.models import AccommodationTier, CostLineItem, Program, Registration
from programs.services import RoomSoldOut, confirm_registration
from .authentication import IsMember, MobileTokenAuthentication


def is_eligible(contact, program) -> bool:
    if program.audience == Program.Audience.PUBLIC:
        return True
    if contact is None:
        return False
    if program.audience == Program.Audience.MEMBERS:
        return bool(contact.is_member or contact.is_student)
    if program.audience == Program.Audience.STUDENTS:
        return bool(contact.is_student)
    return False


def allowed_audiences(contact):
    audiences = {Program.Audience.PUBLIC}
    if contact is not None:
        if contact.is_member or contact.is_student:
            audiences.add(Program.Audience.MEMBERS)
        if contact.is_student:
            audiences.add(Program.Audience.STUDENTS)
    return audiences


# --- Serializers ---

class AccommodationTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccommodationTier
        fields = ['id', 'name', 'description', 'price_per_person', 'rooms_available', 'is_sold_out']


class CostLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostLineItem
        fields = ['id', 'label', 'amount', 'unit']


class ProgramListSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = [
            'id', 'slug', 'title', 'year', 'audience', 'starts_on', 'ends_on',
            'venue', 'location', 'image_url', 'requires_payment', 'currency',
        ]

    def get_image_url(self, obj):
        return obj.image.url if obj.image else ''


class ProgramDetailSerializer(ProgramListSerializer):
    accommodation_tiers = serializers.SerializerMethodField()
    cost_line_items = serializers.SerializerMethodField()
    registration_open = serializers.SerializerMethodField()

    class Meta(ProgramListSerializer.Meta):
        fields = ProgramListSerializer.Meta.fields + [
            'description', 'form_schema', 'capacity',
            'registration_opens_at', 'registration_closes_at', 'registration_open',
            'accommodation_tiers', 'cost_line_items',
        ]

    def get_accommodation_tiers(self, obj):
        qs = obj.accommodation_tiers.filter(is_active=True)
        return AccommodationTierSerializer(qs, many=True).data

    def get_cost_line_items(self, obj):
        qs = obj.cost_line_items.filter(is_active=True)
        return CostLineItemSerializer(qs, many=True).data

    def get_registration_open(self, obj):
        now = timezone.now()
        if obj.registration_opens_at and now < obj.registration_opens_at:
            return False
        if obj.registration_closes_at and now > obj.registration_closes_at:
            return False
        return True


class RegistrationSerializer(serializers.ModelSerializer):
    program_title = serializers.CharField(source='program.title', read_only=True)
    program_slug = serializers.CharField(source='program.slug', read_only=True)
    qr_url = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = [
            'id', 'reference', 'program', 'program_slug', 'program_title',
            'quantity', 'accommodation_tier', 'answers', 'amount', 'currency',
            'status', 'qr_url', 'created_at', 'confirmed_at',
        ]

    def get_qr_url(self, obj):
        return obj.qr.url if obj.qr else ''


# --- Views ---

class ProgramListView(generics.ListAPIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]
    serializer_class = ProgramListSerializer

    def get_queryset(self):
        contact = self.request.auth.contact if self.request.auth else None
        qs = Program.objects.filter(is_published=True)
        return qs.filter(audience__in=allowed_audiences(contact))


class ProgramDetailView(generics.RetrieveAPIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [AllowAny]
    serializer_class = ProgramDetailSerializer
    lookup_field = 'slug'
    queryset = Program.objects.filter(is_published=True)

    def retrieve(self, request, *args, **kwargs):
        program = self.get_object()
        contact = request.auth.contact if request.auth else None
        if not is_eligible(contact, program):
            raise PermissionDenied('This program is for registered members or students.')
        return Response(self.get_serializer(program).data)


class RegisterView(APIView):
    """POST programs/<slug>/register/ {quantity, accommodation_tier_id?, answers?}."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request, slug):
        program = generics.get_object_or_404(Program, slug=slug, is_published=True)
        contact = request.auth.contact

        if not is_eligible(contact, program):
            raise PermissionDenied('You are not eligible to register for this program.')

        # Registration window
        now = timezone.now()
        if program.registration_opens_at and now < program.registration_opens_at:
            raise ValidationError('Registration is not open yet.')
        if program.registration_closes_at and now > program.registration_closes_at:
            raise ValidationError('Registration has closed.')

        quantity = int(request.data.get('quantity', 1) or 1)
        if quantity < 1:
            raise ValidationError('quantity must be at least 1.')

        tier = None
        tier_id = request.data.get('accommodation_tier_id')
        if tier_id:
            tier = AccommodationTier.objects.filter(
                id=tier_id, program=program, is_active=True
            ).first()
            if tier is None:
                raise ValidationError('Invalid accommodation tier.')
            if tier.is_sold_out:
                raise ValidationError('That accommodation tier is sold out.')

        amount = program.compute_amount(quantity=quantity, tier=tier)

        registration = Registration.objects.create(
            program=program,
            contact=contact,
            quantity=quantity,
            accommodation_tier=tier,
            answers=request.data.get('answers', {}) or {},
            amount=amount,
            currency=program.currency,
        )
        registration.assign_reference()

        # Free program (or zero amount) -> confirm immediately.
        if not program.requires_payment or amount == 0:
            confirm_registration(registration)
            return Response(
                {'requires_payment': False, 'registration': RegistrationSerializer(registration).data},
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                'requires_payment': True,
                'amount': str(amount),
                'currency': program.currency,
                'reference': registration.reference,
                'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
                'registration': RegistrationSerializer(registration).data,
            },
            status=status.HTTP_201_CREATED,
        )


class InitializeRegistrationPaymentView(APIView):
    """POST registrations/<reference>/initialize/ -> Paystack authorization_url."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request, reference):
        registration = generics.get_object_or_404(
            Registration, reference=reference, contact=request.auth.contact
        )
        if registration.status == Registration.Status.CONFIRMED:
            raise ValidationError('This registration is already confirmed.')
        email = registration.contact.email or ''
        if not email:
            raise ValidationError('Your membership record has no email for the receipt.')

        data = initialize_transaction(
            email,
            int(registration.amount * 100),
            metadata={'registration_reference': registration.reference},
        )
        if data is None:
            return Response({'detail': 'Could not start payment.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        registration.paystack_reference = data['reference']
        registration.save(update_fields=['paystack_reference'])
        return Response({
            'authorization_url': data['authorization_url'],
            'reference': data['reference'],
        })


class VerifyRegistrationView(APIView):
    """POST registrations/<reference>/verify/ {paystack_reference} -> confirm."""

    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]

    def post(self, request, reference):
        registration = generics.get_object_or_404(
            Registration, reference=reference, contact=request.auth.contact
        )
        if registration.status == Registration.Status.CONFIRMED:
            return Response({'status': 'already_confirmed',
                             'registration': RegistrationSerializer(registration).data})

        paystack_reference = (
            str(request.data.get('paystack_reference', '')).strip()
            or registration.paystack_reference
        )
        if not paystack_reference:
            raise ValidationError('paystack_reference is required.')

        tx = verify_transaction(paystack_reference)
        if tx is None:
            return Response({'detail': 'Payment verification failed.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if (tx['amount'] / 100) < float(registration.amount):
            return Response({'detail': 'Payment amount is less than the registration fee.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            confirm_registration(registration, paystack_reference=paystack_reference)
        except RoomSoldOut:
            return Response({'detail': 'The selected accommodation is now sold out.'},
                            status=status.HTTP_409_CONFLICT)

        return Response({'status': 'confirmed',
                         'registration': RegistrationSerializer(registration).data})


class MyRegistrationsView(generics.ListAPIView):
    authentication_classes = [MobileTokenAuthentication]
    permission_classes = [IsMember]
    serializer_class = RegistrationSerializer

    def get_queryset(self):
        return Registration.objects.filter(contact=self.request.auth.contact).select_related('program')
