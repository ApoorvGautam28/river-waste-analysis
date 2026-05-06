"""
Enterprise REST API Server for River Waste Analysis
FastAPI-based backend with authentication, real-time monitoring, and external integrations
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import jwt
from passlib.context import CryptContext
import boto3
from botocore.exceptions import NoCredentialsError
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import our modules
from database import DatabaseManager, AnalysisRecord
from ml_models import WasteDetectionML, PredictiveAnalytics, AdvancedImageProcessing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="River Waste Analysis API",
    description="Enterprise-level river pollution monitoring and analysis system",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# Initialize components
db_manager = DatabaseManager()
ml_detector = WasteDetectionML()
predictive_analytics = PredictiveAnalytics()

# Pydantic models
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "user"

class AnalysisRequest(BaseModel):
    image_path: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    user_id: Optional[int] = 1
    weather_data: Optional[Dict] = None
    sensor_data: Optional[Dict] = None

class AnalysisResponse(BaseModel):
    id: int
    timestamp: str
    waste_composition: Dict[str, float]
    wwi_score: float
    wqi_score: float
    river_status: str
    location: str
    confidence_score: float

class AlertResponse(BaseModel):
    id: int
    analysis_id: int
    alert_type: str
    severity: str
    message: str
    created_at: str
    location: str

class MonitoringLocation(BaseModel):
    name: str
    latitude: float
    longitude: float
    description: Optional[str] = ""
    is_active: bool = True

# Authentication functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

# API Routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "River Waste Analysis API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/api/docs",
            "health": "/api/health",
            "analyze": "/api/analyze",
            "history": "/api/history",
            "alerts": "/api/alerts"
        }
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        db_manager.connection.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "ml_models": "loaded",
            "version": "2.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.post("/api/auth/login")
async def login(user_credentials: UserLogin):
    """User authentication"""
    try:
        cursor = db_manager.connection.cursor()
        
        if db_manager.db_type == "postgresql":
            cursor.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = %s",
                (user_credentials.username,)
            )
        else:  # SQLite
            cursor.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                (user_credentials.username,)
            )
        
        user = cursor.fetchone()
        
        if not user or not verify_password(user_credentials.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(data={"sub": user['username'], "role": user['role']})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "role": user['role']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@app.post("/api/auth/register")
async def register(user_data: UserCreate):
    """User registration"""
    try:
        # Check if user exists
        cursor = db_manager.connection.cursor()
        
        if db_manager.db_type == "postgresql":
            cursor.execute(
                "SELECT id FROM users WHERE username = %s OR email = %s",
                (user_data.username, user_data.email)
            )
        else:  # SQLite
            cursor.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (user_data.username, user_data.email)
            )
        
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create new user
        password_hash = get_password_hash(user_data.password)
        
        if db_manager.db_type == "postgresql":
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
                (user_data.username, user_data.email, password_hash, user_data.role)
            )
        else:  # SQLite
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (user_data.username, user_data.email, password_hash, user_data.role)
            )
        
        db_manager.connection.commit()
        user_id = cursor.lastrowid if db_manager.db_type == "sqlite" else cursor.fetchone()[0]
        
        return {
            "message": "User created successfully",
            "user_id": user_id,
            "username": user_data.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_river(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(verify_token)
):
    """Analyze river waste composition"""
    try:
        # Perform ML analysis
        waste_composition = ml_detector.predict_waste_composition(request.image_path)
        
        # Calculate WWI and WQI (simplified calculations)
        wwi_score = sum(
            waste_composition.get(category, 0) * weight 
            for category, weight in ml_detector.waste_risk_weights.items()
        ) / 100
        
        # Mock WQI calculation (would integrate with water quality sensors)
        wqi_score = 45.0 + (wwi_score * 0.3)  # Simplified inverse relationship
        
        # Determine river status
        if wqi <= 25 and wwi < 20:
            river_status = "Clean"
        elif wqi <= 50 and wwi < 40:
            river_status = "Moderately Polluted"
        elif wqi <= 75 and wwi < 70:
            river_status = "Polluted"
        else:
            river_status = "Severely Polluted"
        
        # Create analysis record
        record = AnalysisRecord(
            image_path=request.image_path,
            location=request.location,
            latitude=request.latitude,
            longitude=request.longitude,
            waste_composition=waste_composition,
            wwi_score=wwi_score,
            wqi_score=wqi_score,
            river_status=river_status,
            user_id=request.user_id,
            weather_data=request.weather_data,
            sensor_data=request.sensor_data
        )
        
        # Save to database
        analysis_id = db_manager.save_analysis(record)
        
        # Create alerts if necessary
        background_tasks.add_task(
            check_and_create_alerts,
            analysis_id,
            wwi_score,
            wqi_score,
            river_status,
            request.location
        )
        
        # Calculate confidence score
        confidence_score = calculate_confidence_score(waste_composition)
        
        return AnalysisResponse(
            id=analysis_id,
            timestamp=record.timestamp.isoformat(),
            waste_composition=waste_composition,
            wwi_score=round(wwi_score, 2),
            wqi_score=round(wqi_score, 2),
            river_status=river_status,
            location=request.location,
            confidence_score=confidence_score
        )
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

@app.post("/api/analyze/upload")
async def analyze_uploaded_image(
    file: UploadFile = File(...),
    location: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    current_user: str = Depends(verify_token)
):
    """Analyze uploaded image"""
    try:
        # Save uploaded file
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ["jpg", "jpeg", "png"]:
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Generate unique filename
        filename = f"{uuid.uuid4()}.{file_extension}"
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create analysis request
        request = AnalysisRequest(
            image_path=file_path,
            location=location,
            latitude=latitude,
            longitude=longitude
        )
        
        # Analyze
        return await analyze_river(request, BackgroundTasks(), current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Upload analysis failed")

@app.get("/api/history")
async def get_analysis_history(
    location: Optional[str] = None,
    limit: int = 100,
    current_user: str = Depends(verify_token)
):
    """Get analysis history"""
    try:
        if location:
            analyses = db_manager.get_analyses_by_location(location, limit)
        else:
            # Get all recent analyses
            cursor = db_manager.connection.cursor()
            if db_manager.db_type == "postgresql":
                cursor.execute(
                    "SELECT * FROM river_analyses ORDER BY timestamp DESC LIMIT %s",
                    (limit,)
                )
            else:  # SQLite
                cursor.execute(
                    "SELECT * FROM river_analyses ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            
            analyses = [dict(row) for row in cursor.fetchall()]
        
        return {
            "analyses": analyses,
            "total_count": len(analyses),
            "location_filter": location
        }
        
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")

@app.get("/api/trends")
async def get_pollution_trends(
    days: int = 30,
    current_user: str = Depends(verify_token)
):
    """Get pollution trends over time"""
    try:
        trends = db_manager.get_pollution_trends(days)
        
        return {
            "period_days": days,
            "trends": trends,
            "summary": {
                "avg_wwi": sum(trends['avg_wwi']) / len(trends['avg_wwi']) if trends['avg_wwi'] else 0,
                "avg_wqi": sum(trends['avg_wqi']) / len(trends['avg_wqi']) if trends['avg_wqi'] else 0,
                "total_analyses": sum(trends['analysis_count'])
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve trends")

@app.get("/api/alerts", response_model=List[AlertResponse])
async def get_alerts(
    severity: Optional[str] = None,
    current_user: str = Depends(verify_token)
):
    """Get active pollution alerts"""
    try:
        alerts = db_manager.get_active_alerts(severity)
        
        return [
            AlertResponse(
                id=alert['id'],
                analysis_id=alert['analysis_id'],
                alert_type=alert['alert_type'],
                severity=alert['severity'],
                message=alert['message'],
                created_at=alert['created_at'].isoformat() if hasattr(alert['created_at'], 'isoformat') else str(alert['created_at']),
                location=alert.get('location', 'Unknown')
            )
            for alert in alerts
        ]
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")

@app.post("/api/locations")
async def add_monitoring_location(
    location: MonitoringLocation,
    current_user: str = Depends(verify_token)
):
    """Add monitoring location"""
    try:
        cursor = db_manager.connection.cursor()
        
        if db_manager.db_type == "postgresql":
            cursor.execute(
                "INSERT INTO monitoring_locations (name, latitude, longitude, description, is_active) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (location.name, location.latitude, location.longitude, location.description, location.is_active)
            )
        else:  # SQLite
            cursor.execute(
                "INSERT INTO monitoring_locations (name, latitude, longitude, description, is_active) VALUES (?, ?, ?, ?, ?)",
                (location.name, location.latitude, location.longitude, location.description, location.is_active)
            )
        
        db_manager.connection.commit()
        location_id = cursor.lastrowid if db_manager.db_type == "sqlite" else cursor.fetchone()[0]
        
        return {
            "message": "Location added successfully",
            "location_id": location_id,
            "name": location.name
        }
        
    except Exception as e:
        logger.error(f"Failed to add location: {e}")
        raise HTTPException(status_code=500, detail="Failed to add location")

@app.get("/api/locations")
async def get_monitoring_locations(current_user: str = Depends(verify_token)):
    """Get all monitoring locations"""
    try:
        cursor = db_manager.connection.cursor()
        
        if db_manager.db_type == "postgresql":
            cursor.execute("SELECT * FROM monitoring_locations WHERE is_active = TRUE")
        else:  # SQLite
            cursor.execute("SELECT * FROM monitoring_locations WHERE is_active = 1")
        
        locations = [dict(row) for row in cursor.fetchall()]
        
        return {"locations": locations}
        
    except Exception as e:
        logger.error(f"Failed to get locations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve locations")

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: str = Depends(verify_token)):
    """Get dashboard statistics"""
    try:
        # Get recent statistics
        cursor = db_manager.connection.cursor()
        
        if db_manager.db_type == "postgresql":
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_analyses,
                    AVG(wwi_score) as avg_wwi,
                    AVG(wqi_score) as avg_wqi,
                    COUNT(CASE WHEN river_status = 'Severely Polluted' THEN 1 END) as severely_polluted,
                    COUNT(CASE WHEN river_status = 'Clean' THEN 1 END) as clean_rivers
                FROM river_analyses 
                WHERE timestamp >= NOW() - INTERVAL '7 days'
            ''')
        else:  # SQLite
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_analyses,
                    AVG(wwi_score) as avg_wwi,
                    AVG(wqi_score) as avg_wqi,
                    COUNT(CASE WHEN river_status = 'Severely Polluted' THEN 1 END) as severely_polluted,
                    COUNT(CASE WHEN river_status = 'Clean' THEN 1 END) as clean_rivers
                FROM river_analyses 
                WHERE timestamp >= datetime('now', '-7 days')
            ''')
        
        stats = dict(cursor.fetchone())
        
        # Get active alerts count
        active_alerts = db_manager.get_active_alerts()
        stats['active_alerts'] = len(active_alerts)
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

@app.get("/api/export/csv")
async def export_data_csv(
    start_date: str,
    end_date: str,
    current_user: str = Depends(verify_token)
):
    """Export data to CSV"""
    try:
        # Parse dates
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # Generate filename
        filename = f"river_waste_data_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}.csv"
        output_path = f"exports/{filename}"
        
        # Ensure export directory exists
        os.makedirs("exports", exist_ok=True)
        
        # Export data
        db_manager.export_data_to_csv(output_path, (start_dt, end_dt))
        
        return FileResponse(
            output_path,
            media_type="text/csv",
            filename=filename
        )
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail="Export failed")

# Background tasks
async def check_and_create_alerts(analysis_id: int, wwi_score: float, wqi_score: float, river_status: str, location: str):
    """Check thresholds and create alerts"""
    try:
        if river_status == "Severely Polluted":
            await create_alert(
                analysis_id,
                "critical_pollution",
                "critical",
                f"Critical pollution detected at {location}. WWI: {wwi_score:.2f}, WQI: {wqi_score:.2f}"
            )
        elif river_status == "Polluted":
            await create_alert(
                analysis_id,
                "high_pollution",
                "high",
                f"High pollution levels detected at {location}. WWI: {wwi_score:.2f}, WQI: {wqi_score:.2f}"
            )
        
        # Send email notification for critical alerts
        if river_status == "Severely Polluted":
            await send_pollution_alert_email(location, wwi_score, wqi_score)
            
    except Exception as e:
        logger.error(f"Alert creation failed: {e}")

async def create_alert(analysis_id: int, alert_type: str, severity: str, message: str):
    """Create pollution alert"""
    try:
        db_manager.create_alert(analysis_id, alert_type, severity, message)
        logger.info(f"Alert created: {alert_type} - {severity}")
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")

async def send_pollution_alert_email(location: str, wwi_score: float, wqi_score: float):
    """Send pollution alert email"""
    try:
        # Email configuration (would be environment variables)
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        
        if not smtp_username or not smtp_password:
            logger.warning("SMTP credentials not configured, skipping email")
            return
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = smtp_username
        msg['To'] = os.getenv("ALERT_EMAIL", smtp_username)
        msg['Subject'] = f"🚨 Critical Pollution Alert: {location}"
        
        body = f"""
        Critical pollution detected at {location}.
        
        Details:
        - WWI Score: {wwi_score:.2f}
        - WQI Score: {wqi_score:.2f}
        - Status: Severely Polluted
        - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Immediate action required!
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Pollution alert email sent for {location}")
        
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")

# Utility functions
def calculate_confidence_score(waste_composition: Dict[str, float]) -> float:
    """Calculate confidence score for analysis"""
    # Simple confidence calculation based on distribution
    max_percentage = max(waste_composition.values())
    total_percentage = sum(waste_composition.values())
    
    if total_percentage == 0:
        return 0.0
    
    # Higher confidence if one category dominates significantly
    confidence = (max_percentage / total_percentage) * 0.8 + 0.2
    return round(confidence, 2)

# Static files for web interface
app.mount("/static", StaticFiles(directory="static"), name="static")

# Run the server
if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
