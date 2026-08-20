from abc import ABC, abstractmethod


class ITokenService(ABC):
    @abstractmethod
    def create_access_token(self, user_id: str, email: str, role: str) -> str: ...

    @abstractmethod
    def decode_token(self, token: str) -> dict:
        """Returns the decoded payload. Raises on invalid/expired token."""
        ...