from django.http import HttpResponse
from django.views.decorators.http import require_GET
from celery.result import AsyncResult


@require_GET
def download_csv_view(request):
    """
    Позволяет пользователю скачать готовый CSV-файл
    после завершения фоновой задачи обработки данных.
    Если файл ещё не готов, информирует о текущем статусе выполнения.
    """

    task_id = request.GET.get('task_id')
    if not task_id:
        return HttpResponse('Не указан task_id', status=400)

    result = AsyncResult(task_id)

    if result.ready():
        try:
            csv_data = result.get()
            response = HttpResponse(csv_data,
                                    content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
            return response
        except Exception as e:
            return HttpResponse(f'Ошибка при получении данных: {str(e)}',
                                status=500)
    elif result.failed():
        return HttpResponse('Произошла ошибка при формировании файла',
                            status=500)
    else:
        return HttpResponse('Данные ещё формируются. Попробуйте снова через минуту.',
                            status=202)
