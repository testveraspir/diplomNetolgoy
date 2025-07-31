from django.core.exceptions import ValidationError


class CustomMinimumLengthValidator:
    def __init__(self, min_length=10):
        self.min_length = min_length

    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                "Пароль должен содержать минимум 10 символов",
                code='password_too_short'
            )

    def get_help_text(self):
        return "Минимальная длина пароля - 10 символов"
