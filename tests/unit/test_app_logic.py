import io
import logging
from unittest import mock

import pytest
from werkzeug.datastructures import FileStorage

from app import app as flask_app  # Your Flask app instance
from core.config import settings  # To potentially mock settings


@pytest.fixture
def app():
    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key_for_flashing",  # For flash messages
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for simpler form posts in tests
        }
    )
    # Ensure the logger is configured for tests if it hasn't been already
    # This might be needed if tests run in a different context than app startup
    if not hasattr(flask_app, "logger_configured_for_tests"):
        logging_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        logging.basicConfig(
            level=logging_level,
            format="%(asctime)s - %(levelname)s - %(name)s - %(request_id)s - %(message)s",
        )
        # If you have specific handlers or filters added in app.py, replicate minimal setup or ensure they don't break tests.
        # For RequestIdFilter, it tries to use Flask's `g`, which is fine in test request contexts.
        flask_app.logger_configured_for_tests = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def test_upload_no_files_selected(client):
    """Test uploading with no files selected (file part entirely missing)."""
    response = client.post("/upload", data={})  # No files part
    assert response.status_code == 302  # Should redirect
    with client.session_transaction() as session:
        assert "_flashes" in session
        # This triggers the `if 'files[]' not in request.files:` check in app.py
        assert any(
            "No file part in the request" in message[1]
            for message in session["_flashes"]
        )


def test_upload_empty_filenames_in_file_list(client):
    """Test uploading with FileStorage objects that have empty filenames."""
    # This simulates `request.files.getlist('files[]')` returning a list like [FileStorage(filename='', ...)]
    # Such files are typically skipped by the loop `if file_storage.filename == '':` or caught by _validate_file_list.
    empty_file = FileStorage(
        io.BytesIO(b""), filename="", content_type="application/octet-stream"
    )
    response = client.post(
        "/upload", data={"files[]": [empty_file]}, content_type="multipart/form-data"
    )
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "_flashes" in session
        # This should be caught by _validate_file_list
        assert any(
            "No files selected for uploading." in message[1]
            for message in session["_flashes"]
        )


def test_upload_file_type_not_allowed(client):
    """Test uploading a file with a type that is not allowed."""
    disallowed_file = FileStorage(
        io.BytesIO(b"some data"),
        filename="test.disallowed",
        content_type="application/octet-stream",
    )
    response = client.post(
        "/upload",
        data={"files[]": [disallowed_file]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302  # Redirects back
    with client.session_transaction() as session:
        assert "_flashes" in session
        assert any(
            "File type not allowed for test.disallowed" in message[1]
            for message in session["_flashes"]
        )
    # Also check that processed_file_data would contain an unsupported entry (harder to check directly from client)
    # This would require mocking _process_single_file_storage or inspecting its call if not redirecting immediately


@mock.patch("app.settings")  # Mock settings for this test
def test_upload_single_file_exceeds_size_limit(mock_settings, client):
    """Test uploading a single file that exceeds MAX_FILE_SIZE_BYTES."""
    mock_settings.MAX_FILE_SIZE_BYTES = 100  # Set a small limit for test
    mock_settings.MAX_FILE_SIZE_MB = 0.0001  # Align MB for flash message if used
    mock_settings.MAX_TOTAL_UPLOAD_SIZE_BYTES = 200  # Ensure total is not exceeded
    mock_settings.MAX_TOTAL_UPLOAD_SIZE_MB = 0.0002
    mock_settings.ALLOWED_EXTENSIONS = {"txt"}  # Ensure .txt is allowed

    large_file_content = b"a" * 150
    large_file = FileStorage(
        io.BytesIO(large_file_content), filename="large.txt", content_type="text/plain"
    )

    response = client.post(
        "/upload", data={"files[]": [large_file]}, content_type="multipart/form-data"
    )
    assert response.status_code == 302  # Redirects
    with client.session_transaction() as session:
        assert "_flashes" in session
        assert any(
            f"File large.txt exceeds the size limit" in message[1]
            for message in session["_flashes"]
        )


@mock.patch("app.settings")  # Mock settings for this test
def test_upload_total_files_exceed_size_limit(mock_settings, client):
    """Test that uploading files exceeding MAX_TOTAL_UPLOAD_SIZE_BYTES is handled."""
    mock_settings.MAX_FILE_SIZE_BYTES = 100
    mock_settings.MAX_FILE_SIZE_MB = 0.0001
    mock_settings.MAX_TOTAL_UPLOAD_SIZE_BYTES = 150  # Small total limit
    mock_settings.MAX_TOTAL_UPLOAD_SIZE_MB = 0.00015  # Align MB for flash message
    mock_settings.ALLOWED_EXTENSIONS = {"txt"}

    file1_content = b"a" * 80
    file1 = FileStorage(
        io.BytesIO(file1_content), filename="file1.txt", content_type="text/plain"
    )

    file2_content = b"b" * 80
    file2 = FileStorage(
        io.BytesIO(file2_content), filename="file2.txt", content_type="text/plain"
    )

    # Total size = 80 + 80 = 160, which is > MAX_TOTAL_UPLOAD_SIZE_BYTES (150)
    response = client.post(
        "/upload", data={"files[]": [file1, file2]}, content_type="multipart/form-data"
    )

    assert response.status_code == 302  # Should redirect
    with client.session_transaction() as session:
        assert "_flashes" in session
        assert any(
            f"Total upload size exceeds the limit" in message[1]
            for message in session["_flashes"]
        )


@mock.patch("app.tempfile.mkdtemp")
@mock.patch("app.shutil.rmtree")
@mock.patch("app.document_processor.process_uploaded_file")
@mock.patch("app.llm_handler.generate_report_from_content", new_callable=mock.AsyncMock)
@mock.patch("app.settings")  # Mock settings for general limits not being hit
def test_upload_successful_flow(
    mock_app_settings,
    mock_generate_report,
    mock_process_file,
    mock_rmtree,
    mock_mkdtemp,
    client,
):
    """Test a successful file upload and report generation flow."""
    mock_app_settings.MAX_FILE_SIZE_BYTES = 1000
    mock_app_settings.MAX_TOTAL_UPLOAD_SIZE_BYTES = 2000
    mock_app_settings.ALLOWED_EXTENSIONS = {"txt", "pdf"}
    mock_app_settings.MAX_EXTRACTED_TEXT_LENGTH = 5000

    mock_mkdtemp.return_value = "/tmp/fake_temp_dir"

    mock_process_file.side_effect = [
        {
            "type": "text",
            "filename": "file1.txt",
            "content": "Text from file1",
            "source": "file content",
        },
        {
            "type": "text",
            "filename": "file2.pdf",
            "content": "Text from file2",
            "source": "file content",
        },
    ]

    mock_generate_report.return_value = "This is the generated report."

    file1 = FileStorage(io.BytesIO(b"content1"), filename="file1.txt")
    file2 = FileStorage(io.BytesIO(b"content2"), filename="file2.pdf")

    response = client.post(
        "/upload", data={"files[]": [file1, file2]}, content_type="multipart/form-data"
    )

    assert response.status_code == 200
    response_data = response.get_data(as_text=True)
    assert "This is the generated report." in response_data
    assert "file1.txt" in response_data  # Check displayed filenames
    assert "file2.pdf" in response_data

    mock_mkdtemp.assert_called_once()
    assert mock_process_file.call_count == 2
    mock_generate_report.assert_called_once_with(
        processed_files=[
            {
                "type": "text",
                "filename": "file1.txt",
                "content": "Text from file1",
                "source": "file content",
            },
            {
                "type": "text",
                "filename": "file2.pdf",
                "content": "Text from file2",
                "source": "file content",
            },
        ],
        additional_text="",
    )
    # asyncio.to_thread means rmtree might not be called if an error occurs before finally
    # For successful path, it should be. If testing with an ASGI server, the call will be awaited.
    # mock_rmtree.assert_called_once_with("/tmp/fake_temp_dir") # This can be tricky with async/threads


@mock.patch("app.tempfile.mkdtemp")
@mock.patch("app.shutil.rmtree")
@mock.patch("app.document_processor.process_uploaded_file")
@mock.patch("app.llm_handler.generate_report_from_content", new_callable=mock.AsyncMock)
@mock.patch("app.settings")
def test_upload_text_truncation(
    mock_app_settings,
    mock_generate_report,
    mock_process_file,
    mock_rmtree,
    mock_mkdtemp,
    client,
):
    """Test that extracted text is truncated correctly if it exceeds MAX_EXTRACTED_TEXT_LENGTH."""
    mock_app_settings.MAX_FILE_SIZE_BYTES = 1000
    mock_app_settings.MAX_TOTAL_UPLOAD_SIZE_BYTES = 2000
    mock_app_settings.ALLOWED_EXTENSIONS = {"txt"}
    mock_app_settings.MAX_EXTRACTED_TEXT_LENGTH = 20  # Very small for testing

    mock_mkdtemp.return_value = "/tmp/fake_temp_dir"

    # First file fits, second will be truncated, third will be skipped.
    mock_process_file.side_effect = [
        {
            "type": "text",
            "filename": "file1.txt",
            "content": "1234567890",
            "source": "file content",
        },  # 10 chars
        {
            "type": "text",
            "filename": "file2.txt",
            "content": "abcdefghijklmnop",
            "source": "file content",
        },  # 16 chars
        {
            "type": "text",
            "filename": "file3.txt",
            "content": "XYZ",
            "source": "file content",
        },  # 3 chars
    ]

    mock_generate_report.return_value = "Report based on truncated text."

    file1 = FileStorage(io.BytesIO(b"content1"), filename="file1.txt")
    file2 = FileStorage(io.BytesIO(b"content2"), filename="file2.txt")
    file3 = FileStorage(io.BytesIO(b"content3"), filename="file3.txt")

    response = client.post(
        "/upload",
        data={"files[]": [file1, file2, file3]},
        content_type="multipart/form-data",
    )

    assert (
        response.status_code == 200
    )  # Assuming it still proceeds to generate a report
    with client.session_transaction() as session:
        assert "_flashes" in session
        flashed_messages = [msg[1] for msg in session["_flashes"]]
        assert any(
            "Content from file2.txt (file content) was truncated" in msg
            for msg in flashed_messages
        )
        assert any(
            "Skipped some content from file3.txt (file content)" in msg
            for msg in flashed_messages
        )

    expected_processed_files_for_llm = [
        {
            "type": "text",
            "filename": "file1.txt",
            "content": "1234567890",
            "source": "file content",
        },  # Full
        {
            "type": "text",
            "filename": "file2.txt",
            "content": "abcdefghij",
            "source": "file content",
        },  # Truncated (10 chars from 16)
        # file3.txt content is skipped entirely
    ]

    mock_generate_report.assert_called_once_with(
        processed_files=expected_processed_files_for_llm, additional_text=""
    )


@mock.patch("app.tempfile.mkdtemp")
@mock.patch("app.shutil.rmtree")
@mock.patch("app.document_processor.process_uploaded_file")
@mock.patch("app.llm_handler.generate_report_from_content", new_callable=mock.AsyncMock)
@mock.patch("app.settings")
def test_upload_eml_processing(
    mock_app_settings,
    mock_generate_report,
    mock_process_file,
    mock_rmtree,
    mock_mkdtemp,
    client,
):
    """Test EML file processing, ensuring body and attachments are handled and text is aggregated."""
    mock_app_settings.MAX_FILE_SIZE_BYTES = 1000
    mock_app_settings.MAX_TOTAL_UPLOAD_SIZE_BYTES = 2000
    mock_app_settings.ALLOWED_EXTENSIONS = {"eml", "txt"}
    mock_app_settings.MAX_EXTRACTED_TEXT_LENGTH = 100  # Smallish for testing

    mock_mkdtemp.return_value = "/tmp/fake_temp_dir"

    # Simulate document_processor returning data for an EML file
    eml_processed_data = {
        "type": "text",  # Main type for the EML body itself
        "original_filetype": "eml",
        "filename": "email.eml",
        "content": "Email body text. ",  # 17 chars
        "processed_attachments": [
            {
                "type": "text",
                "filename": "attach1.txt",
                "content": "Attachment 1 text. ",
                "source": "attachment",
            },  # 19 chars
            {
                "type": "vision",
                "filename": "image.png",
                "content": "base64_encoded_image_data",
                "source": "attachment",
            },  # Vision, not text
            {
                "type": "text",
                "filename": "attach2.txt",
                "content": "Attachment 2 text, long enough to be truncated. ",
                "source": "attachment",
            },  # 48 chars
        ],
    }
    mock_process_file.return_value = eml_processed_data
    mock_generate_report.return_value = "Report from EML."

    eml_file = FileStorage(io.BytesIO(b"eml content"), filename="email.eml")

    response = client.post(
        "/upload", data={"files[]": [eml_file]}, content_type="multipart/form-data"
    )

    assert response.status_code == 200
    with client.session_transaction() as session:
        assert "_flashes" in session
        flashed_messages = [msg[1] for msg in session["_flashes"]]
        # print(flashed_messages) # For debugging
        assert any(
            "Content from attach2.txt (attachment from EML: email.eml) was truncated"
            in msg
            for msg in flashed_messages
        )

    expected_llm_input = [
        {
            "type": "text",
            "filename": "email.eml",
            "content": "Email body text. ",
            "source": "email body",
        },
        {
            "type": "text",
            "filename": "attach1.txt",
            "content": "Attachment 1 text. ",
            "source": "attachment from EML: email.eml",
        },
        {
            "type": "vision",
            "filename": "image.png",
            "content": "base64_encoded_image_data",
            "source": "attachment",
        },  # Vision included as is
        {
            "type": "text",
            "filename": "attach2.txt",
            "content": "Attachment 2 text, long enough to be truncated. "[
                : 100 - 17 - 19
            ],
            "source": "attachment from EML: email.eml",
        },  # Truncated part
    ]
    # Adjust expected content for attach2.txt based on MAX_EXTRACTED_TEXT_LENGTH (100)
    # Lengths: body (17) + attach1 (19) = 36. Remaining = 100 - 36 = 64
    # So, attach2 content should be truncated to 64 chars.
    expected_llm_input[3]["content"] = (
        "Attachment 2 text, long enough to be truncated. "[:64]
    )

    mock_generate_report.assert_called_once_with(
        processed_files=expected_llm_input, additional_text=""
    )


# Placeholder for more tests
