from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Sum, F
from backend.models import (User, Shop, Category, ProductInfo,
                            ProductParameter, Order, OrderItem,
                            Contact, ConfirmEmailToken)
from backend.signals import new_order_signal
from django.db import transaction


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
    list_editable = ('type',)
    inlines = [ContactInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_info_display', 'quantity',
                       'price', 'sum', 'product_info')

    def product_info_display(self, obj):
        if obj.product_info:
            return f"{obj.product_info.product.name}" \
                   f" ({obj.product_info.model}) - {obj.product_info.shop.name}"
        return "-"

    product_info_display.short_description = 'Товар'

    def price(self, obj):
        return obj.product_info.price if obj.product_info else 0

    price.short_description = 'Цена'

    def sum(self, obj):
        return obj.quantity *\
            (obj.product_info.price if obj.product_info else 0)

    sum.short_description = 'Сумма'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('get_user_email', 'state',
                    'total_sum_display', 'contact_info', 'dt')
    list_filter = ('state', )
    list_editable = ('state',)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = [field.name for field in self.model._meta.fields]
        readonly_fields.remove('state')
        readonly_fields.extend(['get_user_email',
                                'total_sum_display',
                                'contact_info'])
        return readonly_fields

    def get_user_email(self, obj):
        return obj.user.email

    get_user_email.short_description = 'Email пользователя'

    def total_sum_display(self, obj):
        total = obj.ordered_items.aggregate(
            total=Sum(F('quantity') * F('product_info__price')))['total'] or 0
        return f"{total} руб."

    total_sum_display.short_description = 'Общая сумма'

    def contact_info(self, obj):
        if obj.contact:
            return f"{obj.contact.city}, {obj.contact.street}, {obj.contact.phone}"
        return "-"

    contact_info.short_description = 'Контактные данные'

    def has_add_permission(self, request):
        return False

    def changeform_view(self, request, object_id=None,
                        form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_save_and_continue'] = False
        extra_context['show_save_and_add_another'] = False
        extra_context['show_delete'] = False
        return super().changeform_view(request, object_id,
                                       form_url, extra_context)

    def save_model(self, request, obj, form, change):
        """Отправляет сигнал при изменении статуса"""

        if change:
            original = Order.objects.get(pk=obj.pk)
            if original.state != obj.state and obj.state != 'new':
                transaction.on_commit(lambda: new_order_signal(user_id=obj.user.id,
                                                               state=obj.state))

        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Обрабатывает сохранение связанных объектов (OrderItem)"""
        super().save_formset(request, form, formset, change)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    pass


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 0
    list_display = ('product_info', 'parameter', 'value')


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    inlines = [ProductParameterInline]
    list_display = ('model', 'external_id', 'product',
                    'shop', 'quantity', 'price', 'price_rrc')
    list_filter = ('shop', 'product__category')


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at',)
