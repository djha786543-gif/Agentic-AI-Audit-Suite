import unittest

import main
from core.config import settings


class TestStartupGuardrails(unittest.TestCase):
    def setUp(self) -> None:
        self._original = {
            "ENVIRONMENT": settings.ENVIRONMENT,
            "STRICT_PRODUCTION_GUARDS": settings.STRICT_PRODUCTION_GUARDS,
            "RESET_DB_ON_STARTUP": settings.RESET_DB_ON_STARTUP,
            "CORS_ALLOWED_ORIGINS": list(settings.CORS_ALLOWED_ORIGINS),
            "TRUSTED_HOSTS": list(settings.TRUSTED_HOSTS),
            "ENABLE_HTTPS_REDIRECT": settings.ENABLE_HTTPS_REDIRECT,
            "SECRET_KEY": settings.SECRET_KEY,
        }

    def tearDown(self) -> None:
        settings.ENVIRONMENT = self._original["ENVIRONMENT"]
        settings.STRICT_PRODUCTION_GUARDS = self._original["STRICT_PRODUCTION_GUARDS"]
        settings.RESET_DB_ON_STARTUP = self._original["RESET_DB_ON_STARTUP"]
        settings.CORS_ALLOWED_ORIGINS = self._original["CORS_ALLOWED_ORIGINS"]
        settings.TRUSTED_HOSTS = self._original["TRUSTED_HOSTS"]
        settings.ENABLE_HTTPS_REDIRECT = self._original["ENABLE_HTTPS_REDIRECT"]
        settings.SECRET_KEY = self._original["SECRET_KEY"]

    def test_non_production_skips_guardrails(self) -> None:
        settings.ENVIRONMENT = "development"
        settings.RESET_DB_ON_STARTUP = True
        settings.CORS_ALLOWED_ORIGINS = ["*"]
        settings.TRUSTED_HOSTS = ["*"]

        main._enforce_production_guardrails()

    def test_production_rejects_unsafe_configuration(self) -> None:
        settings.ENVIRONMENT = "production"
        settings.STRICT_PRODUCTION_GUARDS = True
        settings.RESET_DB_ON_STARTUP = True
        settings.CORS_ALLOWED_ORIGINS = ["*"]
        settings.TRUSTED_HOSTS = ["*"]
        settings.ENABLE_HTTPS_REDIRECT = False
        settings.SECRET_KEY = "CHANGE-ME-insecure"

        with self.assertRaises(RuntimeError) as ctx:
            main._enforce_production_guardrails()
        message = str(ctx.exception)
        self.assertIn("RESET_DB_ON_STARTUP", message)
        self.assertIn("CORS_ALLOWED_ORIGINS", message)
        self.assertIn("TRUSTED_HOSTS", message)
        self.assertIn("ENABLE_HTTPS_REDIRECT", message)
        self.assertIn("SECRET_KEY", message)

    def test_production_accepts_safe_configuration(self) -> None:
        settings.ENVIRONMENT = "production"
        settings.STRICT_PRODUCTION_GUARDS = True
        settings.RESET_DB_ON_STARTUP = False
        settings.CORS_ALLOWED_ORIGINS = ["https://audit.example.com"]
        settings.TRUSTED_HOSTS = ["audit.example.com"]
        settings.ENABLE_HTTPS_REDIRECT = True
        settings.SECRET_KEY = "super-secure-and-long-secret"

        main._enforce_production_guardrails()


if __name__ == "__main__":
    unittest.main()
