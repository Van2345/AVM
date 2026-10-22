from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import ActivityLog, AssistanceRequest, Assignment, User, Volunteer


class AssistanceUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "full_name", "email", "role")


class AssistanceUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class AssistanceUserAdmin(UserAdmin):
    add_form = AssistanceUserCreationForm
    form = AssistanceUserChangeForm
    list_display = ("username", "full_name", "email", "role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Assistance account", {"fields": ("full_name", "role", "created_at")}),
    )
    readonly_fields = ("created_at",)
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "full_name",
                    "email",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


admin.site.register(Volunteer)
admin.site.register(AssistanceRequest)
admin.site.register(Assignment)
admin.site.register(ActivityLog)
