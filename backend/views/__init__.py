from .partner_views import PartnerUpdate, PartnerOrders, PartnerState
from .user_views import (RegisterAccount, ConfirmAccount,
                         AccountDetails, LoginAccount, ContactView)
from .basket_views import BasketView
from .shops_views import CategoryView, ShopView, ProductInfoView, OrderView
from .admin_export_views import download_csv_view
from .admin_import_views import ImportFromAdmin
from .social_auth_views import yandex_oauth_callback
