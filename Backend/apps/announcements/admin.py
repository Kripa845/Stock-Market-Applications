from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("published_at", "symbol", "type", "category", "source", "title")
    list_filter = ("type", "category", "source", "is_event")
    search_fields = ("symbol", "title")