"""AYUR-INTEL — PlantNet Identification Service Unit Tests.

Unit tests for backend PlantNet service, response normalization, input validation,
error handling, and FastAPI endpoint response contracts.
"""

from __future__ import annotations

import io
import unittest
from unittest.mock import MagicMock, patch

from httpx import ASGITransport, Client

from api.main import app
from api.services.plantnet_service import (
    PlantNetAuthError,
    PlantNetConfigurationError,
    PlantNetError,
    PlantNetParseError,
    PlantNetProviderError,
    PlantNetRateLimitError,
    PlantNetTimeoutError,
    PlantNetValidationError,
    _get_confidence_label,
    identify_plant_with_plantnet,
    normalize_plantnet_response,
    validate_plant_image,
)

# Valid 1x1 JPEG magic bytes sample
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
# Valid PNG magic bytes sample
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"


class TestPlantNetService(unittest.TestCase):
    """Test suite for PlantNet service logic and endpoints."""

    def setUp(self):
        self.client = Client(transport=ASGITransport(app=app), base_url="http://test")

    # -----------------------------------------------------------------------
    # 1. Validation Tests
    # -----------------------------------------------------------------------

    def test_validate_valid_jpeg(self):
        validate_plant_image(VALID_JPEG_BYTES, content_type="image/jpeg", filename="test.jpg")

    def test_validate_valid_png(self):
        validate_plant_image(VALID_PNG_BYTES, content_type="image/png", filename="test.png")

    def test_validate_empty_file(self):
        with self.assertRaises(PlantNetValidationError) as ctx:
            validate_plant_image(b"", content_type="image/jpeg")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_validate_file_too_large(self):
        large_bytes = VALID_JPEG_BYTES + (b"\x00" * (10 * 1024 * 1024 + 1))
        with self.assertRaises(PlantNetValidationError) as ctx:
            validate_plant_image(large_bytes, content_type="image/jpeg")
        self.assertIn("maximum limit", str(ctx.exception).lower())

    def test_validate_unsupported_mime(self):
        with self.assertRaises(PlantNetValidationError) as ctx:
            validate_plant_image(VALID_JPEG_BYTES, content_type="image/gif")
        self.assertIn("jpg or png", str(ctx.exception).lower())

    def test_validate_bad_header_bytes(self):
        bad_bytes = b"NOT_A_JPEG_OR_PNG_HEADER_DATA"
        with self.assertRaises(PlantNetValidationError) as ctx:
            validate_plant_image(bad_bytes, content_type="image/jpeg")
        self.assertIn("corrupted or invalid", str(ctx.exception).lower())

    # -----------------------------------------------------------------------
    # 2. Confidence Label Tests
    # -----------------------------------------------------------------------

    def test_confidence_labels(self):
        self.assertEqual(_get_confidence_label(85.0), "High confidence")
        self.assertEqual(_get_confidence_label(80.0), "High confidence")
        self.assertEqual(_get_confidence_label(79.9), "Likely match")
        self.assertEqual(_get_confidence_label(55.0), "Likely match")
        self.assertEqual(_get_confidence_label(54.9), "Low confidence")
        self.assertEqual(_get_confidence_label(12.5), "Low confidence")

    # -----------------------------------------------------------------------
    # 3. Response Normalization Tests
    # -----------------------------------------------------------------------

    def test_normalize_valid_response(self):
        raw_response = {
            "query": {"organs": ["leaf"], "project": "all"},
            "results": [
                {
                    "score": 0.84751,
                    "species": {
                        "scientificNameWithoutAuthor": "Azadirachta indica",
                        "scientificName": "Azadirachta indica A.Juss.",
                        "commonNames": ["Neem", "Neem Tree", "Indian lilac"],
                        "family": {"scientificNameWithoutAuthor": "Meliaceae"},
                        "genus": {"scientificNameWithoutAuthor": "Azadirachta"},
                    },
                    "gbif": {"id": "3190474"},
                    "powo": {"id": "urn:lsid:ipni.org:names:576629-1"},
                    "iucn": {"id": "61794204", "category": "LC"},
                },
                {
                    "score": 0.1234,
                    "species": {
                        "scientificNameWithoutAuthor": "Melia azedarach",
                        "commonNames": ["Chinaberry"],
                        "family": {"scientificNameWithoutAuthor": "Meliaceae"},
                    },
                },
                {
                    "score": 0.05,
                    "species": {
                        "scientificNameWithoutAuthor": "Murraya koenigii",
                        "commonNames": ["Curry leaf"],
                        "family": {"scientificNameWithoutAuthor": "Rutaceae"},
                    },
                },
                {
                    "score": 0.02,
                    "species": {
                        "scientificNameWithoutAuthor": "Swietenia mahagoni",
                        "commonNames": ["Mahogany"],
                        "family": {"scientificNameWithoutAuthor": "Meliaceae"},
                    },
                },
                {
                    "score": 0.01,
                    "species": {
                        "scientificNameWithoutAuthor": "Extra candidate",
                        "commonNames": ["Extra"],
                    },
                },
            ],
        }

        normalized = normalize_plantnet_response(raw_response, default_organ="leaf")

        self.assertTrue(normalized["success"])
        self.assertEqual(normalized["provider"], "PlantNet")

        bm = normalized["best_match"]
        self.assertEqual(bm["scientific_name"], "Azadirachta indica")
        self.assertEqual(bm["scientific_name_full"], "Azadirachta indica A.Juss.")
        self.assertIn("Neem", bm["common_names"])
        self.assertEqual(bm["family"], "Meliaceae")
        self.assertEqual(bm["genus"], "Azadirachta")
        self.assertEqual(bm["score"], 0.84751)
        self.assertEqual(bm["confidence_percent"], 84.75)
        self.assertEqual(bm["confidence_label"], "High confidence")
        self.assertEqual(bm["gbif_id"], "3190474")
        self.assertEqual(bm["powo_id"], "urn:lsid:ipni.org:names:576629-1")
        self.assertEqual(bm["iucn_id"], "61794204")
        self.assertEqual(bm["iucn_category"], "LC")

        # Organ check
        self.assertEqual(normalized["predicted_organ"]["organ"], "leaf")

        # Alternatives check: max 3 (out of 4 remaining candidates)
        self.assertEqual(len(normalized["alternatives"]), 3)
        self.assertEqual(normalized["alternatives"][0]["scientific_name"], "Melia azedarach")
        self.assertEqual(normalized["alternatives"][0]["confidence_percent"], 12.34)

    def test_normalize_empty_results(self):
        raw_response = {"results": []}
        normalized = normalize_plantnet_response(raw_response, default_organ="leaf")

        self.assertFalse(normalized["success"])
        self.assertIsNone(normalized["best_match"])
        self.assertIn("couldn't identify", normalized["message"])

    def test_normalize_malformed_response(self):
        with self.assertRaises(PlantNetParseError):
            normalize_plantnet_response("NOT_A_DICT")

    # -----------------------------------------------------------------------
    # 4. API Error Handling Tests
    # -----------------------------------------------------------------------

    @patch("api.services.plantnet_service.settings")
    def test_missing_api_key(self, mock_settings):
        mock_settings.effective_plantnet_api_key = ""
        with self.assertRaises(PlantNetConfigurationError):
            identify_plant_with_plantnet(VALID_JPEG_BYTES, content_type="image/jpeg")

    @patch("api.services.plantnet_service.requests.post")
    @patch("api.services.plantnet_service.settings")
    def test_timeout_error(self, mock_settings, mock_post):
        mock_settings.effective_plantnet_api_key = "test_key"
        mock_settings.AYURINTEL_PLANTNET_PROJECT = "all"
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        with self.assertRaises(PlantNetTimeoutError):
            identify_plant_with_plantnet(VALID_JPEG_BYTES, content_type="image/jpeg")

    @patch("api.services.plantnet_service.requests.post")
    @patch("api.services.plantnet_service.settings")
    def test_auth_401_error(self, mock_settings, mock_post):
        mock_settings.effective_plantnet_api_key = "bad_key"
        mock_settings.AYURINTEL_PLANTNET_PROJECT = "all"
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_post.return_value = mock_resp

        with self.assertRaises(PlantNetAuthError):
            identify_plant_with_plantnet(VALID_JPEG_BYTES, content_type="image/jpeg")

    @patch("api.services.plantnet_service.requests.post")
    @patch("api.services.plantnet_service.settings")
    def test_rate_limit_429_error(self, mock_settings, mock_post):
        mock_settings.effective_plantnet_api_key = "test_key"
        mock_settings.AYURINTEL_PLANTNET_PROJECT = "all"
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_post.return_value = mock_resp

        with self.assertRaises(PlantNetRateLimitError):
            identify_plant_with_plantnet(VALID_JPEG_BYTES, content_type="image/jpeg")

    @patch("api.services.plantnet_service.requests.post")
    @patch("api.services.plantnet_service.settings")
    def test_provider_500_error(self, mock_settings, mock_post):
        mock_settings.effective_plantnet_api_key = "test_key"
        mock_settings.AYURINTEL_PLANTNET_PROJECT = "all"
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp

        with self.assertRaises(PlantNetProviderError):
            identify_plant_with_plantnet(VALID_JPEG_BYTES, content_type="image/jpeg")

    # -----------------------------------------------------------------------
    # 5. FastAPI Endpoint Integration Test
    # -----------------------------------------------------------------------

    @patch("api.routers.plant_discovery.identify_plant_with_plantnet")
    def test_endpoint_success(self, mock_identify):
        import asyncio
        from fastapi import UploadFile
        from api.routers.plant_discovery import identify_plant

        mock_identify.return_value = {
            "success": True,
            "best_match": {
                "scientific_name": "Azadirachta indica",
                "scientific_name_full": "Azadirachta indica A.Juss.",
                "common_names": ["Neem"],
                "family": "Meliaceae",
                "genus": "Azadirachta",
                "score": 0.85,
                "confidence_percent": 85.0,
                "confidence_label": "High confidence",
                "gbif_id": "3190474",
                "powo_id": None,
                "iucn_id": None,
                "iucn_category": None,
            },
            "predicted_organ": {"organ": "leaf", "score": 0.85},
            "alternatives": [],
            "provider": "PlantNet",
        }

        file_obj = io.BytesIO(VALID_JPEG_BYTES)
        upload_file = UploadFile(filename="test.jpg", file=file_obj, headers={"content-type": "image/jpeg"})

        response_data = asyncio.run(identify_plant(image=upload_file, organ="leaf"))

        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["best_match"]["scientific_name"], "Azadirachta indica")
        self.assertEqual(response_data["provider"], "PlantNet")


if __name__ == "__main__":
    unittest.main()
