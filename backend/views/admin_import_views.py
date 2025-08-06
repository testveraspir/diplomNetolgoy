from django.http import HttpResponseRedirect
from django.contrib import messages
from django.core.validators import URLValidator, ValidationError
from django.core.cache import cache
from django.shortcuts import reverse
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from backend.tasks import do_import
from celery.result import AsyncResult


@method_decorator(staff_member_required, name='dispatch')
class ImportFromAdmin(View):
    """Класс для обработки импорта данных из админки."""

    def post(self, request):
        source_type = request.POST.get('source_type')
        user_id = request.POST.get('user_id')
        source = None

        if source_type == 'url':
            url = request.POST.get('url', '').strip()
            try:
                URLValidator()(url)
                source = url
            except ValidationError as e:
                messages.error(request, f'Ошибка URL: {str(e)}')
                return self.redirect_to_admin()

        elif source_type == 'file':
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                messages.error(request, 'Файл не загружен')
                return self.redirect_to_admin()

            if not uploaded_file.name.endswith(('.yaml', '.yml')):
                messages.error(request, 'Файл должен быть в формате YAML')
                return self.redirect_to_admin()

            if uploaded_file.size > 10 * 1024 * 1024:
                messages.error(request, 'Размер файла не должен превышать 10MB')
                return self.redirect_to_admin()

            source = uploaded_file.read()

        task = do_import.delay(source, user_id)
        cache.set(f"task_owner_{task.id}", request.user.id, timeout=86400)
        task_url = reverse('admin:task-status-admin',
                           kwargs={'task_id': str(task.id)})
        message = mark_safe(
            f'Импорт начат в фоновом режиме.'
            f' <a href="{task_url}">Проверить результат</a>')
        messages.success(request, message)
        return self.redirect_to_admin()

    def get(self, request, task_id=None):
        if not task_id:
            return self.redirect_to_admin()

        task = AsyncResult(task_id)
        task_owner_id = cache.get(f'task_owner_{task_id}')

        if task_owner_id is None or task_owner_id != request.user.id:
            messages.error(request, 'У вас нет прав на просмотр этой задачи.')
            return self.redirect_to_admin()

        if task.failed():
            messages.error(request, {str(task.result)})
        elif task.ready():
            messages.success(request, 'Данные успешно загружены в таблицу')
        else:
            task_url = reverse('admin:task-status-admin',
                               kwargs={'task_id': str(task.id)})
            refresh_message = mark_safe('Идёт процесс загрузки данных. '
                                        f'<a href="{task_url}">Обновить статус</a>')
            messages.info(request, refresh_message)
        return self.redirect_to_admin()

    def redirect_to_admin(self):
        return HttpResponseRedirect(reverse('admin:backend_user_changelist'))
