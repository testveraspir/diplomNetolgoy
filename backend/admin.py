from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from backend.models import (User, Shop, Category, Product,
                            ProductInfo, Parameter, ProductParameter,
                            Order, OrderItem, Contact, ConfirmEmailToken)


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 1
    fields = ('city', 'street', 'house', 'structure', 'building', 'apartment', 'phone')
    verbose_name = 'Контакт'
    verbose_name_plural = 'Контакты пользователя'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Панель управления пользователями."""

    model = User

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Персональная информация', {'fields': ('first_name', 'last_name', 'company', 'position')}),
        ('Даты', {'fields': ('date_joined', )}),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'type')
    inlines = [ContactInline]


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    pass


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    pass


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    pass


@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    pass



@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at',)
