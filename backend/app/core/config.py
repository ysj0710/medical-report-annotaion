from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Medical Report Annotation"
    DATABASE_URL: str = "postgresql+psycopg2://enjoy0710:@localhost:5432/med_anno"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    class Config:
        env_file = ".env"


settings = Settings()
