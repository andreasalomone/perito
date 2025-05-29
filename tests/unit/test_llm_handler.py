"""
Unit tests for LLM handler functionality.
Tests the LLM processing step in the user flow: prompt assembly and Google Gemini API calls.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, ANY
from google.genai import types
from core.config import settings
from core.prompt_config import PREDEFINED_STYLE_REFERENCE_TEXT, REPORT_STRUCTURE_PROMPT, SYSTEM_INSTRUCTION

# Import the functions under test
import llm_handler
from llm_handler import generate_report_from_content


class TestPromptAssembly(unittest.TestCase):
    """Test prompt construction and assembly for LLM calls."""
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_generate_report_from_content_with_vision_files(self, mock_gemini_client_constructor, mock_get_cache):
        """Test report generation with vision files (PDF/images) for cache hit and miss."""
        
        processed_files = [
            {'type': 'vision', 'path': '/tmp/test.pdf', 'mime_type': 'application/pdf', 'filename': 'test.pdf'},
            {'type': 'vision', 'path': '/tmp/image.png', 'mime_type': 'image/png', 'filename': 'image.png'}
        ]
        additional_text = "Sample extracted text from DOCX files"
        expected_report_content = "Generated insurance report content"

        for cache_scenario_active_cache_name in ["mocked_cache_name_vision", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name
            
            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_uploaded_file_pdf = Mock(spec=types.File, name='uploaded_pdf')
            mock_uploaded_file_pdf.name = 'files/pdf_file_id'
            mock_uploaded_file_image = Mock(spec=types.File, name='uploaded_image')
            mock_uploaded_file_image.name = 'files/image_file_id'
            
            mock_client_instance.files.upload.side_effect = [
                mock_uploaded_file_pdf,
                mock_uploaded_file_image
            ]

            mock_response = Mock()
            mock_response.text = expected_report_content
            mock_response.candidates = [] # Ensure .text is prioritized
            mock_response.prompt_feedback = None
            mock_client_instance.models.generate_content.return_value = mock_response
            
            # Act
            result = generate_report_from_content(processed_files, additional_text)
                
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            self.assertEqual(mock_client_instance.files.upload.call_count, 2)
            mock_client_instance.models.generate_content.assert_called_once()
            
            call_args = mock_client_instance.models.generate_content.call_args
            gen_config = call_args.kwargs['config']
            prompt_parts = call_args.kwargs['contents']
            
            if cache_scenario_active_cache_name: # Cache Hit
                self.assertEqual(gen_config.cached_content, cache_scenario_active_cache_name)
                self.assertNotIn(REPORT_STRUCTURE_PROMPT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                self.assertNotIn(PREDEFINED_STYLE_REFERENCE_TEXT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                self.assertNotIn(SYSTEM_INSTRUCTION, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                self.assertTrue(any("precedentemente cachate" in str(p) for p in prompt_parts if isinstance(p, str)))
            else: # Cache Miss
                self.assertIsNone(getattr(gen_config, 'cached_content', None))
                self.assertIn(REPORT_STRUCTURE_PROMPT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                self.assertIn(PREDEFINED_STYLE_REFERENCE_TEXT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                self.assertIn(SYSTEM_INSTRUCTION, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                self.assertTrue(any("fornite all'inizio di questo prompt" in str(p) for p in prompt_parts if isinstance(p, str)))

            self.assertIn(additional_text, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
            self.assertIn(mock_uploaded_file_pdf, prompt_parts)
            self.assertIn(mock_uploaded_file_image, prompt_parts)
                
            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_any_call(name='files/pdf_file_id')
            mock_client_instance.files.delete.assert_any_call(name='files/image_file_id')

            # Reset mocks for next iteration of the loop
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.files.upload.reset_mock(side_effect=True) # reset call count and side_effect
            mock_client_instance.models.generate_content.reset_mock()
            mock_client_instance.files.delete.reset_mock()

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_generate_report_from_content_with_text_only(self, mock_gemini_client_constructor, mock_get_cache):
        """Test report generation with only text files for cache hit and miss."""
        processed_files = [
            {'type': 'text', 'content': 'DOCX content', 'filename': 'document.docx'},
            {'type': 'text', 'content': 'TXT content', 'filename': 'notes.txt'}
        ]
        additional_text = "--- INIZIO CONTENUTO DA FILE: document.docx ---\\nDOCX content\\n--- FINE CONTENUTO DA FILE: document.docx ---\\n\\n--- INIZIO CONTENUTO DA FILE: notes.txt ---\\nTXT content\\n--- FINE CONTENUTO DA FILE: notes.txt ---\\n\\n"
        expected_report_content = "Generated report from text only"

        for cache_scenario_active_cache_name in ["mocked_cache_name_text", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name

            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_response = Mock()
            mock_response.text = expected_report_content
            mock_response.candidates = []
            mock_response.prompt_feedback = None
            mock_client_instance.models.generate_content.return_value = mock_response
            
            # Act
            result = generate_report_from_content(processed_files, additional_text) # Pass additional_text which is now auto-constructed
                
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            mock_client_instance.models.generate_content.assert_called_once()
            
            call_args = mock_client_instance.models.generate_content.call_args
            gen_config = call_args.kwargs['config']
            prompt_parts = call_args.kwargs['contents']
                
            mock_client_instance.files.upload.assert_not_called()

            if cache_scenario_active_cache_name: # Cache Hit
                self.assertEqual(gen_config.cached_content, cache_scenario_active_cache_name)
                self.assertNotIn(REPORT_STRUCTURE_PROMPT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                # ... other base prompt checks
            else: # Cache Miss
                self.assertIsNone(getattr(gen_config, 'cached_content', None))
                self.assertIn(REPORT_STRUCTURE_PROMPT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                # ... other base prompt checks

            self.assertIn(additional_text, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
            self.assertFalse(any(isinstance(part, types.File) for part in prompt_parts))
                
            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_not_called()

            # Reset mocks for next iteration
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.models.generate_content.reset_mock()

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_generate_report_from_content_mixed_files(self, mock_gemini_client_constructor, mock_get_cache):
        """Test report generation with mixed file types for cache hit and miss."""
        processed_files = [
            {'type': 'vision', 'path': '/tmp/damage_photo.jpg', 'mime_type': 'image/jpeg', 'filename': 'damage_photo.jpg'},
            {'type': 'text', 'content': 'Policy details from spreadsheet', 'filename': 'policy.xlsx'},
            {'type': 'error', 'filename': 'corrupted.pdf', 'message': 'File could not be processed'}
        ]
        additional_text = "--- INIZIO CONTENUTO DA FILE: policy.xlsx ---\\nPolicy details from spreadsheet\\n--- FINE CONTENUTO DA FILE: policy.xlsx ---\\n\\n" # Auto-generated
        expected_report_content = "Generated report with mixed content"

        for cache_scenario_active_cache_name in ["mocked_cache_name_mixed", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name

            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_uploaded_file_jpg = Mock(spec=types.File)
            mock_uploaded_file_jpg.name = 'files/jpg_file_id'
            mock_client_instance.files.upload.return_value = mock_uploaded_file_jpg

            mock_response = Mock()
            mock_response.text = expected_report_content
            mock_response.candidates = []
            mock_response.prompt_feedback = None
            mock_client_instance.models.generate_content.return_value = mock_response
            
            # Act
            result = generate_report_from_content(processed_files, additional_text) # Pass auto-generated additional_text
                
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            mock_client_instance.files.upload.assert_called_once_with(
                file='/tmp/damage_photo.jpg', 
                config=ANY
            )
            mock_client_instance.models.generate_content.assert_called_once()
            
            call_args = mock_client_instance.models.generate_content.call_args
            gen_config = call_args.kwargs['config']
            prompt_parts = call_args.kwargs['contents']

            if cache_scenario_active_cache_name: # Cache Hit
                self.assertEqual(gen_config.cached_content, cache_scenario_active_cache_name)
            else: # Cache Miss
                self.assertIsNone(getattr(gen_config, 'cached_content', None))

            self.assertIn(additional_text, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
            self.assertIn(mock_uploaded_file_jpg, prompt_parts)
            self.assertTrue(any("corrupted.pdf" in str(part) for part in prompt_parts if isinstance(part, str)))

            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_called_once_with(name='files/jpg_file_id')
            
            # Reset mocks
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.files.upload.reset_mock(return_value=True) # Reset return_value as well if it was set
            mock_client_instance.models.generate_content.reset_mock()
            mock_client_instance.files.delete.reset_mock()
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_generate_report_from_content_empty_files(self, mock_gemini_client_constructor, mock_get_cache):
        """Test report generation with empty file list for cache hit and miss."""
        processed_files = []
        additional_text = ""
        expected_report_content = "Generated report with no files"

        for cache_scenario_active_cache_name in ["mocked_cache_name_empty", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name
            
            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_response = Mock()
            mock_response.text = expected_report_content
            mock_response.candidates = []
            mock_response.prompt_feedback = None
            mock_client_instance.models.generate_content.return_value = mock_response
            
            # Act
            result = generate_report_from_content(processed_files, additional_text)
                
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            mock_client_instance.models.generate_content.assert_called_once()
            mock_client_instance.files.upload.assert_not_called()
            
            call_args = mock_client_instance.models.generate_content.call_args
            gen_config = call_args.kwargs['config']
            prompt_parts = call_args.kwargs['contents']
                
            if cache_scenario_active_cache_name: # Cache Hit
                self.assertEqual(gen_config.cached_content, cache_scenario_active_cache_name)
                self.assertNotIn(REPORT_STRUCTURE_PROMPT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
            else: # Cache Miss
                self.assertIsNone(getattr(gen_config, 'cached_content', None))
                self.assertIn(REPORT_STRUCTURE_PROMPT, "".join(str(p) for p in prompt_parts if isinstance(p, str)))
                
            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_not_called()

            # Reset mocks
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.models.generate_content.reset_mock()


class TestGeminiAPIIntegration(unittest.TestCase):
    """Test Google Gemini API integration and error handling."""
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_call_gemini_api_success(self, mock_gemini_client_constructor, mock_get_cache):
        """Test successful Gemini API call for cache hit and miss."""
        processed_files = [{'type': 'text', 'content': 'User content', 'filename': 'test.txt'}]
        additional_text = "--- INIZIO CONTENUTO DA FILE: test.txt ---\\nUser content\\n--- FINE CONTENUTO DA FILE: test.txt ---\\n\\n" # Auto-generated
        expected_report_content = "Generated report content"

        for cache_scenario_active_cache_name in ["mocked_cache_api_success", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name
            
            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance
            
            mock_response = Mock()
            mock_response.text = expected_report_content
            mock_response.candidates = []
            mock_response.prompt_feedback = None
            mock_client_instance.models.generate_content.return_value = mock_response
            
            # Act
            result = generate_report_from_content(processed_files, additional_text) # Pass auto-generated text
            
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            mock_client_instance.models.generate_content.assert_called_once()
            self.assertEqual(result, expected_report_content)

            # Reset mocks
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.models.generate_content.reset_mock()

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_call_gemini_api_with_vision_content(self, mock_gemini_client_constructor, mock_get_cache):
        """Test Gemini API call with vision content for cache hit and miss."""
        processed_files = [{'type': 'vision', 'path': '/tmp/fake_image.jpg', 'mime_type': 'image/jpeg', 'filename': 'fake_image.jpg'}]
        additional_text = "Analyze this image" # User provided, not from file
        expected_report_content = "Report based on visual content"

        for cache_scenario_active_cache_name in ["mocked_cache_vision_api", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name

            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_uploaded_file = Mock(spec=types.File)
            mock_uploaded_file.name = "files/fake_id"
            mock_client_instance.files.upload.return_value = mock_uploaded_file
            
            mock_response = Mock()
            mock_response.text = expected_report_content
            mock_response.candidates = []
            mock_response.prompt_feedback = None
            mock_client_instance.models.generate_content.return_value = mock_response
            
            # Act
            result = generate_report_from_content(processed_files, additional_text)
            
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            mock_client_instance.files.upload.assert_called_once()
            mock_client_instance.models.generate_content.assert_called_once()
            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_called_once_with(name="files/fake_id")

            # Reset mocks
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.files.upload.reset_mock(return_value=True)
            mock_client_instance.models.generate_content.reset_mock()
            mock_client_instance.files.delete.reset_mock()

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_call_gemini_api_error_handling(self, mock_gemini_client_constructor, mock_get_cache):
        """Test error handling in Gemini API calls for cache hit and miss."""
        processed_files = [{'type': 'text', 'content': 'Test prompt', 'filename': 'test.txt'}]
        additional_text = "--- INIZIO CONTENUTO DA FILE: test.txt ---\\nTest prompt\\n--- FINE CONTENUTO DA FILE: test.txt ---\\n\\n" # Auto-generated

        for cache_scenario_active_cache_name in ["mocked_cache_api_error", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name
            
            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance
            
            mock_client_instance.models.generate_content.side_effect = Exception("API call failed")
            
            # Act
            result = generate_report_from_content(processed_files, additional_text) # Pass auto-generated text
            
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            mock_client_instance.models.generate_content.assert_called_once()
            self.assertTrue(result.startswith("Error generating report due to an unexpected LLM issue:"))
            self.assertIn("API call failed", result)

            # Reset mocks
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.models.generate_content.reset_mock(side_effect=True)
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_generate_report_api_error_propagation(self, mock_gemini_client_constructor, mock_get_cache):
        """Test that API errors are properly propagated for cache hit and miss."""
        processed_files = [{'type': 'text', 'content': 'Test content', 'filename': 'test.txt'}]
        additional_text = "--- INIZIO CONTENUTO DA FILE: test.txt ---\\nTest content\\n--- FINE CONTENUTO DA FILE: test.txt ---\\n\\n" # Auto-generated

        for cache_scenario_active_cache_name in ["mocked_cache_prop_error", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name
            
            # Arrange
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance
            
            mock_client_instance.models.generate_content.side_effect = Exception("Rate limit exceeded")
            
            # Act
            result = generate_report_from_content(processed_files, additional_text) # Pass auto-generated text
                
            # Assert
            mock_gemini_client_constructor.assert_called_with(api_key=settings.GEMINI_API_KEY)
            mock_client_instance.models.generate_content.assert_called_once()
            self.assertTrue(result.startswith("Error generating report due to an unexpected LLM issue:"))
            self.assertIn("Rate limit exceeded", result)

            # Reset mocks
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.models.generate_content.reset_mock(side_effect=True)


class TestPromptConstruction(unittest.TestCase):
    """Test the construction of prompts with different content types, considering cache."""
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_prompt_includes_base_prompts_on_cache_miss(self, mock_gemini_client_constructor, mock_get_cache):
        """Test that base prompts are included on cache miss."""
        mock_get_cache.return_value = None # Cache Miss
        
        mock_client_instance = Mock()
        mock_gemini_client_constructor.return_value = mock_client_instance
        mock_response = Mock(text="Test response", candidates=[], prompt_feedback=None)
        mock_client_instance.models.generate_content.return_value = mock_response
        
        generate_report_from_content([], "")
            
        mock_client_instance.models.generate_content.assert_called_once()
        call_args = mock_client_instance.models.generate_content.call_args
        prompt_parts_str = "".join(str(p) for p in call_args.kwargs['contents'] if isinstance(p, str))
            
        self.assertIn(REPORT_STRUCTURE_PROMPT, prompt_parts_str)
        self.assertIn(PREDEFINED_STYLE_REFERENCE_TEXT, prompt_parts_str)
        self.assertIn(SYSTEM_INSTRUCTION, prompt_parts_str)
        self.assertIn("fornite all'inizio di questo prompt", prompt_parts_str)
        self.assertIsNone(getattr(call_args.kwargs['config'], 'cached_content', None))

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_prompt_uses_cache_on_hit(self, mock_gemini_client_constructor, mock_get_cache):
        """Test that base prompts are NOT in content and cache is used on cache hit."""
        mock_get_cache.return_value = "mocked_cache_for_prompt_test" # Cache Hit
        
        mock_client_instance = Mock()
        mock_gemini_client_constructor.return_value = mock_client_instance
        mock_response = Mock(text="Test response", candidates=[], prompt_feedback=None)
        mock_client_instance.models.generate_content.return_value = mock_response
        
        generate_report_from_content([], "")
            
        mock_client_instance.models.generate_content.assert_called_once()
        call_args = mock_client_instance.models.generate_content.call_args
        prompt_parts_str = "".join(str(p) for p in call_args.kwargs['contents'] if isinstance(p, str))

        self.assertNotIn(REPORT_STRUCTURE_PROMPT, prompt_parts_str)
        self.assertNotIn(PREDEFINED_STYLE_REFERENCE_TEXT, prompt_parts_str)
        self.assertNotIn(SYSTEM_INSTRUCTION, prompt_parts_str) # System instruction is in cache
        self.assertIn("precedentemente cachate", prompt_parts_str)
        self.assertEqual(call_args.kwargs['config'].cached_content, "mocked_cache_for_prompt_test")

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_prompt_includes_additional_text_when_provided(self, mock_gemini_client_constructor, mock_get_cache):
        """Test that additional text is included in prompts, regardless of cache state."""
        additional_text = "This is important extracted text from documents"

        for cache_scenario_active_cache_name in ["mocked_cache_add_text", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name

            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance
            mock_response = Mock(text="Test response", candidates=[], prompt_feedback=None)
            mock_client_instance.models.generate_content.return_value = mock_response
            
            generate_report_from_content([], additional_text) # User-provided additional text
                
            mock_client_instance.models.generate_content.assert_called_once()
            call_args = mock_client_instance.models.generate_content.call_args
            prompt_parts_str = "".join(str(p) for p in call_args.kwargs['contents'] if isinstance(p, str))
                
            self.assertIn(f"--- INIZIO TESTO AGGIUNTIVO FORNITO ---\n{additional_text}\n--- FINE TESTO AGGIUNTIVO FORNITO ---\n", prompt_parts_str)
            
            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.models.generate_content.reset_mock()

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_prompt_excludes_empty_additional_text(self, mock_gemini_client_constructor, mock_get_cache):
        """Test that empty additional text is handled properly."""
        additional_text = "" # Empty user-provided text
        
        # Only need to test one cache scenario as additional_text logic is independent
        mock_get_cache.return_value = None 
        
        mock_client_instance = Mock()
        mock_gemini_client_constructor.return_value = mock_client_instance
        mock_response = Mock(text="Test response", candidates=[], prompt_feedback=None)
        mock_client_instance.models.generate_content.return_value = mock_response
        
        generate_report_from_content([], additional_text)
            
        mock_client_instance.models.generate_content.assert_called_once()
        call_args = mock_client_instance.models.generate_content.call_args
        prompt_parts_str = "".join(str(p) for p in call_args.kwargs['contents'] if isinstance(p, str))
        self.assertNotIn("--- INIZIO TESTO AGGIUNTIVO FORNITO ---", prompt_parts_str)


class TestVisionFileHandling(unittest.TestCase):
    """Test handling of vision files (PDFs and images) in prompts."""
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    @patch('builtins.open', create=True) # Mock open for file reading if any, though upload handles it
    def test_vision_file_upload_and_inclusion(self, mock_open, mock_gemini_client_constructor, mock_get_cache):
        """Test that vision files are properly uploaded and included."""
        processed_files = [{'type': 'vision', 'path': '/tmp/test.pdf', 'mime_type': 'application/pdf', 'filename': 'test.pdf'}]
        expected_report_content = "Report with vision content"

        for cache_scenario_active_cache_name in ["mock_cache_vision_file", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name

            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_uploaded_file = Mock(spec=types.File)
            mock_uploaded_file.name = "files/fake_pdf_id"
            mock_client_instance.files.upload.return_value = mock_uploaded_file

            mock_response = Mock(text=expected_report_content, candidates=[], prompt_feedback=None)
            mock_client_instance.models.generate_content.return_value = mock_response
            
            result = generate_report_from_content(processed_files, "")
                
            mock_client_instance.files.upload.assert_called_once_with(
                file='/tmp/test.pdf', 
                config=ANY
            )
            # Check config obj values
            upload_call_args = mock_client_instance.files.upload.call_args
            upload_config_arg = upload_call_args.kwargs['config']
            self.assertEqual(upload_config_arg.mime_type, 'application/pdf')
            self.assertEqual(upload_config_arg.display_name, 'test.pdf')


            mock_client_instance.models.generate_content.assert_called_once()
            call_args = mock_client_instance.models.generate_content.call_args
            self.assertIn(mock_uploaded_file, call_args.kwargs['contents'])
            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_called_once_with(name="files/fake_pdf_id")

            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.files.upload.reset_mock(return_value=True)
            mock_client_instance.models.generate_content.reset_mock()
            mock_client_instance.files.delete.reset_mock()

    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_multiple_vision_files(self, mock_gemini_client_constructor, mock_get_cache):
        """Test handling of multiple vision files in a single request."""
        processed_files = [
            {'type': 'vision', 'path': '/tmp/document.pdf', 'mime_type': 'application/pdf', 'filename': 'document.pdf'},
            {'type': 'vision', 'path': '/tmp/photo1.jpg', 'mime_type': 'image/jpeg', 'filename': 'photo1.jpg'},
            {'type': 'vision', 'path': '/tmp/photo2.png', 'mime_type': 'image/png', 'filename': 'photo2.png'}
        ]
        expected_report_content = "Report analyzing multiple visual documents"

        for cache_scenario_active_cache_name in ["mock_cache_multi_vision", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name

            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_uploaded_pdf = Mock(spec=types.File)
            mock_uploaded_pdf.name = "files/pdf_id"
            mock_uploaded_jpg = Mock(spec=types.File)
            mock_uploaded_jpg.name = "files/jpg_id"
            mock_uploaded_png = Mock(spec=types.File)
            mock_uploaded_png.name = "files/png_id"
            
            mock_client_instance.files.upload.side_effect = [mock_uploaded_pdf, mock_uploaded_jpg, mock_uploaded_png]

            mock_response = Mock(text=expected_report_content, candidates=[], prompt_feedback=None)
            mock_client_instance.models.generate_content.return_value = mock_response
            
            result = generate_report_from_content(processed_files, "")
                
            self.assertEqual(mock_client_instance.files.upload.call_count, 3)
            mock_client_instance.models.generate_content.assert_called_once()
            
            call_args = mock_client_instance.models.generate_content.call_args
            prompt_parts = call_args.kwargs['contents']
            
            self.assertIn(mock_uploaded_pdf, prompt_parts)
            self.assertIn(mock_uploaded_jpg, prompt_parts)
            self.assertIn(mock_uploaded_png, prompt_parts)
            
            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_any_call(name="files/pdf_id")
            mock_client_instance.files.delete.assert_any_call(name="files/jpg_id")
            mock_client_instance.files.delete.assert_any_call(name="files/png_id")
            self.assertEqual(mock_client_instance.files.delete.call_count, 3)

            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.files.upload.reset_mock(side_effect=True)
            mock_client_instance.models.generate_content.reset_mock()
            mock_client_instance.files.delete.reset_mock()


class TestErrorFileHandling(unittest.TestCase):
    """Test handling of files that had processing errors."""
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_error_files_are_mentioned_in_prompt(self, mock_gemini_client_constructor, mock_get_cache):
        """Test that files with processing errors are mentioned in prompt."""
        processed_files = [
            {'type': 'vision', 'path': '/tmp/good.pdf', 'mime_type': 'application/pdf', 'filename': 'good.pdf'},
            {'type': 'error', 'filename': 'corrupted.pdf', 'message': 'File could not be processed'},
            {'type': 'text', 'content': 'Valid text content', 'filename': 'valid.txt'}
        ]
        additional_text = "--- INIZIO CONTENUTO DA FILE: valid.txt ---\\nValid text content\\n--- FINE CONTENUTO DA FILE: valid.txt ---\\n\\n" # auto
        expected_report_content = "Report with valid files only"

        for cache_scenario_active_cache_name in ["mock_cache_error_file", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name

            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance

            mock_uploaded_good_pdf = Mock(spec=types.File)
            mock_uploaded_good_pdf.name = "files/good_pdf_id"
            mock_client_instance.files.upload.return_value = mock_uploaded_good_pdf
            
            mock_response = Mock(text=expected_report_content, candidates=[], prompt_feedback=None)
            mock_client_instance.models.generate_content.return_value = mock_response
            
            result = generate_report_from_content(processed_files, additional_text) # Pass auto-generated
                
            mock_client_instance.files.upload.assert_called_once_with(file='/tmp/good.pdf', config=ANY)
            mock_client_instance.models.generate_content.assert_called_once()
            
            call_args = mock_client_instance.models.generate_content.call_args
            prompt_parts = call_args.kwargs['contents']
            prompt_parts_str = "".join(str(p) for p in prompt_parts if isinstance(p, str))

            self.assertIn(mock_uploaded_good_pdf, prompt_parts)
            self.assertIn("[AVVISO: Problema durante l'elaborazione del file corrupted.pdf: File could not be processed]", prompt_parts_str)
            self.assertIn("Valid text content", prompt_parts_str) # From additional_text

            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_called_once_with(name="files/good_pdf_id")

            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.files.upload.reset_mock(return_value=True)
            mock_client_instance.models.generate_content.reset_mock()
            mock_client_instance.files.delete.reset_mock()
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.genai.Client')
    def test_all_error_files_still_generates_report(self, mock_gemini_client_constructor, mock_get_cache):
        """Test that report generation continues even if all files had errors."""
        processed_files = [
            {'type': 'error', 'filename': 'corrupted1.pdf', 'message': 'File could not be processed'},
            {'type': 'error', 'filename': 'corrupted2.jpg', 'message': 'Invalid image format'}
        ]
        expected_report_content = "Report generated despite file errors"

        for cache_scenario_active_cache_name in ["mock_cache_all_error", None]:
            mock_get_cache.return_value = cache_scenario_active_cache_name
            
            mock_client_instance = Mock()
            mock_gemini_client_constructor.return_value = mock_client_instance
            
            mock_response = Mock(text=expected_report_content, candidates=[], prompt_feedback=None)
            mock_client_instance.models.generate_content.return_value = mock_response
            
            result = generate_report_from_content(processed_files, "")
                
            mock_client_instance.files.upload.assert_not_called() 
            mock_client_instance.models.generate_content.assert_called_once()
            
            call_args = mock_client_instance.models.generate_content.call_args
            prompt_parts_str = "".join(str(p) for p in call_args.kwargs['contents'] if isinstance(p, str))
            self.assertIn("corrupted1.pdf", prompt_parts_str)
            self.assertIn("corrupted2.jpg", prompt_parts_str)
            
            self.assertEqual(result, expected_report_content)
            mock_client_instance.files.delete.assert_not_called()

            mock_gemini_client_constructor.reset_mock()
            mock_client_instance.models.generate_content.reset_mock()


class TestConfigurationUsage(unittest.TestCase):
    """Test that LLM handler uses configuration settings properly."""
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.settings') # Mock settings module directly used in generate_report_from_content
    @patch('llm_handler.genai.Client')
    def test_uses_configured_model_name(self, mock_gemini_client_constructor, mock_settings_module, mock_get_cache):
        """Test that the configured model name is used."""
        # Test with cache miss to see model name in generate_content call directly
        mock_get_cache.return_value = None 

        mock_client_instance = Mock()
        mock_gemini_client_constructor.return_value = mock_client_instance
        
        mock_settings_module.GEMINI_API_KEY = "test_api_key"
        mock_settings_module.LLM_MODEL_NAME = "custom-test-model-v1"
        # These need to be present for GenerateContentConfig
        mock_settings_module.LLM_TEMPERATURE = 0.75 
        mock_settings_module.LLM_MAX_TOKENS = 2048
        
        mock_response = Mock(text="Test response", candidates=[], prompt_feedback=None)
        mock_client_instance.models.generate_content.return_value = mock_response
            
        generate_report_from_content([], "")
            
        mock_gemini_client_constructor.assert_called_once_with(api_key="test_api_key")
        mock_client_instance.models.generate_content.assert_called_once()
        call_args = mock_client_instance.models.generate_content.call_args
        self.assertEqual(call_args.kwargs['model'], "custom-test-model-v1")
    
    @patch('llm_handler._get_or_create_prompt_cache')
    @patch('llm_handler.settings') # Mock settings module
    @patch('llm_handler.genai.Client')
    def test_uses_configured_temperature_and_tokens(self, mock_gemini_client_constructor, mock_settings_module, mock_get_cache):
        """Test that configured temperature and max tokens are used."""
        mock_get_cache.return_value = None # Irrelevant for this, but needs a value

        mock_client_instance = Mock()
        mock_gemini_client_constructor.return_value = mock_client_instance

        mock_settings_module.GEMINI_API_KEY = "test_api_key"
        mock_settings_module.LLM_MODEL_NAME = "gemini-pro" 
        mock_settings_module.LLM_TEMPERATURE = 0.33
        mock_settings_module.LLM_MAX_TOKENS = 5555
        
        mock_response = Mock(text="Test response", candidates=[], prompt_feedback=None)
        mock_client_instance.models.generate_content.return_value = mock_response
            
        generate_report_from_content([], "")
            
        mock_gemini_client_constructor.assert_called_once_with(api_key="test_api_key")
        mock_client_instance.models.generate_content.assert_called_once()
        call_args = mock_client_instance.models.generate_content.call_args
        gen_config = call_args.kwargs['config']
        self.assertEqual(gen_config.temperature, 0.33)
        self.assertEqual(gen_config.max_output_tokens, 5555)

# Note: To run these tests, ensure unittest is used as the test runner.
# Example: python -m unittest tests/unit/test_llm_handler.py 