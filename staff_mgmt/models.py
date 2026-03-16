from django.db import models
from members.models import Contact


class Worker(models.Model):
    contact = models.OneToOneField(Contact, on_delete=models.CASCADE, related_name='worker')
    role = models.CharField(max_length=255, blank=True)
    duties = models.TextField(blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.contact.full_name}"


class Representative(models.Model):
    contact = models.OneToOneField(Contact, on_delete=models.CASCADE, related_name='representative')
    country = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.contact.full_name}"
