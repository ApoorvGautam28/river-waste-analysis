"""
Enterprise-level Database Integration
PostgreSQL, Redis, and Data Warehousing for River Waste Analysis
"""

import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import hashlib
import os
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AnalysisRecord:
    """Data model for river waste analysis records"""
    id: Optional[int] = None
    timestamp: datetime = None
    image_path: str = ""
    location: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    waste_composition: Dict = None
    wwi_score: float = 0.0
    wqi_score: float = 0.0
    river_status: str = ""
    user_id: int = 1
    weather_data: Dict = None
    sensor_data: Dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.waste_composition is None:
            self.waste_composition = {}

class DatabaseManager:
    """Enterprise database management system"""
    
    def __init__(self, db_type="sqlite", connection_params=None):
        self.db_type = db_type
        self.connection_params = connection_params or {}
        self.connection = None
        self.redis_client = None
        
        self._initialize_connections()
        self._create_tables()
    
    def _initialize_connections(self):
        """Initialize database connections"""
        try:
            if self.db_type == "postgresql":
                self._connect_postgresql()
            elif self.db_type == "sqlite":
                self._connect_sqlite()
            
            # Initialize Redis for caching
            self._connect_redis()
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def _connect_sqlite(self):
        """Connect to SQLite database"""
        db_path = self.connection_params.get('database', 'river_waste_analysis.db')
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        logger.info(f"Connected to SQLite database: {db_path}")
    
    def _connect_postgresql(self):
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=self.connection_params.get('host', 'localhost'),
                database=self.connection_params.get('database', 'river_waste_db'),
                user=self.connection_params.get('user', 'postgres'),
                password=self.connection_params.get('password', ''),
                port=self.connection_params.get('port', 5432)
            )
            logger.info("Connected to PostgreSQL database")
        except ImportError:
            logger.warning("psycopg2 not installed, falling back to SQLite")
            self._connect_sqlite()
    
    def _connect_redis(self):
        """Connect to Redis for caching"""
        try:
            self.redis_client = redis.Redis(
                host=self.connection_params.get('redis_host', 'localhost'),
                port=self.connection_params.get('redis_port', 6379),
                db=self.connection_params.get('redis_db', 0),
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.redis_client = None
    
    def _create_tables(self):
        """Create database tables"""
        if self.db_type == "sqlite":
            self._create_sqlite_tables()
        elif self.db_type == "postgresql":
            self._create_postgresql_tables()
    
    def _create_sqlite_tables(self):
        """Create SQLite tables"""
        cursor = self.connection.cursor()
        
        # Main analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS river_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                location TEXT,
                latitude REAL,
                longitude REAL,
                waste_composition TEXT,
                wwi_score REAL,
                wqi_score REAL,
                river_status TEXT,
                user_id INTEGER,
                weather_data TEXT,
                sensor_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Locations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                latitude REAL,
                longitude REAL,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pollution_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                is_resolved BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES river_analyses (id)
            )
        ''')
        
        self.connection.commit()
    
    def _create_postgresql_tables(self):
        """Create PostgreSQL tables"""
        cursor = self.connection.cursor()
        
        # Main analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS river_analyses (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                location TEXT,
                latitude REAL,
                longitude REAL,
                waste_composition JSONB,
                wwi_score REAL,
                wqi_score REAL,
                river_status TEXT,
                user_id INTEGER,
                weather_data JSONB,
                sensor_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255),
                role VARCHAR(20) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Locations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_locations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                latitude REAL,
                longitude REAL,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pollution_alerts (
                id SERIAL PRIMARY KEY,
                analysis_id INTEGER REFERENCES river_analyses(id),
                alert_type VARCHAR(50),
                severity VARCHAR(20),
                message TEXT,
                is_resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analyses_timestamp ON river_analyses(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analyses_location ON river_analyses(location)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_severity ON pollution_alerts(severity)')
        
        self.connection.commit()
    
    def save_analysis(self, record: AnalysisRecord) -> int:
        """Save analysis record to database"""
        try:
            cursor = self.connection.cursor()
            
            if self.db_type == "postgresql":
                query = '''
                    INSERT INTO river_analyses 
                    (timestamp, image_path, location, latitude, longitude, 
                     waste_composition, wwi_score, wqi_score, river_status, 
                     user_id, weather_data, sensor_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                '''
                values = (
                    record.timestamp, record.image_path, record.location,
                    record.latitude, record.longitude,
                    json.dumps(record.waste_composition),
                    record.wwi_score, record.wqi_score, record.river_status,
                    record.user_id, json.dumps(record.weather_data or {}),
                    json.dumps(record.sensor_data or {})
                )
                cursor.execute(query, values)
            else:  # SQLite
                query = '''
                    INSERT INTO river_analyses 
                    (timestamp, image_path, location, latitude, longitude, 
                     waste_composition, wwi_score, wqi_score, river_status, 
                     user_id, weather_data, sensor_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
                values = (
                    record.timestamp, record.image_path, record.location,
                    record.latitude, record.longitude,
                    json.dumps(record.waste_composition),
                    record.wwi_score, record.wqi_score, record.river_status,
                    record.user_id, json.dumps(record.weather_data or {}),
                    json.dumps(record.sensor_data or {})
                )
                cursor.execute(query, values)
            
            self.connection.commit()
            record_id = cursor.lastrowid if self.db_type == "sqlite" else cursor.fetchone()[0]
            
            # Cache in Redis
            if self.redis_client:
                cache_key = f"analysis:{record_id}"
                self.redis_client.setex(
                    cache_key, 
                    3600,  # 1 hour cache
                    json.dumps({
                        'id': record_id,
                        'timestamp': record.timestamp.isoformat(),
                        'wwi_score': record.wwi_score,
                        'wqi_score': record.wqi_score,
                        'river_status': record.river_status
                    })
                )
            
            logger.info(f"Analysis saved with ID: {record_id}")
            return record_id
            
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")
            self.connection.rollback()
            raise
    
    def get_analysis(self, analysis_id: int) -> Optional[Dict]:
        """Get analysis record by ID"""
        # Try cache first
        if self.redis_client:
            cache_key = f"analysis:{analysis_id}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        
        # Query database
        try:
            cursor = self.connection.cursor()
            
            if self.db_type == "postgresql":
                cursor.execute(
                    "SELECT * FROM river_analyses WHERE id = %s",
                    (analysis_id,)
                )
            else:  # SQLite
                cursor.execute(
                    "SELECT * FROM river_analyses WHERE id = ?",
                    (analysis_id,)
                )
            
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # Parse JSON fields
                if self.db_type == "sqlite":
                    result['waste_composition'] = json.loads(result['waste_composition'])
                    result['weather_data'] = json.loads(result['weather_data'])
                    result['sensor_data'] = json.loads(result['sensor_data'])
                
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get analysis {analysis_id}: {e}")
            return None
    
    def get_analyses_by_location(self, location: str, limit: int = 100) -> List[Dict]:
        """Get analyses for a specific location"""
        try:
            cursor = self.connection.cursor()
            
            if self.db_type == "postgresql":
                cursor.execute(
                    "SELECT * FROM river_analyses WHERE location = %s ORDER BY timestamp DESC LIMIT %s",
                    (location, limit)
                )
            else:  # SQLite
                cursor.execute(
                    "SELECT * FROM river_analyses WHERE location = ? ORDER BY timestamp DESC LIMIT ?",
                    (location, limit)
                )
            
            rows = cursor.fetchall()
            results = []
            
            for row in rows:
                result = dict(row)
                if self.db_type == "sqlite":
                    result['waste_composition'] = json.loads(result['waste_composition'])
                    result['weather_data'] = json.loads(result['weather_data'])
                    result['sensor_data'] = json.loads(result['sensor_data'])
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get analyses for location {location}: {e}")
            return []
    
    def get_pollution_trends(self, days: int = 30) -> Dict:
        """Get pollution trends over time"""
        try:
            cursor = self.connection.cursor()
            start_date = datetime.now() - timedelta(days=days)
            
            if self.db_type == "postgresql":
                cursor.execute('''
                    SELECT DATE(timestamp) as date, 
                           AVG(wwi_score) as avg_wwi,
                           AVG(wqi_score) as avg_wqi,
                           COUNT(*) as analysis_count
                    FROM river_analyses 
                    WHERE timestamp >= %s
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                ''', (start_date,))
            else:  # SQLite
                cursor.execute('''
                    SELECT DATE(timestamp) as date, 
                           AVG(wwi_score) as avg_wwi,
                           AVG(wqi_score) as avg_wqi,
                           COUNT(*) as analysis_count
                    FROM river_analyses 
                    WHERE timestamp >= ?
                    GROUP BY DATE(timestamp)
                    ORDER BY date
                ''', (start_date,))
            
            rows = cursor.fetchall()
            
            trends = {
                'dates': [row[0] for row in rows],
                'avg_wwi': [float(row[1]) for row in rows],
                'avg_wqi': [float(row[2]) for row in rows],
                'analysis_count': [row[3] for row in rows]
            }
            
            return trends
            
        except Exception as e:
            logger.error(f"Failed to get pollution trends: {e}")
            return {'dates': [], 'avg_wwi': [], 'avg_wqi': [], 'analysis_count': []}
    
    def create_alert(self, analysis_id: int, alert_type: str, severity: str, message: str) -> int:
        """Create pollution alert"""
        try:
            cursor = self.connection.cursor()
            
            if self.db_type == "postgresql":
                cursor.execute('''
                    INSERT INTO pollution_alerts (analysis_id, alert_type, severity, message)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                ''', (analysis_id, alert_type, severity, message))
            else:  # SQLite
                cursor.execute('''
                    INSERT INTO pollution_alerts (analysis_id, alert_type, severity, message)
                    VALUES (?, ?, ?, ?)
                ''', (analysis_id, alert_type, severity, message))
            
            self.connection.commit()
            alert_id = cursor.lastrowid if self.db_type == "sqlite" else cursor.fetchone()[0]
            
            logger.info(f"Alert created with ID: {alert_id}")
            return alert_id
            
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            self.connection.rollback()
            raise
    
    def get_active_alerts(self, severity: str = None) -> List[Dict]:
        """Get active pollution alerts"""
        try:
            cursor = self.connection.cursor()
            
            if severity:
                if self.db_type == "postgresql":
                    cursor.execute('''
                        SELECT a.*, r.location, r.river_status
                        FROM pollution_alerts a
                        JOIN river_analyses r ON a.analysis_id = r.id
                        WHERE a.is_resolved = FALSE AND a.severity = %s
                        ORDER BY a.created_at DESC
                    ''', (severity,))
                else:  # SQLite
                    cursor.execute('''
                        SELECT a.*, r.location, r.river_status
                        FROM pollution_alerts a
                        JOIN river_analyses r ON a.analysis_id = r.id
                        WHERE a.is_resolved = 0 AND a.severity = ?
                        ORDER BY a.created_at DESC
                    ''', (severity,))
            else:
                if self.db_type == "postgresql":
                    cursor.execute('''
                        SELECT a.*, r.location, r.river_status
                        FROM pollution_alerts a
                        JOIN river_analyses r ON a.analysis_id = r.id
                        WHERE a.is_resolved = FALSE
                        ORDER BY a.severity, a.created_at DESC
                    ''')
                else:  # SQLite
                    cursor.execute('''
                        SELECT a.*, r.location, r.river_status
                        FROM pollution_alerts a
                        JOIN river_analyses r ON a.analysis_id = r.id
                        WHERE a.is_resolved = 0
                        ORDER BY a.severity, a.created_at DESC
                    ''')
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []
    
    def export_data_to_csv(self, output_path: str, date_range: Tuple = None):
        """Export analysis data to CSV"""
        try:
            query = "SELECT * FROM river_analyses"
            params = []
            
            if date_range:
                start_date, end_date = date_range
                if self.db_type == "postgresql":
                    query += " WHERE timestamp BETWEEN %s AND %s"
                else:  # SQLite
                    query += " WHERE timestamp BETWEEN ? AND ?"
                params = [start_date, end_date]
            
            df = pd.read_sql_query(query, self.connection, params=params)
            df.to_csv(output_path, index=False)
            logger.info(f"Data exported to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            raise
    
    def close(self):
        """Close database connections"""
        if self.connection:
            self.connection.close()
        if self.redis_client:
            self.redis_client.close()

class DataWarehouse:
    """Advanced data warehousing for analytics"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def generate_comprehensive_report(self, start_date: datetime, end_date: datetime) -> Dict:
        """Generate comprehensive analytics report"""
        try:
            # Get all analyses in date range
            cursor = self.db_manager.connection.cursor()
            
            if self.db_manager.db_type == "postgresql":
                cursor.execute('''
                    SELECT * FROM river_analyses 
                    WHERE timestamp BETWEEN %s AND %s
                    ORDER BY timestamp
                ''', (start_date, end_date))
            else:  # SQLite
                cursor.execute('''
                    SELECT * FROM river_analyses 
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp
                ''', (start_date, end_date))
            
            analyses = cursor.fetchall()
            
            # Generate statistics
            report = {
                'summary': self._generate_summary(analyses),
                'trends': self._analyze_trends(analyses),
                'hotspots': self._identify_pollution_hotspots(analyses),
                'recommendations': self._generate_recommendations(analyses)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return {}
    
    def _generate_summary(self, analyses: List) -> Dict:
        """Generate summary statistics"""
        if not analyses:
            return {}
        
        total_analyses = len(analyses)
        avg_wwi = sum(row['wwi_score'] for row in analyses) / total_analyses
        avg_wqi = sum(row['wqi_score'] for row in analyses) / total_analyses
        
        # Count by river status
        status_counts = {}
        for analysis in analyses:
            status = analysis['river_status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'total_analyses': total_analyses,
            'average_wwi': round(avg_wwi, 2),
            'average_wqi': round(avg_wqi, 2),
            'status_distribution': status_counts,
            'most_common_status': max(status_counts, key=status_counts.get)
        }
    
    def _analyze_trends(self, analyses: List) -> Dict:
        """Analyze pollution trends"""
        # Group by date
        daily_data = {}
        for analysis in analyses:
            date = analysis['timestamp'].date()
            if date not in daily_data:
                daily_data[date] = {'wwi': [], 'wqi': []}
            daily_data[date]['wwi'].append(analysis['wwi_score'])
            daily_data[date]['wqi'].append(analysis['wqi_score'])
        
        # Calculate daily averages
        trend_data = {
            'dates': sorted(daily_data.keys()),
            'wwi_trend': [],
            'wqi_trend': []
        }
        
        for date in trend_data['dates']:
            wwi_avg = sum(daily_data[date]['wwi']) / len(daily_data[date]['wwi'])
            wqi_avg = sum(daily_data[date]['wqi']) / len(daily_data[date]['wqi'])
            trend_data['wwi_trend'].append(wwi_avg)
            trend_data['wqi_trend'].append(wqi_avg)
        
        return trend_data
    
    def _identify_pollution_hotspots(self, analyses: List) -> List[Dict]:
        """Identify pollution hotspots"""
        location_stats = {}
        
        for analysis in analyses:
            location = analysis['location'] or 'Unknown'
            if location not in location_stats:
                location_stats[location] = {
                    'analyses': [],
                    'total_wwi': 0,
                    'total_wqi': 0
                }
            
            location_stats[location]['analyses'].append(analysis)
            location_stats[location]['total_wwi'] += analysis['wwi_score']
            location_stats[location]['total_wqi'] += analysis['wqi_score']
        
        # Calculate averages and identify hotspots
        hotspots = []
        for location, stats in location_stats.items():
            count = len(stats['analyses'])
            avg_wwi = stats['total_wwi'] / count
            avg_wqi = stats['total_wqi'] / count
            
            if avg_wwi > 50 or avg_wqi > 50:  # Threshold for hotspot
                hotspots.append({
                    'location': location,
                    'analysis_count': count,
                    'average_wwi': round(avg_wwi, 2),
                    'average_wqi': round(avg_wqi, 2),
                    'severity': 'High' if avg_wwi > 70 else 'Medium'
                })
        
        # Sort by severity
        hotspots.sort(key=lambda x: x['average_wwi'], reverse=True)
        return hotspots[:10]  # Top 10 hotspots
    
    def _generate_recommendations(self, analyses: List) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if not analyses:
            return recommendations
        
        avg_wwi = sum(row['wwi_score'] for row in analyses) / len(analyses)
        avg_wqi = sum(row['wqi_score'] for row in analyses) / len(analyses)
        
        if avg_wwi > 70:
            recommendations.append("Immediate cleanup intervention required - severe pollution detected")
        elif avg_wwi > 50:
            recommendations.append("Regular monitoring and cleanup schedule recommended")
        
        if avg_wqi > 70:
            recommendations.append("Water quality treatment necessary before recreational use")
        elif avg_wqi > 50:
            recommendations.append("Implement water quality improvement measures")
        
        # Analyze waste composition
        all_compositions = []
        for analysis in analyses:
            if self.db_manager.db_type == "sqlite":
                composition = json.loads(analysis['waste_composition'])
            else:
                composition = analysis['waste_composition']
            all_compositions.append(composition)
        
        if all_compositions:
            # Find dominant waste types
            waste_totals = {}
            for composition in all_compositions:
                for waste_type, percentage in composition.items():
                    waste_totals[waste_type] = waste_totals.get(waste_type, 0) + percentage
            
            dominant_waste = max(waste_totals, key=waste_totals.get)
            if dominant_waste == "Plastic":
                recommendations.append("Focus on plastic waste reduction and recycling programs")
            elif dominant_waste == "E-Waste":
                recommendations.append("Implement e-waste collection and proper disposal systems")
            elif dominant_waste == "Organic Waste":
                recommendations.append("Consider organic waste composting solutions")
        
        return recommendations
