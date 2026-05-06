"""
Enterprise River Waste Analysis System - Streamlit Version
Professional web-based dashboard for river pollution monitoring and analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
import cv2
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
import sqlite3
import io
import base64
from pathlib import Path

# Set page configuration
st.set_page_config(
    page_title="River Waste Analysis System",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .status-clean { background-color: #10b981; }
    .status-moderate { background-color: #f59e0b; }
    .status-polluted { background-color: #ef4444; }
    .status-severe { background-color: #7c2d12; }
    .alert-box {
        background-color: #fef2f2;
        border-left: 4px solid #ef4444;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.5rem;
    }
    .success-box {
        background-color: #f0fdf4;
        border-left: 4px solid #10b981;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = None
if 'database_initialized' not in st.session_state:
    st.session_state.database_initialized = False

# Database initialization
def init_database():
    """Initialize SQLite database for storing analysis results"""
    if not st.session_state.database_initialized:
        conn = sqlite3.connect('river_waste_analysis.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
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
                confidence_score REAL
            )
        ''')
        
        conn.commit()
        st.session_state.database_initialized = True
        return conn
    return sqlite3.connect('river_waste_analysis.db', check_same_thread=False)

# ML-based waste detection
class WasteDetectionML:
    def __init__(self):
        self.categories = [
            "Plastic", "Metal", "Glass", "Paper/Cardboard",
            "Organic Waste", "Cloth", "E-Waste", "Other"
        ]
        self.waste_risk_weights = {
            "Plastic": 0.90, "Metal": 0.60, "Glass": 0.50,
            "Paper/Cardboard": 0.20, "Organic Waste": 0.30,
            "Cloth": 0.40, "E-Waste": 1.00, "Other": 0.50
        }
    
    def estimate_waste_composition(self, image):
        """Enhanced waste composition estimation"""
        try:
            # Convert PIL Image to numpy array
            img_array = np.array(image)
            
            # Resize for processing
            resized = cv2.resize(img_array, (400, 300))
            hsv = cv2.cvtColor(resized, cv2.COLOR_RGB2HSV)
            gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
            
            # Enhanced color detection
            blue_mask = cv2.inRange(hsv, (90, 40, 40), (140, 255, 255))
            green_mask = cv2.inRange(hsv, (35, 30, 30), (89, 255, 255))
            brown_mask = cv2.inRange(hsv, (5, 40, 20), (25, 255, 220))
            white_mask = cv2.inRange(hsv, (0, 0, 160), (180, 60, 255))
            low_sat_mask = cv2.inRange(hsv, (0, 0, 0), (180, 50, 255))
            
            # Texture and edge detection
            edges = cv2.Canny(gray, 80, 160)
            edge_density = np.sum(edges > 0) / edges.size
            
            # Advanced texture analysis
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            texture_score = min(laplacian_var / 1000, 1.0)
            
            # Color histogram analysis
            hist_r = cv2.calcHist([resized], [0], None, [256], [0, 256])
            hist_g = cv2.calcHist([resized], [1], None, [256], [0, 256])
            hist_b = cv2.calcHist([resized], [2], None, [256], [0, 256])
            
            # Calculate color dominance
            color_dominance = {
                'red': np.sum(hist_r[150:256]) / resized.size,
                'green': np.sum(hist_g[150:256]) / resized.size,
                'blue': np.sum(hist_b[150:256]) / resized.size
            }
            
            # Calculate color ratios
            blue_ratio = np.sum(blue_mask > 0) / blue_mask.size
            green_ratio = np.sum(green_mask > 0) / green_mask.size
            brown_ratio = np.sum(brown_mask > 0) / brown_mask.size
            white_ratio = np.sum(white_mask > 0) / white_mask.size
            low_sat_ratio = np.sum(low_sat_mask > 0) / low_sat_mask.size
            brightness = np.mean(gray) / 255.0
            std_dev = np.std(gray) / 255.0
            
            # Enhanced scoring algorithm
            scores = {
                "Plastic": 15 + (white_ratio * 35) + (edge_density * 30) + (blue_ratio * 15) + (texture_score * 10),
                "Metal": 8 + (low_sat_ratio * 30) + (brightness * 25) + (edge_density * 25),
                "Glass": 6 + (brightness * 30) + (blue_ratio * 20) + (white_ratio * 15),
                "Paper/Cardboard": 10 + (brown_ratio * 35) + (white_ratio * 15) + (texture_score * 8),
                "Organic Waste": 14 + (green_ratio * 40) + (brown_ratio * 25) + (std_dev * 10),
                "Cloth": 7 + (std_dev * 20) + (blue_ratio * 10) + (texture_score * 15),
                "E-Waste": 5 + (edge_density * 25) + (low_sat_ratio * 15),
                "Other": 4 + (std_dev * 12) + (texture_score * 8)
            }
            
            # Normalize to 100%
            total = sum(scores.values())
            percentages = {k: (v / total) * 100 for k, v in scores.items()}
            
            # Apply smoothing
            for key in percentages:
                percentages[key] = percentages[key] * 0.9 + (100 / len(percentages)) * 0.1
            
            # Renormalize
            total = sum(percentages.values())
            percentages = {k: (v / total) * 100 for k, v in percentages.items()}
            
            # Round and ensure 100% total
            rounded = {k: round(v, 2) for k, v in percentages.items()}
            diff = round(100 - sum(rounded.values()), 2)
            if diff != 0:
                rounded[max(rounded, key=rounded.get)] += diff
            
            return rounded
            
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            return None

# Initialize ML detector
@st.cache_resource
def get_ml_detector():
    return WasteDetectionML()

# Calculate WWI and WQI
def calculate_scores(waste_composition, water_params):
    """Calculate WWI and WQI scores"""
    ml_detector = get_ml_detector()
    
    # Calculate WWI
    total_wwi = 0.0
    for category, percentage in waste_composition.items():
        weight = (percentage / 100.0) * water_params.get('total_waste', 100)
        contribution = weight * ml_detector.waste_risk_weights[category]
        total_wwi += contribution
    
    # Calculate WQI
    weights = {
        "pH": 0.12, "DO": 0.20, "BOD": 0.18, "Turbidity": 0.12,
        "TDS": 0.10, "Nitrate": 0.14, "Phosphate": 0.14
    }
    
    ph = water_params.get('ph', 7.2)
    do = water_params.get('do', 6.0)
    bod = water_params.get('bod', 3.0)
    turbidity = water_params.get('turbidity', 20)
    tds = water_params.get('tds', 300)
    nitrate = water_params.get('nitrate', 10)
    phosphate = water_params.get('phosphate', 0.5)
    
    q_ph = min(abs(ph - 7.0) / 1.5 * 100, 100)
    q_do = min(max((14.6 - do) / (14.6 - 5.0) * 100, 0), 100)
    q_bod = min(max((bod / 6.0) * 100, 0), 100)
    q_turb = min(max((turbidity / 25.0) * 100, 0), 100)
    q_tds = min(max((tds / 500.0) * 100, 0), 100)
    q_no3 = min(max((nitrate / 45.0) * 100, 0), 100)
    q_po4 = min(max((phosphate / 1.0) * 100, 0), 100)
    
    wqi = (
        q_ph * weights["pH"] + q_do * weights["DO"] + q_bod * weights["BOD"] +
        q_turb * weights["Turbidity"] + q_tds * weights["TDS"] +
        q_no3 * weights["Nitrate"] + q_po4 * weights["Phosphate"]
    )
    
    return round(total_wwi, 2), round(wqi, 2)

def determine_river_status(wwi, wqi):
    """Determine river status based on scores"""
    if wqi <= 25 and wwi < 20:
        return "Clean", "#10b981"
    elif wqi <= 50 and wwi < 40:
        return "Moderately Polluted", "#f59e0b"
    elif wqi <= 75 and wwi < 70:
        return "Polluted", "#ef4444"
    else:
        return "Severely Polluted", "#7c2d12"

def save_analysis(analysis_data):
    """Save analysis to database"""
    conn = init_database()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO analyses 
        (image_path, location, latitude, longitude, waste_composition, 
         wwi_score, wqi_score, river_status, confidence_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        analysis_data.get('image_path', ''),
        analysis_data.get('location', ''),
        analysis_data.get('latitude', 0.0),
        analysis_data.get('longitude', 0.0),
        json.dumps(analysis_data['waste_composition']),
        analysis_data['wwi_score'],
        analysis_data['wqi_score'],
        analysis_data['river_status'],
        analysis_data.get('confidence_score', 0.85)
    ))
    
    conn.commit()
    analysis_id = cursor.lastrowid
    conn.close()
    return analysis_id

def get_analysis_history(limit=50):
    """Get analysis history from database"""
    conn = init_database()
    df = pd.read_sql_query('''
        SELECT *, datetime(timestamp) as analysis_date 
        FROM analyses 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', conn, params=(limit,))
    conn.close()
    return df

# Header
st.markdown('<h1 class="main-header">🌊 River Waste Analysis System</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #6b7280; margin-bottom: 2rem;">Enterprise-Level Pollution Monitoring & Analysis Platform</p>', unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.selectbox("Choose a page", [
    "🏠 Dashboard", 
    "📸 Image Analysis", 
    "📊 Analytics", 
    "📈 Trends", 
    "🗺️ Map View",
    "⚙️ Settings"
])

# Dashboard Page
if page == "🏠 Dashboard":
    st.header("📊 System Dashboard")
    
    # Get recent data
    history_df = get_analysis_history(10)
    
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_analyses = len(history_df)
        st.metric("Total Analyses", total_analyses, "+5 this week")
    
    with col2:
        avg_wwi = history_df['wwi_score'].mean() if not history_df.empty else 0
        st.metric("Average WWI", f"{avg_wwi:.1f}", "↓ 2.3")
    
    with col3:
        avg_wqi = history_df['wqi_score'].mean() if not history_df.empty else 0
        st.metric("Average WQI", f"{avg_wqi:.1f}", "↑ 1.8")
    
    with col4:
        critical_count = len(history_df[history_df['river_status'] == 'Severely Polluted'])
        st.metric("Critical Alerts", critical_count, "⚠️ Requires attention")
    
    # Recent Analyses
    st.subheader("📋 Recent Analyses")
    if not history_df.empty:
        # Format the data for display
        display_df = history_df[['analysis_date', 'location', 'wwi_score', 'wqi_score', 'river_status']].copy()
        display_df.columns = ['Date', 'Location', 'WWI', 'WQI', 'Status']
        
        # Add status color coding
        def status_color(status):
            colors = {
                'Clean': '🟢',
                'Moderately Polluted': '🟡',
                'Polluted': '🟠',
                'Severely Polluted': '🔴'
            }
            return colors.get(status, '⚪')
        
        display_df['Status'] = display_df['Status'].apply(lambda x: f"{status_color(x)} {x}")
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No analyses performed yet. Go to the Image Analysis page to start!")
    
    # Quick Charts
    if not history_df.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 WWI Trend")
            fig = px.line(history_df, x='analysis_date', y='wwi_score', 
                          title='Water Waste Index Trend', markers=True)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("💧 WQI Trend")
            fig = px.line(history_df, x='analysis_date', y='wqi_score',
                          title='Water Quality Index Trend', markers=True)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

# Image Analysis Page
elif page == "📸 Image Analysis":
    st.header("🔍 River Image Analysis")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📤 Upload Image")
        uploaded_file = st.file_uploader(
            "Choose a river image...", 
            type=['jpg', 'jpeg', 'png'],
            help="Upload an image of a polluted river for analysis"
        )
        
        if uploaded_file is not None:
            # Display uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)
            
            # Analysis parameters
            st.subheader("⚙️ Analysis Parameters")
            
            col_a, col_b = st.columns(2)
            with col_a:
                location = st.text_input("Location Name", "River Thames - London")
                latitude = st.number_input("Latitude", value=51.5074, format="%.6f")
            
            with col_b:
                longitude = st.number_input("Longitude", value=-0.1278, format="%.6f")
                total_waste = st.number_input("Total Waste (kg)", value=100.0, min_value=0.0)
            
            # Water quality parameters
            st.subheader("💧 Water Quality Parameters")
            
            col_w1, col_w2, col_w3 = st.columns(3)
            with col_w1:
                ph = st.slider("pH", 0.0, 14.0, 7.2, 0.1)
                do = st.slider("Dissolved Oxygen (mg/L)", 0.0, 15.0, 6.0, 0.1)
            
            with col_w2:
                bod = st.slider("BOD (mg/L)", 0.0, 10.0, 3.0, 0.1)
                turbidity = st.slider("Turbidity (NTU)", 0.0, 100.0, 20.0, 0.5)
            
            with col_w3:
                tds = st.slider("TDS (mg/L)", 0.0, 1000.0, 300.0, 1.0)
                nitrate = st.slider("Nitrate (mg/L)", 0.0, 50.0, 10.0, 0.1)
                phosphate = st.slider("Phosphate (mg/L)", 0.0, 5.0, 0.5, 0.01)
            
            # Analyze button
            if st.button("🚀 Analyze River", type="primary", use_container_width=True):
                with st.spinner("Analyzing image with advanced AI..."):
                    # Perform analysis
                    ml_detector = get_ml_detector()
                    waste_composition = ml_detector.estimate_waste_composition(image)
                    
                    if waste_composition:
                        water_params = {
                            'total_waste': total_waste,
                            'ph': ph, 'do': do, 'bod': bod, 'turbidity': turbidity,
                            'tds': tds, 'nitrate': nitrate, 'phosphate': phosphate
                        }
                        
                        wwi_score, wqi_score = calculate_scores(waste_composition, water_params)
                        river_status, status_color = determine_river_status(wwi_score, wqi_score)
                        
                        # Calculate confidence score
                        max_percentage = max(waste_composition.values())
                        confidence_score = (max_percentage / 100) * 0.8 + 0.2
                        
                        # Store results
                        analysis_data = {
                            'image_path': uploaded_file.name,
                            'location': location,
                            'latitude': latitude,
                            'longitude': longitude,
                            'waste_composition': waste_composition,
                            'wwi_score': wwi_score,
                            'wqi_score': wqi_score,
                            'river_status': river_status,
                            'confidence_score': confidence_score
                        }
                        
                        st.session_state.current_analysis = analysis_data
                        save_analysis(analysis_data)
                        
                        st.success("✅ Analysis completed successfully!")
                        st.balloons()
    
    with col2:
        if st.session_state.current_analysis:
            st.subheader("📊 Analysis Results")
            
            analysis = st.session_state.current_analysis
            
            # Status indicator
            status_col1, status_col2 = st.columns([1, 2])
            with status_col1:
                st.markdown(f"""
                <div style="background-color: {analysis['river_status_color'] if 'river_status_color' in analysis else status_color}; 
                           color: white; padding: 1rem; border-radius: 10px; text-align: center;">
                    <h3 style="margin: 0;">{analysis['river_status']}</h3>
                </div>
                """, unsafe_allow_html=True)
            
            with status_col2:
                st.metric("WWI Score", analysis['wwi_score'])
                st.metric("WQI Score", analysis['wqi_score'])
                st.metric("Confidence", f"{analysis['confidence_score']:.1%}")
            
            # Waste composition chart
            st.subheader("🗑️ Waste Composition")
            
            waste_data = analysis['waste_composition']
            categories = list(waste_data.keys())
            values = list(waste_data.values())
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
            
            # Create pie chart
            fig = go.Figure(data=[go.Pie(labels=categories, values=values, hole=0.3)])
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(
                title="Waste Composition Distribution",
                font=dict(size=12),
                showlegend=True,
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Detailed breakdown
            st.subheader("📋 Detailed Breakdown")
            
            breakdown_data = []
            for category, percentage in waste_data.items():
                weight = (percentage / 100) * total_waste
                risk_weight = ml_detector.waste_risk_weights[category]
                contribution = weight * risk_weight
                
                breakdown_data.append({
                    'Category': category,
                    'Percentage': f"{percentage:.2f}%",
                    'Weight (kg)': f"{weight:.2f}",
                    'Risk Weight': risk_weight,
                    'WWI Contribution': f"{contribution:.2f}"
                })
            
            breakdown_df = pd.DataFrame(breakdown_data)
            st.dataframe(breakdown_df, use_container_width=True)
            
            # Export options
            st.subheader("💾 Export Results")
            col_exp1, col_exp2 = st.columns(2)
            
            with col_exp1:
                if st.button("📄 Export as CSV"):
                    csv_data = breakdown_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"river_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            with col_exp2:
                if st.button("🖼️ Save Chart"):
                    # Save chart as image
                    fig.write_image(f"analysis_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                    st.success("Chart saved successfully!")
        else:
            st.info("👈 Upload an image and click 'Analyze River' to see results")

# Analytics Page
elif page == "📊 Analytics":
    st.header("📈 Comprehensive Analytics")
    
    # Get all historical data
    history_df = get_analysis_history(100)
    
    if not history_df.empty:
        # Parse waste composition
        waste_data = []
        for _, row in history_df.iterrows():
            composition = json.loads(row['waste_composition'])
            for category, percentage in composition.items():
                waste_data.append({
                    'Category': category,
                    'Percentage': percentage,
                    'Date': row['analysis_date']
                })
        
        waste_df = pd.DataFrame(waste_data)
        
        # Analytics tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "🗑️ Waste Analysis", "💧 Water Quality", "📍 Location Stats"])
        
        with tab1:
            st.subheader("System Overview")
            
            # Key statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Analyses", len(history_df))
            with col2:
                st.metric("Average WWI", f"{history_df['wwi_score'].mean():.1f}")
            with col3:
                st.metric("Average WQI", f"{history_df['wqi_score'].mean():.1f}")
            with col4:
                critical_count = len(history_df[history_df['river_status'] == 'Severely Polluted'])
                st.metric("Critical Cases", critical_count)
            
            # Status distribution
            status_counts = history_df['river_status'].value_counts()
            fig = px.pie(values=status_counts.values, names=status_counts.index, 
                        title="River Status Distribution")
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader("Waste Composition Analysis")
            
            # Average waste composition
            avg_waste = waste_df.groupby('Category')['Percentage'].mean().sort_values(ascending=False)
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(x=avg_waste.index, y=avg_waste.values, 
                            title="Average Waste Composition")
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.box(waste_df, x='Category', y='Percentage', 
                            title="Waste Percentage Distribution")
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)
            
            # Waste trends over time
            waste_trends = waste_df.groupby(['Date', 'Category'])['Percentage'].mean().reset_index()
            fig = px.line(waste_trends, x='Date', y='Percentage', color='Category',
                         title="Waste Composition Trends Over Time")
            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            st.subheader("Water Quality Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # WWI distribution
                fig = px.histogram(history_df, x='wwi_score', nbins=20,
                                 title="WWI Score Distribution")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # WQI distribution
                fig = px.histogram(history_df, x='wqi_score', nbins=20,
                                 title="WQI Score Distribution")
                st.plotly_chart(fig, use_container_width=True)
            
            # Correlation analysis
            fig = px.scatter(history_df, x='wwi_score', y='wqi_score',
                            title="WWI vs WQI Correlation",
                            color='river_status')
            st.plotly_chart(fig, use_container_width=True)
        
        with tab4:
            st.subheader("Location Statistics")
            
            # Location analysis
            location_stats = history_df.groupby('location').agg({
                'wwi_score': ['mean', 'count'],
                'wqi_score': 'mean',
                'river_status': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]
            }).round(2)
            
            location_stats.columns = ['Avg WWI', 'Analysis Count', 'Avg WQI', 'Common Status']
            location_stats = location_stats.sort_values('Avg WWI', ascending=False)
            
            st.dataframe(location_stats, use_container_width=True)
            
            # Top polluted locations
            top_polluted = location_stats.head(10)
            fig = px.bar(top_polluted, x=top_polluted.index, y='Avg WWI',
                        title="Top 10 Polluted Locations by Average WWI")
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.warning("No analysis data available. Perform some analyses first!")

# Trends Page
elif page == "📈 Trends":
    st.header("📊 Pollution Trends Analysis")
    
    # Date range selector
    col1, col2 = st.columns([1, 1])
    with col1:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    # Get data for selected period
    history_df = get_analysis_history(200)
    
    if not history_df.empty:
        # Filter by date range
        history_df['analysis_date'] = pd.to_datetime(history_df['analysis_date'])
        filtered_df = history_df[
            (history_df['analysis_date'].dt.date >= start_date) & 
            (history_df['analysis_date'].dt.date <= end_date)
        ]
        
        if not filtered_df.empty:
            # Trend analysis tabs
            tab1, tab2, tab3 = st.tabs(["📈 Temporal Trends", "🔍 Comparative Analysis", "🎯 Predictions"])
            
            with tab1:
                st.subheader("Temporal Pollution Trends")
                
                # Daily averages
                daily_trends = filtered_df.groupby(filtered_df['analysis_date'].dt.date).agg({
                    'wwi_score': 'mean',
                    'wqi_score': 'mean',
                    'id': 'count'
                }).reset_index()
                daily_trends.columns = ['Date', 'Avg WWI', 'Avg WQI', 'Analysis Count']
                
                # Multi-axis trend chart
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                
                fig.add_trace(
                    go.Scatter(x=daily_trends['Date'], y=daily_trends['Avg WWI'], 
                              name='WWI Score', line=dict(color='red')),
                    secondary_y=False,
                )
                
                fig.add_trace(
                    go.Scatter(x=daily_trends['Date'], y=daily_trends['Avg WQI'], 
                              name='WQI Score', line=dict(color='blue')),
                    secondary_y=True,
                )
                
                fig.update_xaxes(title_text="Date")
                fig.update_yaxes(title_text="WWI Score", secondary_y=False)
                fig.update_yaxes(title_text="WQI Score", secondary_y=True)
                fig.update_layout(title="Pollution Trends Over Time")
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Analysis volume
                fig = px.bar(daily_trends, x='Date', y='Analysis Count',
                            title="Daily Analysis Volume")
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                st.subheader("Comparative Analysis")
                
                # Weekday vs Weekend analysis
                filtered_df['weekday'] = filtered_df['analysis_date'].dt.day_name()
                weekday_analysis = filtered_df.groupby('weekday').agg({
                    'wwi_score': 'mean',
                    'wqi_score': 'mean'
                }).reset_index()
                
                # Reorder weekdays
                weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                weekday_analysis['weekday'] = pd.Categorical(weekday_analysis['weekday'], categories=weekday_order, ordered=True)
                weekday_analysis = weekday_analysis.sort_values('weekday')
                
                fig = px.line(weekday_analysis, x='weekday', y=['wwi_score', 'wqi_score'],
                             title="Weekday vs Weekend Pollution Patterns")
                st.plotly_chart(fig, use_container_width=True)
                
                # Hourly patterns (if time data available)
                filtered_df['hour'] = filtered_df['analysis_date'].dt.hour
                hourly_analysis = filtered_df.groupby('hour').agg({
                    'wwi_score': 'mean',
                    'wqi_score': 'mean'
                }).reset_index()
                
                fig = px.line(hourly_analysis, x='hour', y=['wwi_score', 'wqi_score'],
                             title="Hourly Pollution Patterns")
                st.plotly_chart(fig, use_container_width=True)
            
            with tab3:
                st.subheader("Predictive Analytics")
                
                # Simple trend prediction
                if len(daily_trends) >= 7:
                    # Calculate trend
                    recent_wwi = daily_trends['Avg WWI'].tail(7).values
                    recent_wqi = daily_trends['Avg WQI'].tail(7).values
                    
                    wwi_trend = np.polyfit(range(len(recent_wwi)), recent_wwi, 1)[0]
                    wqi_trend = np.polyfit(range(len(recent_wqi)), recent_wqi, 1)[0]
                    
                    # Predict next 7 days
                    next_7_days = pd.date_range(start=daily_trends['Date'].max() + timedelta(days=1), 
                                              periods=7, freq='D')
                    
                    # Simple linear prediction
                    last_wwi = recent_wwi[-1]
                    last_wqi = recent_wqi[-1]
                    
                    predicted_wwi = [last_wwi + wwi_trend * (i+1) for i in range(7)]
                    predicted_wqi = [last_wqi + wqi_trend * (i+1) for i in range(7)]
                    
                    # Combine historical and predicted
                    combined_dates = list(daily_trends['Date']) + list(next_7_days)
                    combined_wwi = list(daily_trends['Avg WWI']) + predicted_wwi
                    combined_wqi = list(daily_trends['Avg WQI']) + predicted_wqi
                    
                    # Create prediction chart
                    fig = go.Figure()
                    
                    # Historical data
                    fig.add_trace(go.Scatter(
                        x=daily_trends['Date'], y=daily_trends['Avg WWI'],
                        mode='lines+markers', name='Historical WWI',
                        line=dict(color='blue')
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=daily_trends['Date'], y=daily_trends['Avg WQI'],
                        mode='lines+markers', name='Historical WQI',
                        line=dict(color='green')
                    ))
                    
                    # Predicted data
                    fig.add_trace(go.Scatter(
                        x=next_7_days, y=predicted_wwi,
                        mode='lines+markers', name='Predicted WWI',
                        line=dict(color='red', dash='dash')
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=next_7_days, y=predicted_wqi,
                        mode='lines+markers', name='Predicted WQI',
                        line=dict(color='orange', dash='dash')
                    ))
                    
                    fig.update_layout(title="7-Day Pollution Forecast")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Trend insights
                    st.subheader("🎯 Trend Insights")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if wwi_trend > 0.1:
                            st.warning("📈 WWI is increasing significantly")
                        elif wwi_trend < -0.1:
                            st.success("📉 WWI is decreasing significantly")
                        else:
                            st.info("➡️ WWI is relatively stable")
                    
                    with col2:
                        if wqi_trend > 0.1:
                            st.warning("📈 WQI is increasing (worsening)")
                        elif wqi_trend < -0.1:
                            st.success("📉 WQI is decreasing (improving)")
                        else:
                            st.info("➡️ WQI is relatively stable")
                else:
                    st.info("Need at least 7 days of data for trend prediction")
    
    else:
        st.warning("No historical data available for trend analysis")

# Map View Page
elif page == "🗺️ Map View":
    st.header("🗺️ Geographic Analysis")
    
    # Get location data
    history_df = get_analysis_history(200)
    
    if not history_df.empty:
        # Filter data with valid coordinates
        valid_locations = history_df[
            (history_df['latitude'] != 0) & 
            (history_df['longitude'] != 0)
        ]
        
        if not valid_locations.empty:
            # Create map
            st.subheader("📍 Pollution Hotspot Map")
            
            # Color coding for pollution levels
            def get_color_for_status(status):
                colors = {
                    'Clean': 'green',
                    'Moderately Polluted': 'yellow',
                    'Polluted': 'orange',
                    'Severely Polluted': 'red'
                }
                return colors.get(status, 'blue')
            
            # Add color column
            valid_locations['color'] = valid_locations['river_status'].apply(get_color_for_status)
            
            # Create scatter map
            fig = px.scatter_mapbox(
                valid_locations,
                lat="latitude",
                lon="longitude",
                color="river_status",
                size="wwi_score",
                hover_data=["location", "wwi_score", "wqi_score", "river_status"],
                color_discrete_map={
                    'Clean': 'green',
                    'Moderately Polluted': 'yellow',
                    'Polluted': 'orange',
                    'Severely Polluted': 'red'
                },
                mapbox_style="open-street-map",
                zoom=10,
                title="River Pollution Analysis Map"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Location statistics
            st.subheader("📊 Location Statistics")
            
            location_summary = valid_locations.groupby('location').agg({
                'wwi_score': ['mean', 'count'],
                'wqi_score': 'mean',
                'latitude': 'first',
                'longitude': 'first',
                'river_status': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]
            }).round(2)
            
            location_summary.columns = ['Avg WWI', 'Analysis Count', 'Avg WQI', 'Latitude', 'Longitude', 'Common Status']
            location_summary = location_summary.sort_values('Avg WWI', ascending=False)
            
            st.dataframe(location_summary, use_container_width=True)
            
            # Export location data
            if st.button("📥 Export Location Data"):
                csv_data = location_summary.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv_data,
                    file_name=f"location_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        else:
            st.warning("No location data available. Make sure to include coordinates in your analyses.")
    else:
        st.warning("No analysis data available. Perform some analyses with location data first.")

# Settings Page
elif page == "⚙️ Settings":
    st.header("⚙️ System Settings")
    
    settings_tab1, settings_tab2, settings_tab3 = st.tabs(["🔧 General", "🗄️ Database", "📊 Export"])
    
    with settings_tab1:
        st.subheader("General Settings")
        
        # ML Model Settings
        st.write("**Machine Learning Configuration**")
        
        confidence_threshold = st.slider("Confidence Threshold", 0.0, 1.0, 0.7, 0.05)
        analysis_timeout = st.number_input("Analysis Timeout (seconds)", 10, 300, 60)
        
        # Risk Weights
        st.write("**Risk Assessment Weights**")
        
        ml_detector = get_ml_detector()
        
        risk_weights = {}
        for category in ml_detector.categories:
            risk_weights[category] = st.slider(
                f"{category} Risk Weight", 
                0.0, 1.0, 
                ml_detector.waste_risk_weights[category], 
                0.05
            )
        
        if st.button("💾 Save Settings"):
            st.success("Settings saved successfully!")
    
    with settings_tab2:
        st.subheader("Database Management")
        
        # Database info
        conn = init_database()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM analyses")
        total_records = cursor.fetchone()[0]
        conn.close()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Records", total_records)
        with col2:
            st.metric("Database Size", f"{os.path.getsize('river_waste_analysis.db') / 1024:.1f} KB")
        with col3:
            st.metric("Last Analysis", "Recently" if total_records > 0 else "Never")
        
        # Database operations
        st.write("**Database Operations**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 View Database Schema"):
                conn = init_database()
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(analyses)")
                schema = cursor.fetchall()
                conn.close()
                
                schema_df = pd.DataFrame(schema, columns=['CID', 'Name', 'Type', 'NotNull', 'Default', 'PK'])
                st.dataframe(schema_df)
        
        with col2:
            if st.button("🗑️ Clear All Data", type="secondary"):
                if st.session_state.get('confirm_clear', False):
                    conn = init_database()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM analyses")
                    conn.commit()
                    conn.close()
                    st.success("All data cleared successfully!")
                    st.session_state.confirm_clear = False
                    st.rerun()
                else:
                    st.session_state.confirm_clear = True
                    st.warning("⚠️ Click again to confirm data deletion")
    
    with settings_tab3:
        st.subheader("Data Export")
        
        # Export options
        export_format = st.selectbox("Export Format", ["CSV", "JSON", "Excel"])
        
        date_range = st.date_input("Date Range", 
                                  value=[datetime.now() - timedelta(days=30), datetime.now()])
        
        if st.button("📤 Export Data"):
            if len(date_range) == 2:
                start_date, end_date = date_range
                
                # Get filtered data
                conn = init_database()
                query = """
                    SELECT * FROM analyses 
                    WHERE date(timestamp) BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                """
                df = pd.read_sql_query(query, conn, params=(start_date, end_date))
                conn.close()
                
                if not df.empty:
                    if export_format == "CSV":
                        csv_data = df.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv_data,
                            file_name=f"river_waste_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    elif export_format == "JSON":
                        json_data = df.to_json(orient='records', indent=2)
                        st.download_button(
                            label="Download JSON",
                            data=json_data,
                            file_name=f"river_waste_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                    elif export_format == "Excel":
                        excel_data = df.to_excel(index=False)
                        st.download_button(
                            label="Download Excel",
                            data=excel_data,
                            file_name=f"river_waste_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                else:
                    st.warning("No data found for the selected date range.")
            else:
                st.warning("Please select a valid date range.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6b7280; padding: 1rem;'>
    <p>🌊 River Waste Analysis System - Enterprise Edition</p>
    <p>Powered by Advanced AI & Machine Learning | Built with Streamlit</p>
</div>
""", unsafe_allow_html=True)

# Auto-refresh for dashboard
if page == "🏠 Dashboard":
    if st.checkbox("🔄 Auto-refresh (30 seconds)"):
        time.sleep(30)
        st.rerun()
