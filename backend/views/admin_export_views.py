from django.http import HttpResponse
from django.views.decorators.http import require_GET
from celery.result import AsyncResult
from django.utils.safestring import mark_safe


def get_task_status_html(current_url):
    """Генерирует HTML с автоматической проверкой статуса задачи и отображением статусных сообщений"""

    return mark_safe(f"""
<div id="task-status">
    <p id="status-message">Идёт подготовка файла... (автообновление через 3 сек)</p>
    <script>
        function checkStatus() {{
            fetch('{current_url}', {{ 
                headers: {{ 
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json' 
                }} 
            }})
            .then(response => {{
                if (response.status === 200) {{
                    // Обновляем сообщение перед редиректом
                    document.getElementById('status-message').innerHTML = 
                        '<span style="color:green;">✓ Файл готов! Загрузка начнётся автоматически...</span>';
                    // Перенаправляем на скачивание файла
                    setTimeout(() => window.location.href = '{current_url}', 1000);
                    
                }} else if (response.status === 202) {{
                    // Файл ещё в обработке
                    document.getElementById('status-message').innerHTML = 
                        'Идёт подготовка файла... (автообновление через 3 сек)';
                    setTimeout(checkStatus, 3000);
                }} else {{
                    // Ошибка или другой статус
                    document.getElementById('status-message').innerHTML = 
                        '<span style="color:red;">⚠ Произошла ошибка при подготовке файла. Повторная попытка...</span>';
                    setTimeout(checkStatus, 3000);
                }}
            }})
            .catch(error => {{
                console.error('Ошибка:', error);
                setTimeout(checkStatus, 3000);
            }});
        }}

        // Запускаем первую проверку через 3 секунды
        setTimeout(checkStatus, 3000);
    </script>
</div>
""")


@require_GET
def download_csv_view(request):
    """
    Позволяет пользователю скачать готовый Excel-файл
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
            response = HttpResponse(
                csv_data,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="products_export.xlsx"'
            return response
        except Exception as e:
            return HttpResponse(f'Ошибка при получении данных: {str(e)}',
                                status=500)
    elif result.failed():
        return HttpResponse('Произошла ошибка при формировании файла',
                            status=500)
    return HttpResponse(get_task_status_html(request.get_full_path()),
                        status=202)
