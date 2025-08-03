from django.apps import AppConfig


class BackendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend'

    def ready(self):

        import backend.signals
        from django_rest_passwordreset.models import ResetPasswordToken
        from django.contrib import admin

        if ResetPasswordToken in admin.site._registry:
            del admin.site._registry[ResetPasswordToken]
