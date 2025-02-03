from datetime import timedelta

class jwt_config:
    JWT_SECRET_KEY = "my_secret_key"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_BlACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = "access"
