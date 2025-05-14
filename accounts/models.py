from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password

 


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            raise ValueError("The Password field must be set")
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not password:
            raise ValueError("Superuser must have a password.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

 
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',   
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions_set',  
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions'
    )

    def __str__(self):
        return self.email



class Company(models.Model):
    user_id = models.CharField(max_length=255, unique=True,blank=True, null=True)
    company_name = models.CharField(max_length=255,blank=True, null=True)
    company_admin_name = models.CharField(max_length=255,blank=True, null=True)
    email_address = models.EmailField(unique=True,blank=True, null=True)   
    password = models.CharField(max_length=255)  
    phone_no1 = models.CharField(max_length=15,blank=True, null=True)
    phone_no2 = models.CharField(max_length=15, blank=True, null=True)   
    company_logo = models.ImageField(upload_to='company_photos/', null=True, blank=True)

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('blocked', 'Blocked'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    currency = models.CharField(max_length=255,blank=True, null=True) 
    currency_code = models.CharField(max_length=255,blank=True, null=True) 
    date_joined = models.DateTimeField(auto_now_add=True)
    
    def set_password(self, raw_password):
        """Hash password before saving"""
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        """Check if a raw password matches the stored hashed password"""
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.company_name
