from django.core.files.storage import default_storage
from rest_framework import serializers
from backend.models import (User, Category, Shop, ProductInfo,
                            Product, ProductParameter, OrderItem,
                            Order, Contact)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure',
                  'building', 'apartment', 'user', 'phone')
        read_only_fields = ('id',)
        extra_kwargs = {
            'user': {'write_only': True}
        }


class UserSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(read_only=True, many=True)
    avatar = serializers.SerializerMethodField()
    avatar_thumbnails = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name',
                  'email', 'company', 'position', 'contacts',
                  'avatar', 'avatar_thumbnails')
        read_only_fields = ('id',)

    def get_avatar(self, obj):
        if not obj.avatar:
            return None

        request = self.context.get('request')
        avatar_data = {
            'width': obj.avatar.width,
            'height': obj.avatar.height
        }

        if request:
            avatar_data['url'] = request.build_absolute_uri(obj.avatar.url)
        else:
            avatar_data['url'] = obj.avatar.url

        return avatar_data

    def get_avatar_thumbnails(self, obj):
        if not hasattr(obj, 'avatar_thumbnails') or not obj.avatar_thumbnails:
            return {}

        request = self.context.get('request')
        result = {}

        for size, path in obj.avatar_thumbnails.items():
            if default_storage.exists(path):
                url = default_storage.url(path)
                result[size] = {
                    'url': request.build_absolute_uri(url) if request else url,
                    'dimensions': size
                }

        return result


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name',)
        read_only_fields = ('id',)


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'state',)
        read_only_fields = ('id',)


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    image = serializers.SerializerMethodField()
    thumbnails = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ('name', 'category', 'image', 'thumbnails')

    def get_image(self, obj):
        if not obj.image:
            return None

        request = self.context.get("request")
        image_data = {
            'width': obj.image.width,
            'height': obj.image.height
        }

        try:
            image_url = obj.image.url
            image_data['original'] = request.build_absolute_uri(image_url)\
                if request else image_url
        except ValueError:
            image_data['original'] = None

        return image_data

    def get_thumbnails(self, obj):
        if not hasattr(obj, 'thumbnails') or not obj.thumbnails:
            return {}

        request = self.context.get("request")
        result = {}

        for size, path in obj.thumbnails.items():
            if not path:
                continue

            try:
                if default_storage.exists(path):
                    storage_url = default_storage.url(path)
                    result[size] = {
                        'url': request.build_absolute_uri(storage_url) if request else storage_url,
                        'dimensions': size
                    }
            except (ValueError, NotImplementedError):
                continue
        return result


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.StringRelatedField()

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value',)


class ProductInfoSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True,
                                                    many=True)

    class Meta:
        model = ProductInfo
        fields = ('id', 'model', 'product', 'shop', 'quantity',
                  'price', 'price_rrc', 'product_parameters',)
        read_only_fields = ('id',)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity', 'order',)
        read_only_fields = ('id',)
        extra_kwargs = {
            'order': {'write_only': True}
        }


class OrderItemCreateSerializer(OrderItemSerializer):
    product_info = ProductInfoSerializer(read_only=True)


class OrderSerializer(serializers.ModelSerializer):
    ordered_items = OrderItemCreateSerializer(read_only=True,
                                              many=True)

    total_sum = serializers.IntegerField()
    contact = ContactSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'ordered_items', 'state',
                  'dt', 'total_sum', 'contact',)
        read_only_fields = ('id',)


class PartnerOrderItemSerializer(serializers.ModelSerializer):
    product_info = ProductInfoSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity',)
        read_only_fields = ('id',)


class PartnerOrderSerializer(serializers.ModelSerializer):
    ordered_items = PartnerOrderItemSerializer(many=True, read_only=True)
    total_sum = serializers.SerializerMethodField()
    contact = ContactSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'ordered_items', 'state',
                  'dt', 'total_sum', 'contact',)
        read_only_fields = ('id',)

    def get_total_sum(self, obj):
        return obj.partner_sum
