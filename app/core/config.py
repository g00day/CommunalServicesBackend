from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    DEBUG: bool 

    JWT_SECRET: str
    JWT_ALGORITHM: str 
    ACCESS_TOKEN_MINUTES: int 
    REFRESH_TOKEN_DAYS: int

    POSTGRES_URL: str

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
