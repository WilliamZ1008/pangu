"""
Service package exports.

Keep package initialization lightweight so offline experiment modules such as
`services.model_clients` and `services.result_store` do not require optional
database dependencies at import time.
"""

__all__ = ["UserProfileService", "SessionManager"]


def __getattr__(name):
    if name == "UserProfileService":
        from services.user_profile import UserProfileService

        return UserProfileService
    if name == "SessionManager":
        from services.session_manager import SessionManager

        return SessionManager
    raise AttributeError(f"module 'services' has no attribute {name!r}")
