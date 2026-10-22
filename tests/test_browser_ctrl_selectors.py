import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import sys

# Add project root to sys.path to allow importing browserCtrl
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from browserCtrl import Web, CHROME

MINIMAL_FALLBACK_SELECTORS = {
    "login_check_element": "*[data-icon=new-chat-outline]",
    "message_textbox": "//div[@title='Type a message']",
    "attach_button": "//span[@data-icon='attach-menu-plus']",
    "media_file_input": "//input[@accept='image/*,video/mp4,video/3gpp,video/quicktime']",
    "media_caption_textbox": "//div[@role='textbox'][contains(@class,'selectable-text')]",
    "navigation_link": "/html/head/a[@id='whatsappLink']"
}

EXPECTED_SELECTOR_FILE_PATH_STR_IN_LOG = os.path.join("src", "selectors.json")


class TestSelectorLoading(unittest.TestCase):

    @patch('browserCtrl.log')
    @patch('browserCtrl.open', new_callable=mock_open)
    def test_successful_selector_loading(self, mock_file_open, mock_log):
        mock_data = {
            "message_textbox": "//new/message/xpath",
            "attach_button": "//new/attach/xpath"
        }
        # Configure the mock to simulate reading valid JSON data
        mock_file_open.return_value.__enter__.return_value.read.return_value = json.dumps(mock_data)

        with patch.object(Web, '_Web__init_browser', return_value=None): # Prevent actual browser init
             web_instance = Web(browser=CHROME)

        self.assertEqual(web_instance.selectors, mock_data)

        found_log = False
        # Construct the expected path suffix carefully, considering how os.path.join works
        # If EXPECTED_SELECTOR_FILE_PATH_STR_IN_LOG is "src/selectors.json" or "src\\selectors.json"
        # and logged path is absolute like "/path/to/project/src/selectors.json"
        # then endswith should work if the suffix is constructed correctly.
        # The path logged by browserCtrl.py's __init__ is os.path.join("src", "selectors.json")
        # which is relative if CWD is project root, or absolute if used with an absolute base path.
        # The log message itself might construct an absolute path.
        # For robustness, we check if the logged message *contains* the relative path string.
        # This is safer than endswith if absolute paths are logged.

        # The log in browserCtrl.py is: log.info(f"Successfully loaded selectors from {selector_file_path}")
        # where selector_file_path = os.path.join("src", "selectors.json")
        # This means the logged path is relative to the project root.
        expected_logged_path = EXPECTED_SELECTOR_FILE_PATH_STR_IN_LOG

        for call_arg_list in mock_log.info.call_args_list:
            args, _ = call_arg_list
            if args and isinstance(args[0], str) and \
               args[0] == f"Successfully loaded selectors from {expected_logged_path}":
                found_log = True
                break
        self.assertTrue(found_log, f"Success log for selector loading not found or path mismatch. Expected path in log: {expected_logged_path}. Log calls: {mock_log.info.call_args_list}")


    @patch('browserCtrl.log')
    @patch('browserCtrl.open', side_effect=FileNotFoundError("File not found for test"))
    def test_selector_loading_file_not_found(self, mock_file_open_error, mock_log):
        with patch.object(Web, '_Web__init_browser', return_value=None):
            web_instance = Web(browser=CHROME)

        self.assertEqual(web_instance.selectors, MINIMAL_FALLBACK_SELECTORS)

        found_log = False
        expected_logged_path = EXPECTED_SELECTOR_FILE_PATH_STR_IN_LOG
        # Log message in browserCtrl: log.error(f"'{selector_file_path}' not found. Using hardcoded fallback selectors.")
        for call_arg_list in mock_log.error.call_args_list:
            args, _ = call_arg_list
            if args and isinstance(args[0], str) and \
               args[0] == f"'{expected_logged_path}' not found. Using hardcoded fallback selectors.":
                found_log = True
                break
        self.assertTrue(found_log, f"FileNotFoundError log not found or path mismatch. Expected path in log: '{expected_logged_path}'. Log calls: {mock_log.error.call_args_list}")
        mock_log.warning.assert_any_call("Using hardcoded fallback selectors due to missing selectors.json.")


    @patch('browserCtrl.log')
    @patch('browserCtrl.open', new_callable=mock_open)
    def test_selector_loading_json_decode_error(self, mock_file_open_invalid, mock_log):
        mock_file_open_invalid.return_value.__enter__.return_value.read.return_value = "this is not valid json"

        with patch.object(Web, '_Web__init_browser', return_value=None):
            web_instance = Web(browser=CHROME)

        self.assertEqual(web_instance.selectors, MINIMAL_FALLBACK_SELECTORS)

        found_log = False
        expected_logged_path = EXPECTED_SELECTOR_FILE_PATH_STR_IN_LOG
        # Log message in browserCtrl: log.error(f"Error decoding '{selector_file_path}': {e}. Using hardcoded fallback selectors.")
        # The actual error 'e' from json.JSONDecodeError is "Expecting value: line 1 column 1 (char 0)" for "this is not valid json"
        expected_json_error_message_part = "Expecting value: line 1 column 1 (char 0)"

        for call_arg_list in mock_log.error.call_args_list:
            args, _ = call_arg_list
            if args and isinstance(args[0], str) and \
               args[0].startswith(f"Error decoding '{expected_logged_path}':") and \
               expected_json_error_message_part in args[0] and \
               args[0].endswith(". Using hardcoded fallback selectors."):
                found_log = True
                break
        self.assertTrue(found_log, f"JSONDecodeError log not found or incorrect. Expected path: '{expected_logged_path}'. Expected error part: '{expected_json_error_message_part}'. Log calls: {mock_log.error.call_args_list}")
        mock_log.warning.assert_any_call("Using hardcoded fallback selectors due to JSON decode error.")


    @patch('browserCtrl.log')
    @patch('browserCtrl.open', side_effect=OSError("Some OS error for test"))
    def test_selector_loading_other_os_error(self, mock_file_open_os_error, mock_log):
        # In case of a generic Exception (like OSError here), selectors dict becomes empty
        expected_selectors_on_generic_error = {}

        with patch.object(Web, '_Web__init_browser', return_value=None):
            web_instance = Web(browser=CHROME)

        self.assertEqual(web_instance.selectors, expected_selectors_on_generic_error)

        found_log = False
        expected_logged_path = EXPECTED_SELECTOR_FILE_PATH_STR_IN_LOG
        # Log message: log.exception(f"Unexpected error loading '{selector_file_path}': {e}")
        #              log.error("Selectors could not be loaded. Operations requiring selectors will likely fail.")

        # Check for the log.exception message
        for call_arg_list in mock_log.exception.call_args_list:
            args, _ = call_arg_list
            if args and isinstance(args[0], str) and \
               args[0].startswith(f"Unexpected error loading '{expected_logged_path}':") and \
               "Some OS error for test" in args[0]: # Check if the OS error message is part of the log
                found_log = True
                break
        self.assertTrue(found_log, f"Generic OSError (exception) log not found or incorrect. Expected path: '{expected_logged_path}'. Log calls: {mock_log.exception.call_args_list}")

        # Check for the subsequent log.error message
        mock_log.error.assert_any_call("Selectors could not be loaded. Operations requiring selectors will likely fail.")

if __name__ == '__main__':
    unittest.main()
