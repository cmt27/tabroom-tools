# app/auth/credential_manager.py
import os
import base64
import json
import logging
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from app import config

logger = logging.getLogger(__name__)

class CredentialManager:
    """Secure management of user credentials"""
    
    def __init__(self, storage_dir=None, encryption_key=None):
        """
        Initialize the credential manager
        
        Args:
            storage_dir: Directory to store encrypted credentials
            encryption_key: Key used for encryption/decryption
        """
        self.storage_dir = storage_dir or config.COOKIE_DIR
        
        # Ensure the storage directory exists
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Define file paths
        self.key_file = os.path.join(self.storage_dir, ".key")
        self.credentials_file = os.path.join(self.storage_dir, "credentials.enc")
        
        # Setup encryption key - if there are existing credentials but no key file,
        # we'll need to delete the credentials as we can't decrypt them
        if os.path.exists(self.credentials_file) and not os.path.exists(self.key_file):
            logger.warning("Found credentials but no key file. Removing old credentials.")
            try:
                os.remove(self.credentials_file)
            except Exception as e:
                logger.error(f"Failed to remove old credentials: {e}")
        
        # Initialize encryption key
        self.encryption_key = self._initialize_key(encryption_key)
    
    def _initialize_key(self, provided_key=None):
        """
        Initialize the encryption key, either from provided key, existing key file,
        or by generating a new one
        
        Args:
            provided_key: Optional key provided by the caller
            
        Returns:
            bytes: 32-byte encryption key
        """
        # Use provided key if available
        if provided_key:
            if isinstance(provided_key, str):
                # Convert string to bytes and ensure it's 32 bytes
                key = provided_key.encode('utf-8')
                if len(key) < 32:
                    key = key.ljust(32, b'\0')
                elif len(key) > 32:
                    key = key[:32]
                return key
            elif isinstance(provided_key, bytes):
                # Ensure bytes are 32 bytes
                if len(provided_key) < 32:
                    key = provided_key.ljust(32, b'\0')
                elif len(provided_key) > 32:
                    key = provided_key[:32]
                return key
        
        # If key file exists, load it
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, "rb") as f:
                    key = f.read()
                    if len(key) != 32:
                        logger.warning("Key file has incorrect length. Generating new key.")
                        return self._generate_and_save_key()
                    return key
            except Exception as e:
                logger.error(f"Error loading key file: {e}")
                return self._generate_and_save_key()
        
        # Otherwise, generate a new key
        return self._generate_and_save_key()
    
    def _generate_and_save_key(self):
        """
        Generate a new random key and save it to the key file
        
        Returns:
            bytes: The generated key
        """
        key = get_random_bytes(32)  # 256 bits
        try:
            with open(self.key_file, "wb") as f:
                f.write(key)
            logger.info("Generated and saved new encryption key")
        except Exception as e:
            logger.error(f"Failed to save encryption key: {e}")
        
        return key
    
    def save_credentials(self, username, password):
        """
        Save credentials securely
        
        Args:
            username: User's username/email
            password: User's password
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Prepare credentials as a JSON string
            credentials = {
                "username": username,
                "password": password
            }
            credentials_json = json.dumps(credentials)
            
            # Encrypt and save
            encrypted_data = self._encrypt_data(credentials_json)
            with open(self.credentials_file, "wb") as f:
                f.write(encrypted_data)
                
            logger.info("Credentials saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
            return False
    
    def load_credentials(self):
        """
        Load stored credentials
        
        Returns:
            dict: Dictionary with username and password, or None if not available
        """
        if not os.path.exists(self.credentials_file):
            logger.info("No stored credentials found")
            return None
            
        try:
            # Read encrypted data
            with open(self.credentials_file, "rb") as f:
                encrypted_data = f.read()
                
            # Decrypt data
            decrypted_json = self._decrypt_data(encrypted_data)
            if not decrypted_json:
                # If decryption fails, clear the file and return None
                logger.warning("Decryption failed. Removing corrupted credentials file.")
                self.clear_credentials()
                return None
                
            # Parse JSON into dictionary
            credentials = json.loads(decrypted_json)
            logger.info("Credentials loaded successfully")
            return credentials
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid credential format: {e}")
            self.clear_credentials()
            return None
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            self.clear_credentials()
            return None
    
    def clear_credentials(self):
        """
        Delete stored credentials
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(self.credentials_file):
            return True
            
        try:
            os.remove(self.credentials_file)
            logger.info("Credentials deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting credentials: {e}")
            return False
    
    def _encrypt_data(self, data):
        """
        Encrypt data using AES
        
        Args:
            data: String data to encrypt
            
        Returns:
            bytes: Combined IV and encrypted data
        """
        try:
            # Convert data to bytes
            data_bytes = data.encode('utf-8')
            
            # Create cipher with random IV
            iv = get_random_bytes(16)
            cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
            
            # Pad and encrypt
            padded_data = pad(data_bytes, AES.block_size)
            encrypted_data = cipher.encrypt(padded_data)
            
            # Combine IV and encrypted data
            return iv + encrypted_data
            
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def _decrypt_data(self, encrypted_data):
        """
        Decrypt data using AES
        
        Args:
            encrypted_data: Combined IV and encrypted data
            
        Returns:
            str: Decrypted data as string or None if decryption failed
        """
        try:
            # Extract IV (first 16 bytes) and encrypted data
            if len(encrypted_data) < 16:
                logger.error("Encrypted data too short to contain IV")
                return None
                
            iv = encrypted_data[:16]
            encrypted_bytes = encrypted_data[16:]
            
            # Create cipher with extracted IV
            cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
            
            # Decrypt and unpad
            decrypted_padded = cipher.decrypt(encrypted_bytes)
            decrypted_data = unpad(decrypted_padded, AES.block_size)
            
            # Convert back to string
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None