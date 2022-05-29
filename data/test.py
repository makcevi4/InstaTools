from cryptography.fernet import Fernet
password = 'dasdasdasdasdasdasd'
key = Fernet.generate_key()
print(key)
processor = Fernet(key)
encrypted = processor.encrypt(password.encode('utf-8'))
print(encrypted)
decrypted = processor.decrypt(encrypted)
print(decrypted)
