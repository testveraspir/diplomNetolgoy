function initImportForm() {
    const urlRadio = document.getElementById('source_url');
    const fileRadio = document.getElementById('source_file');
    const urlField = document.getElementById('url_field');
    const fileField = document.getElementById('file_field');

    function toggleFields() {
        urlField.classList.toggle('hidden', !urlRadio.checked);
        fileField.classList.toggle('hidden', !fileRadio.checked);
    }

    if (urlRadio && fileRadio && urlField && fileField) {
        urlRadio.addEventListener('change', toggleFields);
        fileRadio.addEventListener('change', toggleFields);
        toggleFields();
    }
}

document.addEventListener('DOMContentLoaded', initImportForm);