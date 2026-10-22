import unittest
from unittest.mock import patch, MagicMock
import requests # Import requests for its exceptions

# Add project root to sys.path to allow importing 'main'
# This might be needed if running tests directly from tests/ directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import Main # Assuming main.py is in the root
from appLog import log # To ensure log object is available if main.py relies on it being configured

class TestMainConnectionCheck(unittest.TestCase):

    @patch('main.requests.get')
    def test_connection_check_success(self, mock_requests_get):
        # Configure the mock to simulate a successful request
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock() # Does nothing for success
        mock_requests_get.return_value = mock_response

        self.assertTrue(Main.ConnectionCheck())
        mock_requests_get.assert_called_once_with('https://www.whatsapp.com/', timeout=5)

    @patch('main.requests.get')
    def test_connection_check_http_error(self, mock_requests_get):
        # Configure the mock to simulate an HTTPError
        mock_response = MagicMock()
        # Ensure raise_for_status actually raises the error for the test
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Test HTTP Error")
        mock_requests_get.return_value = mock_response

        self.assertFalse(Main.ConnectionCheck())

    @patch('main.requests.get')
    def test_connection_check_connection_error(self, mock_requests_get):
        # Configure the mock to simulate a ConnectionError
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Test Connection Error")

        self.assertFalse(Main.ConnectionCheck())

    @patch('main.requests.get')
    def test_connection_check_timeout(self, mock_requests_get):
        # Configure the mock to simulate a Timeout
        mock_requests_get.side_effect = requests.exceptions.Timeout("Test Timeout")

        self.assertFalse(Main.ConnectionCheck())

    @patch('main.requests.get')
    def test_connection_check_generic_request_exception(self, mock_requests_get):
        # Configure the mock to simulate a generic RequestException
        mock_requests_get.side_effect = requests.exceptions.RequestException("Test Generic Request Error")

        self.assertFalse(Main.ConnectionCheck())

if __name__ == '__main__':
    unittest.main()
