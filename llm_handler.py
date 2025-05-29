import os
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions
from typing import Dict, Any, List, Union, Optional
import logging
from core.config import settings
from core.prompt_config import PREDEFINED_STYLE_REFERENCE_TEXT, REPORT_STRUCTURE_PROMPT, SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)


def _get_or_create_prompt_cache(client: genai.Client) -> Optional[str]:
    """Retries an existing prompt cache or creates a new one.

    Checks for a cache name in settings. If found, tries to retrieve it.
    If not found or invalid, creates a new cache with predefined prompts.

    Returns:
        Optional[str]: The name of the active cache, or None if an error occurs.
    """
    existing_cache_name = settings.REPORT_PROMPT_CACHE_NAME
    active_cache_name: Optional[str] = None

    if existing_cache_name:
        logger.info(f"Attempting to retrieve existing cache: {existing_cache_name}")
        try:
            # Ensure the cache name has the correct prefix for retrieval
            cache_name_for_get = existing_cache_name
            if not existing_cache_name.startswith("cachedContents/"):
                cache_name_for_get = f"cachedContents/{existing_cache_name}"
            
            cache = client.caches.get(name=cache_name_for_get)
            # Basic validation: check if it's for the same model and not expired (implicitly, get succeeds)
            if cache.model.endswith(settings.LLM_MODEL_NAME): # Model name in cache includes 'models/' prefix
                logger.info(f"Successfully retrieved and validated existing cache: {cache.name}")
                active_cache_name = cache.name
            else:
                logger.warning(
                    f"Existing cache {existing_cache_name} is for a different model ({cache.model}). \
                    Will create a new cache for {settings.LLM_MODEL_NAME}."
                )
        except google_exceptions.NotFound:
            logger.warning(f"Existing cache {existing_cache_name} not found. Will create a new one.")
        except Exception as e:
            logger.error(f"Error retrieving cache {existing_cache_name}: {e}. Will attempt to create a new one.", exc_info=True)

    if not active_cache_name:
        logger.info(f"Creating new prompt cache for model: {settings.LLM_MODEL_NAME}")
        try:
            # Define content parts with roles
            # The role for prompt-like content for the system/model to use is typically 'user'
            # or 'model' if it's meant to be a pre-fill of a model's response.
            # Given these are instructions and reference texts, 'user' seems appropriate.
            cached_content_parts = [
                types.Content(parts=[types.Part(text=PREDEFINED_STYLE_REFERENCE_TEXT)], role="user"),
                types.Content(parts=[types.Part(text=REPORT_STRUCTURE_PROMPT)], role="user"),
            ]
            
            ttl_seconds = settings.CACHE_TTL_DAYS * 24 * 60 * 60
            ttl_string = f"{ttl_seconds}s"

            # Ensure model name for cache creation is just the model ID, not prefixed with 'models/'
            # The client.caches.create expects the pure model ID like 'gemini-1.5-flash-001'
            # while cache.model from a get() call returns 'models/gemini-1.5-flash-001'.
            model_id_for_creation = settings.LLM_MODEL_NAME
            if model_id_for_creation.startswith("models/"):
                 model_id_for_creation = model_id_for_creation.split("/")[-1]


            new_cache = client.caches.create(
                model=model_id_for_creation, # Use the raw model ID here
                config={
                    'contents': cached_content_parts, # Use the Content objects with roles
                    'system_instruction': types.Content(parts=[types.Part(text=SYSTEM_INSTRUCTION)], role="system"), # System instruction should have role "system"
                    'ttl': ttl_string,
                    'display_name': settings.CACHE_DISPLAY_NAME
                }
            )
            active_cache_name = new_cache.name
            logger.info(f"Successfully created new cache: {active_cache_name} with TTL: {ttl_string}")
            
            # Prepare the cache name for logging, ensuring no "cachedContents/" prefix.
            log_cache_name = active_cache_name.replace('cachedContents/', '')
            logger.info(
                f'To reuse this cache in future runs, set the environment variable REPORT_PROMPT_CACHE_NAME="{log_cache_name}"'
            )
        except Exception as e:
            logger.error(f"Failed to create new prompt cache: {e}", exc_info=True)
            return None
    
    return active_cache_name


def generate_report_from_content(
    processed_files: List[Dict[str, Any]],
    additional_text: str = ""
) -> str:
    """Generates an insurance report using Google Gemini with multimodal content and context caching."""
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not configured in settings.")
        return "Error: LLM service is not configured (API key missing)."

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    uploaded_file_objects: List[types.File] = []
    temp_uploaded_file_names_for_api: List[str] = []
    final_prompt_parts: List[Union[str, types.Part, types.File]] = []
    active_cache_name_for_generation: Optional[str] = None

    try:
        active_cache_name_for_generation = _get_or_create_prompt_cache(client)

        if not active_cache_name_for_generation:
            logger.warning("Proceeding with report generation without prompt caching due to an issue.")
            # Fallback: Include prompts directly if caching failed
            final_prompt_parts.extend([
                PREDEFINED_STYLE_REFERENCE_TEXT,
                "\n\n",
                REPORT_STRUCTURE_PROMPT,
                "\n\n",
                SYSTEM_INSTRUCTION, # Add system instruction if not using cache where it's embedded
                "\n\n"
            ])

        for file_info in processed_files:
            if file_info.get('type') == 'vision':
                file_path = file_info.get('path')
                mime_type = file_info.get('mime_type')
                display_name = file_info.get('filename', os.path.basename(file_path) if file_path else "uploaded_file")
                if not file_path or not mime_type:
                    logger.warning(f"Skipping vision file due to missing path or mime_type: {file_info}")
                    continue
                try:
                    logger.info(f"Uploading {display_name} ({mime_type}) to Gemini File Service...")
                    # The new SDK uses client.files.upload(path=...) and path should be a string.
                    upload_config = types.UploadFileConfig(mime_type=mime_type, display_name=display_name)
                    uploaded_file = client.files.upload(file=file_path, config=upload_config) # Ensure file_path is string
                    uploaded_file_objects.append(uploaded_file)
                    temp_uploaded_file_names_for_api.append(uploaded_file.name)
                    logger.info(f"Successfully uploaded {display_name} as {uploaded_file.name}")
                except Exception as e:
                    logger.error(f"Failed to upload file {display_name} to Gemini: {e}", exc_info=True)
                    final_prompt_parts.append(f"\n\n[AVVISO: Il file {display_name} non ha potuto essere caricato per l'analisi.]\n\n")
            elif file_info.get('type') == 'text':
                filename = file_info.get('filename', 'documento testuale')
                content = file_info.get('content', '')
                if content:
                    final_prompt_parts.append(f"--- INIZIO CONTENUTO DA FILE: {filename} ---\n")
                    final_prompt_parts.append(content)
                    final_prompt_parts.append(f"\n--- FINE CONTENUTO DA FILE: {filename} ---\n\n")
            elif file_info.get('type') == 'error':
                filename = file_info.get('filename', 'file sconosciuto')
                message = file_info.get('message', 'errore generico')
                final_prompt_parts.append(f"\n\n[AVVISO: Problema durante l'elaborazione del file {filename}: {message}]\n\n")
            elif file_info.get('type') == 'unsupported':
                filename = file_info.get('filename', 'file sconosciuto')
                message = file_info.get('message', 'tipo non supportato')
                final_prompt_parts.append(f"\n\n[AVVISO: Il file {filename} è di un tipo non supportato e non può essere processato: {message}]\n\n")

        if additional_text.strip():
            final_prompt_parts.append(f"--- INIZIO TESTO AGGIUNTIVO FORNITO ---\n{additional_text}\n--- FINE TESTO AGGIUNTIVO FORNITO ---\n")

        # Add uploaded file objects (references) to the prompt parts
        # These are `types.File` objects, which the API handles as references to uploaded content.
        final_prompt_parts.extend(uploaded_file_objects)
        
        final_instruction = "\n\nAnalizza TUTTI i documenti e testi forniti (sia quelli caricati come file referenziati, sia quelli inclusi direttamente come testo) e genera il report." 
        if active_cache_name_for_generation:
            final_instruction += " Utilizza le istruzioni di stile, struttura e sistema precedentemente cachate."
        else:
            final_instruction += " Utilizza le istruzioni di stile, struttura e sistema fornite all'inizio di questo prompt."
        final_prompt_parts.append(final_instruction)

        gen_config_dict = {
            "max_output_tokens": settings.LLM_MAX_TOKENS,
            "temperature": settings.LLM_TEMPERATURE
        }
        
        safety_settings_list = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)
        ]

        generation_config_args = {
            **gen_config_dict,
            "safety_settings": safety_settings_list
        }

        if active_cache_name_for_generation:
            generation_config_args["cached_content"] = active_cache_name_for_generation
            logger.info(f"Using cached content: {active_cache_name_for_generation} for report generation.")
        
        final_config = types.GenerateContentConfig(**generation_config_args)

        logger.debug(f"Sending request to Gemini. Model: {settings.LLM_MODEL_NAME}. Using cache: {bool(active_cache_name_for_generation)}. Config: {final_config}")
        # For brevity in logs, don't log full final_prompt_parts if it's very large.
        # logger.debug(f"Prompt parts being sent: {final_prompt_parts}") 

        response = client.models.generate_content(
            model=settings.LLM_MODEL_NAME,
            contents=final_prompt_parts, 
            config=final_config
        )
        
        report_content: str = ""
        
        try:
            if response.text:
                report_content = response.text
            elif response.candidates:
                parts_text: List[str] = []
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text is not None:
                                parts_text.append(part.text)
                if parts_text:
                    report_content = "".join(parts_text)
        except AttributeError as e:
            logger.warning(f"AttributeError while accessing response text or parts: {e}. Full response: {response}")

        if not report_content:
            logger.warning(f"Gemini response did not yield usable text content. Full response: {response}")
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_obj = response.prompt_feedback.block_reason
                block_reason_name = block_reason_obj.name if hasattr(block_reason_obj, 'name') else str(block_reason_obj)
                logger.error(f"Content generation blocked. Reason from prompt_feedback: {block_reason_name}")
                return f"Error: Content generation blocked by the LLM. Reason: {block_reason_name}"
            if response.candidates:
                first_candidate = response.candidates[0]
                if first_candidate.finish_reason:
                    finish_reason_obj = first_candidate.finish_reason
                    finish_reason_name = finish_reason_obj.name if hasattr(finish_reason_obj, 'name') else str(finish_reason_obj)
                    if finish_reason_name == types.FinishReason.MAX_TOKENS.name:
                        logger.warning("Content generation stopped due to MAX_TOKENS.")
                        return "Error: Content generation reached maximum token limit. The generated text may be incomplete."
                    elif finish_reason_name != types.FinishReason.STOP.name:
                        logger.error(f"Content generation stopped for reason: {finish_reason_name}.")
                        return f"Error: LLM generation stopped for reason: {finish_reason_name}."
                    elif finish_reason_name == types.FinishReason.STOP.name and not report_content:
                         logger.warning("LLM generation finished (STOP), but no text content was extracted.")
                         return "Error: LLM generation completed, but no usable text was found in the response."
            else:
                 logger.error("No candidates found in LLM response and not blocked by prompt_feedback.")
            if not report_content:
                logger.error(f"Unknown issue: No text in Gemini response. Prompt Feedback: {response.prompt_feedback}. Candidate 0 Finish Reason (if any): {response.candidates[0].finish_reason if response.candidates else 'N/A'}")
                return "Error: Unknown issue with LLM response, no text content received."
        
        logger.info("Report content successfully generated.")
        return report_content

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Gemini API Error: {e}", exc_info=True)
        return f"Error generating report due to an LLM API issue: {str(e)}"
    except Exception as e:
        logger.error(f"An unexpected error occurred with the Gemini service: {e}", exc_info=True)
        return f"Error generating report due to an unexpected LLM issue: {str(e)}"
    finally:
        for file_api_name in temp_uploaded_file_names_for_api:
            try:
                logger.info(f"Deleting uploaded file {file_api_name} from Gemini File Service...")
                client.files.delete(name=file_api_name)
                logger.info(f"Successfully deleted {file_api_name}.")
            except Exception as e_del:
                logger.error(f"Failed to delete file {file_api_name} from Gemini: {e_del}", exc_info=True)


# Example of how you might want to initialize or check the cache at startup 
# (e.g., in your app.py or a main script)
# def ensure_prompt_cache_exists():
#     if not settings.GEMINI_API_KEY:
#         logger.warning("Cannot ensure prompt cache: GEMINI_API_KEY not set.")
#         return
#     try:
#        client = genai.Client(api_key=settings.GEMINI_API_KEY)
#        cache_name = _get_or_create_prompt_cache(client)
#        if cache_name:
#            logger.info(f"Prompt cache is active: {cache_name}")
#            # Optionally, you could try to update settings.REPORT_PROMPT_CACHE_NAME here
#            # if it was newly created and not set in .env, though that's harder to persist back to .env
#        else:
#            logger.error("Failed to ensure prompt cache is active.")
#     except Exception as e:
#        logger.error(f"Error during prompt cache initialization: {e}", exc_info=True)

# if __name__ == '__main__':
#     # This is just for testing the cache creation/retrieval logic directly
#     # In a real app, this would be part of your application's startup sequence or first request.
#     logging.basicConfig(level=logging.INFO)
#     # Ensure you have GEMINI_API_KEY in your .env or environment
#     # And optionally REPORT_PROMPT_CACHE_NAME set to an existing cache ID
#     if not settings.GEMINI_API_KEY:
#         print("Please set GEMINI_API_KEY in your .env file to test caching.")
#     else:
#         print(f"GEMINI_API_KEY found. Model for caching: {settings.LLM_MODEL_NAME}")
#         print(f"Configured CACHE_TTL_DAYS: {settings.CACHE_TTL_DAYS}")
#         print(f"Configured CACHE_DISPLAY_NAME: {settings.CACHE_DISPLAY_NAME}")
#         print(f"Current REPORT_PROMPT_CACHE_NAME from env (if any): {settings.REPORT_PROMPT_CACHE_NAME}")
        
#         test_client = genai.Client(api_key=settings.GEMINI_API_KEY)
#         active_cache = _get_or_create_prompt_cache(test_client)
#         if active_cache:
#             print(f"Test successful. Active cache name: {active_cache}")
#             print(f"Try setting REPORT_PROMPT_CACHE_NAME='{active_cache}' in your .env file for the next run.")
            
#             # Test retrieving it again to simulate next run with env var set
#             # For this test to work, you'd manually set the env var for the next line if it was just created.
#             # Or, if settings.REPORT_PROMPT_CACHE_NAME was already set and valid, this confirms retrieval.
#             # settings.REPORT_PROMPT_CACHE_NAME = active_cache # Simulate it being set for the next call
#             # print("\nAttempting to retrieve the cache again...")
#             # retrieved_again = _get_or_create_prompt_cache(test_client)
#             # if retrieved_again == active_cache:
#             #     print(f"Second retrieval successful: {retrieved_again}")
#             # else:
#             #     print(f"Second retrieval failed or got a different cache: {retrieved_again}")
#         else:
#             print("Test failed to get or create cache.") 