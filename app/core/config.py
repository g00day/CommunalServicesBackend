from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    DEBUG: bool 

    JWT_SECRET: str
    JWT_ALGORITHM: str 
    ACCESS_TOKEN_MINUTES: int 
    REFRESH_TOKEN_DAYS: int
    CHAT_WEBHOOK_SECRET: str | None = None

    POSTGRES_URL: str
    S3_ENDPOINT_URL: str = "https://storage.yandexcloud.net"
    S3_REGION: str = "ru-central1"
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_PUBLIC_BASE_URL: str | None = None
    TELEGRAM_LINK_CODE_MINUTES: int = 60

    APP_BASE_URL: str 

    # Email
    MAIL_USERNAME: str 
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_SERVER: str 
    MAIL_PORT: int 
    MAIL_SSL: bool 
    MAIL_TLS: bool 

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
