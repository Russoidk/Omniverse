from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_subscribed', 'is_active', 'is_staff', 'created_at')
    list_filter = ('is_subscribed', 'is_active', 'is_staff', 'is_superuser')
    list_editable = ('is_subscribed',)
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    readonly_fields = ('password', 'last_login', 'date_joined', 'created_at', 'updated_at')
    filter_horizontal = ('groups', 'user_permissions')
    fieldsets = (
        ('Cuenta', {'fields': ('email', 'password', 'first_name', 'last_name')}),
        ('Suscripción', {'fields': ('is_subscribed',)}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
