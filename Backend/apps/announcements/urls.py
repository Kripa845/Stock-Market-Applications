from django.urls import path

from .views import AnnouncementFilterOptions, AnnouncementList

urlpatterns = [
    path("api/announcements/", AnnouncementList.as_view()),
    path("api/announcements/filters/", AnnouncementFilterOptions.as_view()),
]