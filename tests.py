"""
Comprehensive Testing Suite for River Waste Analysis System
Unit tests, integration tests, and performance testing
"""

import unittest
import pytest
import asyncio
import json
import tempfile
import os
import cv2
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import requests
from fastapi.testclient import TestClient
import pandas as pd

# Import our modules
from api_server import app
from database import DatabaseManager, AnalysisRecord
from ml_models import WasteDetectionML, PredictiveAnalytics, AdvancedImageProcessing

class TestDatabaseManager(unittest.TestCase):
    """Test database operations"""
    
    def setUp(self):
        """Set up test database"""
        self.db_manager = DatabaseManager(db_type="sqlite", connection_params={
            'database': ':memory:'
        })
    
    def tearDown(self):
        """Clean up after tests"""
        self.db_manager.close()
    
    def test_database_connection(self):
        """Test database connection"""
        self.assertIsNotNone(self.db_manager.connection)
        
        # Test basic query
        cursor = self.db_manager.connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        self.assertEqual(result[0], 1)
    
    def test_save_analysis(self):
        """Test saving analysis record"""
        record = AnalysisRecord(
            image_path="test_image.jpg",
            location="Test River",
            latitude=51.5074,
            longitude=-0.1278,
            waste_composition={"Plastic": 25.0, "Metal": 15.0},
            wwi_score=45.5,
            wqi_score=62.3,
            river_status="Moderately Polluted"
        )
        
        record_id = self.db_manager.save_analysis(record)
        self.assertIsInstance(record_id, int)
        self.assertGreater(record_id, 0)
    
    def test_get_analysis(self):
        """Test retrieving analysis record"""
        # Save a record first
        record = AnalysisRecord(
            image_path="test_image.jpg",
            location="Test River",
            waste_composition={"Plastic": 25.0, "Metal": 15.0},
            wwi_score=45.5,
            wqi_score=62.3,
            river_status="Moderately Polluted"
        )
        record_id = self.db_manager.save_analysis(record)
        
        # Retrieve the record
        retrieved = self.db_manager.get_analysis(record_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['location'], "Test River")
        self.assertEqual(retrieved['wwi_score'], 45.5)
    
    def test_get_pollution_trends(self):
        """Test pollution trends calculation"""
        # Create test data
        for i in range(10):
            record = AnalysisRecord(
                image_path=f"test_{i}.jpg",
                location="Test River",
                waste_composition={"Plastic": 25.0, "Metal": 15.0},
                wwi_score=40.0 + i,
                wqi_score=60.0 - i,
                river_status="Moderately Polluted",
                timestamp=datetime.now() - timedelta(days=i)
            )
            self.db_manager.save_analysis(record)
        
        # Get trends
        trends = self.db_manager.get_pollution_trends(days=30)
        self.assertIn('dates', trends)
        self.assertIn('avg_wwi', trends)
        self.assertIn('avg_wqi', trends)
        self.assertGreater(len(trends['dates']), 0)

class TestWasteDetectionML(unittest.TestCase):
    """Test ML models and waste detection"""
    
    def setUp(self):
        """Set up ML detector"""
        self.ml_detector = WasteDetectionML()
        
        # Create test image
        self.test_image = self.create_test_image()
        self.temp_image_path = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False).name
        cv2.imwrite(self.temp_image_path, self.test_image)
    
    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_image_path):
            os.unlink(self.temp_image_path)
    
    def create_test_image(self):
        """Create a test image for testing"""
        # Create a simple test image with some patterns
        img = np.zeros((300, 400, 3), dtype=np.uint8)
        
        # Add some colored regions to simulate different waste types
        img[50:150, 50:150] = [255, 255, 255]  # White region (plastic)
        img[200:250, 100:200] = [128, 128, 128]  # Gray region (metal)
        img[100:200, 250:350] = [0, 255, 0]  # Green region (organic)
        
        return img
    
    def test_preprocess_image(self):
        """Test image preprocessing"""
        img_batch, original_img = self.ml_detector.preprocess_image(self.temp_image_path)
        
        self.assertEqual(img_batch.shape[0], 1)  # Batch dimension
        self.assertEqual(img_batch.shape[1], 224)  # Height
        self.assertEqual(img_batch.shape[2], 224)  # Width
        self.assertEqual(img_batch.shape[3], 3)  # Channels
        
        # Check normalization
        self.assertLessEqual(np.max(img_batch), 1.0)
        self.assertGreaterEqual(np.min(img_batch), 0.0)
    
    def test_predict_waste_composition(self):
        """Test waste composition prediction"""
        result = self.ml_detector.predict_waste_composition(self.temp_image_path)
        
        self.assertIsInstance(result, dict)
        self.assertIn('Plastic', result)
        self.assertIn('Metal', result)
        self.assertIn('Glass', result)
        
        # Check that percentages sum to 100
        total = sum(result.values())
        self.assertAlmostEqual(total, 100.0, places=1)
        
        # Check that all values are positive
        for value in result.values():
            self.assertGreaterEqual(value, 0)
    
    def test_fallback_analysis(self):
        """Test fallback analysis when ML model is not available"""
        result = self.ml_detector.fallback_analysis(self.temp_image_path)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 8)  # 8 waste categories
        self.assertAlmostEqual(sum(result.values()), 100.0, places=1)

class TestAdvancedImageProcessing(unittest.TestCase):
    """Test advanced image processing techniques"""
    
    def setUp(self):
        """Set up test image"""
        self.test_image = self.create_test_image()
        self.temp_image_path = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False).name
        cv2.imwrite(self.temp_image_path, self.test_image)
    
    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_image_path):
            os.unlink(self.temp_image_path)
    
    def create_test_image(self):
        """Create a test image with water quality indicators"""
        img = np.zeros((300, 400, 3), dtype=np.uint8)
        
        # Add brownish tint for turbidity
        img[:, :] = [139, 69, 19]  # Brown color
        
        # Add some bright spots for foam
        img[50:100, 50:100] = [255, 255, 255]
        img[150:200, 200:250] = [255, 255, 255]
        
        return img
    
    def test_detect_water_quality_indicators(self):
        """Test water quality detection"""
        indicators = AdvancedImageProcessing.detect_water_quality_indicators(self.temp_image_path)
        
        self.assertIsInstance(indicators, dict)
        self.assertIn('turbidity_visual', indicators)
        self.assertIn('color_clarity', indicators)
        self.assertIn('foam_presence', indicators)
        self.assertIn('oil_sheen', indicators)
        self.assertIn('suspended_solids', indicators)
        
        # Check that values are reasonable
        for key, value in indicators.items():
            self.assertIsInstance(value, (int, float))
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)
    
    def test_estimate_turbidity(self):
        """Test turbidity estimation"""
        hsv = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2HSV)
        turbidity = AdvancedImageProcessing.estimate_turbidity(hsv)
        
        self.assertIsInstance(turbidity, (int, float))
        self.assertGreaterEqual(turbidity, 0)
        self.assertLessEqual(turbidity, 100)
    
    def test_detect_foam(self):
        """Test foam detection"""
        foam_score = AdvancedImageProcessing.detect_foam(self.test_image)
        
        self.assertIsInstance(foam_score, (int, float))
        self.assertGreaterEqual(foam_score, 0)
        self.assertLessEqual(foam_score, 100)

class TestPredictiveAnalytics(unittest.TestCase):
    """Test predictive analytics functionality"""
    
    def setUp(self):
        """Set up predictive analytics"""
        self.predictive_analytics = PredictiveAnalytics()
        
        # Create historical data
        self.historical_data = []
        for i in range(30):
            self.historical_data.append({
                'hour': i % 24,
                'day_of_week': (i // 24) % 7,
                'month': 1,
                'temperature': 20 + (i % 10),
                'rainfall': np.random.random() * 5,
                'previous_wwi': 40 + np.random.random() * 20,
                'previous_wqi': 50 + np.random.random() * 20,
                'current_wwi': 42 + np.random.random() * 18
            })
    
    def test_train_pollution_forecast(self):
        """Test training pollution forecast model"""
        self.predictive_analytics.train_pollution_forecast(self.historical_data)
        
        self.assertIn('wwi_forecast', self.predictive_analytics.models)
        self.assertIsNotNone(self.predictive_analytics.models['wwi_forecast']['model'])
        self.assertIsNotNone(self.predictive_analytics.models['wwi_forecast']['scaler'])
    
    def test_predict_pollution_trend(self):
        """Test pollution trend prediction"""
        # Train model first
        self.predictive_analytics.train_pollution_forecast(self.historical_data)
        
        # Make prediction
        current_conditions = {
            'hour': 12,
            'day_of_week': 3,
            'month': 1,
            'temperature': 22,
            'rainfall': 2.5,
            'previous_wwi': 45.0,
            'previous_wqi': 55.0
        }
        
        prediction = self.predictive_analytics.predict_pollution_trend(current_conditions)
        
        if prediction:  # Only test if prediction succeeded
            self.assertIn('predicted_wwi', prediction)
            self.assertIn('confidence', prediction)
            self.assertIn('trend', prediction)
            self.assertIsInstance(prediction['predicted_wwi'], (int, float))
            self.assertIn(prediction['trend'], ['increasing', 'decreasing'])

class TestAPIEndpoints(unittest.TestCase):
    """Test API endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.client = TestClient(app)
        
        # Create test image
        self.test_image = self.create_test_image()
        self.temp_image_path = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False).name
        cv2.imwrite(self.temp_image_path, self.test_image)
    
    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.temp_image_path):
            os.unlink(self.temp_image_path)
    
    def create_test_image(self):
        """Create a test image"""
        img = np.zeros((300, 400, 3), dtype=np.uint8)
        img[:, :] = [100, 150, 200]  # Blue-ish color for water
        return img
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("message", data)
        self.assertIn("version", data)
        self.assertEqual(data["version"], "2.0.0")
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("database", data)
        self.assertIn("ml_models", data)
    
    def test_analyze_endpoint(self):
        """Test analysis endpoint"""
        # This would require authentication in production
        # For testing, we'll mock the authentication
        
        with patch('api_server.verify_token') as mock_auth:
            mock_auth.return_value = "test_user"
            
            analysis_data = {
                "image_path": self.temp_image_path,
                "location": "Test River",
                "latitude": 51.5074,
                "longitude": -0.1278,
                "user_id": 1
            }
            
            response = self.client.post("/api/analyze", json=analysis_data)
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertIn("id", data)
            self.assertIn("waste_composition", data)
            self.assertIn("wwi_score", data)
            self.assertIn("wqi_score", data)
            self.assertIn("river_status", data)
    
    def test_upload_analyze_endpoint(self):
        """Test upload and analyze endpoint"""
        with patch('api_server.verify_token') as mock_auth:
            mock_auth.return_value = "test_user"
            
            with open(self.temp_image_path, 'rb') as f:
                files = {'file': ('test.jpg', f, 'image/jpeg')}
                data = {
                    'location': 'Test River',
                    'latitude': '51.5074',
                    'longitude': '-0.1278'
                }
                
                response = self.client.post("/api/analyze/upload", files=files, data=data)
                self.assertEqual(response.status_code, 200)
                
                result = response.json()
                self.assertIn("id", result)
                self.assertIn("waste_composition", result)
    
    def test_trends_endpoint(self):
        """Test trends endpoint"""
        with patch('api_server.verify_token') as mock_auth:
            mock_auth.return_value = "test_user"
            
            response = self.client.get("/api/trends?days=30")
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertIn("period_days", data)
            self.assertIn("trends", data)
            self.assertIn("summary", data)
    
    def test_dashboard_stats_endpoint(self):
        """Test dashboard statistics endpoint"""
        with patch('api_server.verify_token') as mock_auth:
            mock_auth.return_value = "test_user"
            
            response = self.client.get("/api/dashboard/stats")
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertIn("total_analyses", data)
            self.assertIn("avg_wwi", data)
            self.assertIn("avg_wqi", data)
            self.assertIn("active_alerts", data)

class TestPerformance(unittest.TestCase):
    """Performance and load testing"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.ml_detector = WasteDetectionML()
        
        # Create multiple test images
        self.test_images = []
        for i in range(10):
            img = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
            temp_path = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False).name
            cv2.imwrite(temp_path, img)
            self.test_images.append(temp_path)
    
    def tearDown(self):
        """Clean up test images"""
        for img_path in self.test_images:
            if os.path.exists(img_path):
                os.unlink(img_path)
    
    def test_ml_prediction_performance(self):
        """Test ML prediction performance"""
        import time
        
        start_time = time.time()
        
        for img_path in self.test_images:
            result = self.ml_detector.predict_waste_composition(img_path)
            self.assertIsInstance(result, dict)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_image = total_time / len(self.test_images)
        
        # Performance requirement: should process each image in under 2 seconds
        self.assertLess(avg_time_per_image, 2.0, 
                       f"Average processing time {avg_time_per_image:.2f}s exceeds 2.0s limit")
    
    def test_database_performance(self):
        """Test database operation performance"""
        import time
        
        db_manager = DatabaseManager(db_type="sqlite", connection_params={
            'database': ':memory:'
        })
        
        # Test batch insert performance
        start_time = time.time()
        
        records = []
        for i in range(100):
            record = AnalysisRecord(
                image_path=f"test_{i}.jpg",
                location=f"Location {i}",
                waste_composition={"Plastic": 25.0, "Metal": 15.0},
                wwi_score=40.0 + i,
                wqi_score=60.0 - i,
                river_status="Moderately Polluted"
            )
            records.append(record)
        
        # Insert all records
        for record in records:
            db_manager.save_analysis(record)
        
        end_time = time.time()
        insert_time = end_time - start_time
        
        # Should insert 100 records in under 1 second
        self.assertLess(insert_time, 1.0, 
                       f"Batch insert time {insert_time:.2f}s exceeds 1.0s limit")
        
        # Test query performance
        start_time = time.time()
        trends = db_manager.get_pollution_trends(days=30)
        end_time = time.time()
        query_time = end_time - start_time
        
        # Query should complete in under 0.5 seconds
        self.assertLess(query_time, 0.5, 
                       f"Query time {query_time:.2f}s exceeds 0.5s limit")
        
        db_manager.close()

class TestIntegration(unittest.TestCase):
    """Integration tests for the complete system"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.db_manager = DatabaseManager(db_type="sqlite", connection_params={
            'database': ':memory:'
        })
        self.ml_detector = WasteDetectionML()
        
        # Create test image
        self.test_image = np.random.randint(0, 255, (300, 400, 3), dtype=np.uint8)
        self.temp_image_path = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False).name
        cv2.imwrite(self.temp_image_path, self.test_image)
    
    def tearDown(self):
        """Clean up test environment"""
        self.db_manager.close()
        if os.path.exists(self.temp_image_path):
            os.unlink(self.temp_image_path)
    
    def test_complete_analysis_workflow(self):
        """Test complete analysis workflow from image to database"""
        # Step 1: Analyze image with ML
        waste_composition = self.ml_detector.predict_waste_composition(self.temp_image_path)
        self.assertIsInstance(waste_composition, dict)
        
        # Step 2: Calculate WWI and WQI
        wwi_score = sum(
            waste_composition.get(cat, 0) * weight 
            for cat, weight in self.ml_detector.waste_risk_weights.items()
        ) / 100
        wqi_score = 45.0 + (wwi_score * 0.3)  # Simplified calculation
        
        # Step 3: Determine river status
        if wqi <= 25 and wwi < 20:
            river_status = "Clean"
        elif wqi <= 50 and wwi < 40:
            river_status = "Moderately Polluted"
        elif wqi <= 75 and wwi < 70:
            river_status = "Polluted"
        else:
            river_status = "Severely Polluted"
        
        # Step 4: Save to database
        record = AnalysisRecord(
            image_path=self.temp_image_path,
            location="Integration Test River",
            latitude=51.5074,
            longitude=-0.1278,
            waste_composition=waste_composition,
            wwi_score=wwi_score,
            wqi_score=wqi_score,
            river_status=river_status
        )
        
        record_id = self.db_manager.save_analysis(record)
        self.assertIsInstance(record_id, int)
        self.assertGreater(record_id, 0)
        
        # Step 5: Retrieve and verify
        retrieved = self.db_manager.get_analysis(record_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['location'], "Integration Test River")
        self.assertEqual(retrieved['wwi_score'], wwi_score)
        self.assertEqual(retrieved['wqi_score'], wqi_score)
        self.assertEqual(retrieved['river_status'], river_status)
        
        # Step 6: Test trends calculation
        trends = self.db_manager.get_pollution_trends(days=30)
        self.assertIn('dates', trends)
        self.assertIn('avg_wwi', trends)
        self.assertIn('avg_wqi', trends)

# Test runner
if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestDatabaseManager,
        TestWasteDetectionML,
        TestAdvancedImageProcessing,
        TestPredictiveAnalytics,
        TestAPIEndpoints,
        TestPerformance,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*50}")
    print(f"Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"{'='*50}")
    
    # Exit with appropriate code
    exit_code = 0 if result.wasSuccessful() else 1
    exit(exit_code)
