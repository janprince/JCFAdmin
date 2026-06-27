from rest_framework import serializers

from members.models import Contact


class MemberSerializer(serializers.ModelSerializer):
    """Public-safe view of a Contact for the logged-in member."""

    phone = serializers.SerializerMethodField()
    centre = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            'id', 'full_name', 'email', 'phone', 'gender',
            'is_member', 'is_student', 'is_active', 'centre',
        ]

    def get_phone(self, obj):
        return str(obj.phone) if obj.phone else ''

    def get_centre(self, obj):
        return obj.centre.name if obj.centre_id else None
