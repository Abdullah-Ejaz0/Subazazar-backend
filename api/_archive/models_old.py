from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid


class UserPreference(models.Model):
	phone_number = models.CharField(max_length=25, unique=True)
	full_name = models.CharField(max_length=120, blank=True, default='')
	location = models.CharField(max_length=120, blank=True, default='')
	profile_photo = models.ImageField(upload_to='profiles/%Y/%m/%d/', blank=True, null=True)
	preferred_language = models.CharField(max_length=30, blank=True, default='')
	voice_assistant_enabled = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.phone_number} ({self.preferred_language or 'not-set'})"


class LanguageOnboardingSession(models.Model):
	token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	preferred_language = models.CharField(max_length=30)
	voice_assistant_enabled = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	expires_at = models.DateTimeField()

	def save(self, *args, **kwargs):
		if not self.expires_at:
			self.expires_at = timezone.now() + timedelta(hours=1)
		super().save(*args, **kwargs)

	def __str__(self):
		return f"{self.token} ({self.preferred_language})"


class ScanImageUpload(models.Model):
	class ImageSource(models.TextChoices):
		CAMERA = 'camera', 'Camera'
		GALLERY = 'gallery', 'Gallery'

	user_preference = models.ForeignKey(
		UserPreference,
		on_delete=models.CASCADE,
		related_name='scan_uploads',
	)
	image = models.ImageField(upload_to='scan_uploads/%Y/%m/%d/')
	source = models.CharField(max_length=20, choices=ImageSource.choices)
	analysis_status = models.CharField(max_length=20, default='pending')
	analysis_result = models.TextField(blank=True, default='')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"ScanImageUpload #{self.pk} ({self.user_preference.phone_number})"


class SoilHealthCard(models.Model):
	user_preference = models.ForeignKey(
		UserPreference,
		on_delete=models.CASCADE,
		related_name='soil_health_cards',
	)
	land_name = models.CharField(max_length=120, blank=True, default='')
	ph = models.FloatField()
	nitrogen = models.FloatField()
	hydrogen = models.FloatField()
	phosphate = models.FloatField()
	notes = models.TextField(blank=True, default='')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		name = self.land_name or 'Unnamed land'
		return f"SoilHealthCard #{self.pk} ({name})"


class QuestionPost(models.Model):
	user_preference = models.ForeignKey(
		UserPreference,
		on_delete=models.CASCADE,
		related_name='question_posts',
	)
	question_text = models.TextField()
	crop_disease = models.CharField(max_length=120)
	photo = models.ImageField(upload_to='question_posts/%Y/%m/%d/', blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"QuestionPost #{self.pk} ({self.crop_disease})"


class ExpertCommunityPost(models.Model):
	user_preference = models.ForeignKey(
		UserPreference,
		on_delete=models.CASCADE,
		related_name='expert_posts',
	)
	title = models.CharField(max_length=200)
	message = models.TextField()
	target_region = models.CharField(max_length=120, blank=True, default='')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"ExpertPost #{self.pk} ({self.title})"
