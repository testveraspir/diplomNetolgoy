from django.http import HttpResponse
from django.views.decorators.http import require_GET
from celery.result import AsyncResult
from django.utils.safestring import mark_safe


def get_task_status_html(current_url):
    """Генерирует HTML с автоматической проверкой статуса задачи"""

    return mark_safe(f"""
    <div id="task-status">
        <p>Идёт подготовка файла... (автообновление через 3 сек)</p>
        <script>
            function checkStatus() {{
                fetch('{current_url}', {{ headers: {{ 'X-Requested-With': 'XMLHttpRequest' }} }})
                    .then(response => {{
                        if (response.status === 200) {{
                            document.getElementById('task-status').innerHTML = 
                                '<p style="color:green">✓ Файл готов для загрузки!</p>';
                            window.location.href = '{current_url}';
                        }} else {{
                            setTimeout(() => window.location.reload(), 3000);
                        }}
                    }});
            }}
            setTimeout(checkStatus, 3000);
        </script>
    </div>
    """)


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
    return HttpResponse(get_task_status_html(request.get_full_path()),
                        status=202)
