from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio
import logging
from typing import Optional
from models import JemuranData, RecommendationResponse, RecommendationDetails, ControlRequest, HealthCheckResponse
from mqtt_handler import MQTTClient
from fuzzy_logic import FuzzySystem

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Smart Jemuran API",
    version="1.0.0",
    description="API untuk sistem jemuran pintar berbasis IoT dan fuzzy logic",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
mqtt_client = MQTTClient()
fuzzy_system = FuzzySystem()

# Startup event


@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    try:
        logger.info("Starting up application...")

        # Connect to MQTT (sync function run in thread)
        def sync_connect():
            mqtt_client.connect()

        await asyncio.to_thread(sync_connect)

        logger.info("Application startup completed")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}", exc_info=True)
        raise

# Health check endpoint


@app.get("/health", response_model=HealthCheckResponse, include_in_schema=False)
async def health_check():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "mqtt": "connected" if mqtt_client.is_connected else "disconnected",
            "fuzzy_system": "ready"
        }
    }

# API Endpoints


@app.get("/api/data", response_model=JemuranData)
async def get_latest_data():
    """
    Get latest sensor data from MQTT
    """
    if not mqtt_client.latest_data:
        logger.warning("No data available when requested")
        raise HTTPException(
            status_code=404,
            detail="Belum ada data sensor yang tersedia"
        )

    latest = mqtt_client.latest_data
    return JemuranData(
        temperature=latest.temperature,
        humidity=latest.humidity,
        light=latest.light,
        rain=latest.rain,
        last_update=latest.last_update
    )


@app.get("/api/recommendation", response_model=RecommendationResponse)
async def get_recommendation():
    """
    Get drying recommendation using fuzzy logic
    """
    if not mqtt_client.latest_data:
        logger.error("Recommendation requested but no sensor data available")
        raise HTTPException(
            status_code=404,
            detail="Data sensor tidak tersedia untuk membuat rekomendasi"
        )

    try:
        logger.info("Generating drying recommendation...")

        # Prepare input data
        latest = mqtt_client.latest_data
        rain_value = 1 if latest.rain else 0
        current_hour = datetime.now().hour % 24

        # Log input values
        logger.debug(
            f"Input values - Temp: {latest.temperature}, "
            f"Humidity: {latest.humidity}, "
            f"Light: {latest.light}, "
            f"Rain: {rain_value}, Time: {current_hour}"
        )

        # Evaluate with fuzzy system
        result = fuzzy_system.evaluate(
            temperature=float(latest.temperature),
            humidity=float(latest.humidity),
            light=int(latest.light),
            rain=rain_value,
            time=current_hour
        )

        # Check for errors
        if result.get("status") == "error":
            logger.error(f"Fuzzy system error: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Kesalahan sistem fuzzy: {result.get('error')}"
            )

        # Prepare response
        response_data = {
            "recommendation": result["recommendation"],
            "confidence": result["confidence"],
            "details": {
                "rules_activated": result.get("rules_activated", []),
                "input_values": {
                    "temperature": latest.temperature,
                    "humidity": latest.humidity,
                    "light": latest.light,
                    "rain": latest.rain,
                    "time": current_hour
                }
            }
        }

        logger.info(f"Recommendation generated: {result['recommendation']}")
        return response_data

    except Exception as e:
        logger.error(
            f"Recommendation generation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kesalahan saat membuat rekomendasi: {str(e)}"
        )


@app.post("/api/control")
async def control_jemuran(request: ControlRequest):
    """
    Send control command to clothes rack
    """
    valid_actions = ["buka", "tutup"]

    if request.action.lower() not in valid_actions:
        logger.warning(f"Invalid control action requested: {request.action}")
        raise HTTPException(
            status_code=400,
            detail=f"Aksi tidak valid. Gunakan salah satu dari: {', '.join(valid_actions)}"
        )

    try:
        logger.info(f"Sending control command: {request.action}")
        success, message = await mqtt_client.async_publish_control(request.action.lower())

        if not success:
            raise HTTPException(status_code=500, detail=message)

        return {
            "status": "success",
            "action": request.action,
            "message": message
        }
    except Exception as e:
        logger.error(f"Control command failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengirim perintah kontrol: {str(e)}"
        )


@app.get("/api/statusjemuran")
async def get_jemuran_status():
    """
    Get current jemuran status (TERBUKA/TERTUTUP)
    Response: {
        "status": "success",
        "status_jemuran": "TERBUKA"|"TERTUTUP",
        "last_update": "datetime"
    }
    """
    if not mqtt_client.latest_data:
        logger.warning("No data available when requesting jemuran status")
        raise HTTPException(
            status_code=404,
            detail="Belum ada data sensor yang tersedia"
        )

    try:
        latest = mqtt_client.latest_data
        
        # Pastikan status_jemuran ada di data
        if not hasattr(latest, 'status_jemuran') or latest.status_jemuran is None:
            logger.warning("Jemuran status field missing")
            raise HTTPException(
                status_code=404,
                detail="Field status_jemuran tidak ditemukan dalam data sensor"
            )

        return {
            "status": "success",
            "status_jemuran": latest.status_jemuran,
            "last_update": latest.last_update.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get jemuran status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kesalahan saat mengambil status jemuran: {str(e)}"
        )
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )
