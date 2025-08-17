from social_django.utils import load_strategy
from social_core.backends.yandex import YandexOAuth2
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authtoken.models import Token


@csrf_exempt
def yandex_oauth_callback(request):
    """Обработчик callback с генерацией DRF Token"""

    try:
        # Аутентификация через Yandex
        strategy = load_strategy(request)
        backend = YandexOAuth2(strategy=strategy)

        if 'state' in request.GET:
            request.session['social_auth_state'] = request.GET['state']

        # Завершаем процесс аутентификации
        user = backend.auth_complete(request=request)

        # Генерируем или получаем токен DRF
        token, created = Token.objects.get_or_create(user=user)

        # Возвращаем ответ с токеном
        return JsonResponse({'status': 'success',
                             'user_id': user.id,
                             'email': user.email,
                             'token': token.key,
                             'is_new_user': created
        })

    except Exception as e:
        return JsonResponse({'status': 'error',
                             'error': str(e),
                             'session_data': dict(request.session)},
                            status=400)
