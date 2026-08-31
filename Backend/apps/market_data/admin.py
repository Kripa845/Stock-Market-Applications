from django.contrib import admin
from .models import DailyPrice,FloorsheetTransaction
# Register your models here.
admin.site.register(DailyPrice)
admin.site.register(FloorsheetTransaction)
