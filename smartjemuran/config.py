from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    mqtt_broker: str = "192.168.2.254"
    mqtt_port: int = 1884
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"

settings = Settings()