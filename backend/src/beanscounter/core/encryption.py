"""
Encryption utility for securing sensitive data at rest.
Uses Fernet symmetric encryption from the cryptography library.
"""

import os
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional


def get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable or generate a new one.
    
    Returns:
        Encryption key as bytes
        
    Raises:
        RuntimeError: If ENCRYPTION_KEY is not set and key file doesn't exist
    """
    key_str = os.getenv("ENCRYPTION_KEY")
    if key_str:
        # If key is provided as base64 string, use it directly
        try:
            return key_str.encode()
        except Exception:
            # If not valid base64, try to use as-is (will fail if invalid)
            return Fernet.generate_key()
    
    # Try to read from key file
    # backend/src/beanscounter/core/encryption.py -> backend/data/.encryption_key
    # Path: core -> beanscounter -> src -> backend
    backend_root = Path(__file__).parent.parent.parent.parent
    key_file = backend_root / "data" / ".encryption_key"
    if key_file.exists():
        with open(key_file, "r") as f:
            key_str = f.read().strip()
            # Key file contains base64-encoded string, convert to bytes
            return key_str.encode()
    
    raise RuntimeError(
        "ENCRYPTION_KEY environment variable not set. "
        "Please set it to a base64-encoded Fernet key, or create a key file at backend/data/.encryption_key"
    )


def encrypt_value(value: str, key: Optional[bytes] = None) -> str:
    """
    Encrypt a string value.
    
    Args:
        value: String to encrypt
        key: Optional encryption key (uses get_encryption_key() if not provided)
        
    Returns:
        Encrypted value as base64-encoded string
    """
    if key is None:
        key = get_encryption_key()
    
    f = Fernet(key)
    encrypted = f.encrypt(value.encode())
    return encrypted.decode()


def decrypt_value(encrypted_value: str, key: Optional[bytes] = None) -> str:
    """
    Decrypt an encrypted string value.
    
    Args:
        encrypted_value: Base64-encoded encrypted string
        key: Optional encryption key (uses get_encryption_key() if not provided)
        
    Returns:
        Decrypted string value
        
    Raises:
        ValueError: If decryption fails (invalid key or corrupted data)
    """
    if key is None:
        key = get_encryption_key()
    
    f = Fernet(key)
    try:
        decrypted = f.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt value: {e}")

