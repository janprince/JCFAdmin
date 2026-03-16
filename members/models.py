import os
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField


class Contact(models.Model):
    class Gender(models.TextChoices):
        MALE = 'Male', 'Male'
        FEMALE = 'Female', 'Female'

    full_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    phone = PhoneNumberField()
    telephone = PhoneNumberField(blank=True)
    email = models.EmailField(blank=True)
    profession = models.CharField(max_length=255, blank=True)
    religion = models.CharField(max_length=255, default='N/A')
    residence = models.CharField(max_length=255, blank=True)
    hometown = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, default='Ghana')
    father_name = models.CharField(max_length=255, blank=True)
    mother_name = models.CharField(max_length=255, blank=True)
    referral = models.CharField(max_length=255, blank=True)
    is_member = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    is_initiate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['full_name', 'phone'], name='unique_contact_name_phone')
        ]
        ordering = ['-id']

    def __str__(self):
        return self.full_name


class DataFile(models.Model):
    contact = models.ForeignKey(Contact, related_name='datafiles', on_delete=models.RESTRICT)
    file = models.FileField(upload_to='data-files/')
    created_at = models.DateTimeField(auto_now_add=True)

    def extension(self):
        name, ext = os.path.splitext(self.file.name)
        return ext

    @property
    def filesize(self):
        x = self.file.size
        if x < 512000:
            return f"{round(x / 1000, 2)} kb"
        elif x < 512000000:
            return f"{round(x / 1000000, 2)} MB"
        return f"{round(x / 1000000000, 2)} GB"

    def __str__(self):
        return f"File for {self.contact.full_name}"


class Inquiry(models.Model):
    contact = models.ForeignKey(Contact, related_name='inquiries', on_delete=models.CASCADE)
    subject = models.TextField(blank=True)
    remark = models.TextField(blank=True)
    guidance = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'inquiries'

    def __str__(self):
        return f"Inquiry: {self.contact.full_name}"
