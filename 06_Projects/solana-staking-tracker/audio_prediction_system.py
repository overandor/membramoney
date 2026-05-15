#!/usr/bin/env python3
"""
AUDIO PREDICTION SYSTEM - THOUGHT PREDICTION ENGINE
Records and predicts user thoughts based on working cycles and environmental sounds
Advanced audio analysis with LM integration for thought prediction
"""

import asyncio
import json
import time
import logging
import threading
import queue
import numpy as np
import pyaudio
import wave
import os
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import speech_recognition as sr
import librosa
import soundfile as sf
from flask import Flask, render_template_string, jsonify, request
import webbrowser
import requests
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('audio_prediction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class AudioSegment:
    """Audio segment with metadata"""
    segment_id: str
    timestamp: datetime
    duration: float
    audio_data: np.ndarray
    sample_rate: int
    transcription: Optional[str] = None
    predicted_thought: Optional[str] = None
    confidence: float = 0.0
    environmental_context: Dict = None

@dataclass
class ThoughtPattern:
    """Thought pattern prediction"""
    pattern_id: str
    audio_signature: np.ndarray
    likely_thoughts: List[str]
    confidence_scores: List[float]
    context_keywords: List[str]
    cycle_phase: str  # 'focus', 'break', 'inspiration', 'frustration'
    prediction_accuracy: float = 0.0

class AudioPredictionSystem:
    """Advanced audio prediction and thought analysis system"""
    
    def __init__(self):
        self.recording = False
        self.audio_queue = queue.Queue()
        self.prediction_queue = queue.Queue()
        self.segments: List[AudioSegment] = []
        self.patterns: List[ThoughtPattern] = []
        
        # Audio configuration
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 44100
        self.CHUNK = 1024
        self.RECORD_SECONDS = 30  # 30-second segments
        
        # Pattern recognition
        self.audio_history = deque(maxlen=1000)
        self.transcription_history = deque(maxlen=500)
        self.prediction_history = deque(maxlen=200)
        
        # Analysis parameters
        self.min_prediction_confidence = 0.7
        self.pattern_similarity_threshold = 0.8
        
        # Database
        self.db_path = "audio_prediction.db"
        self.init_database()
        
        # Initialize components
        self.recognizer = sr.Recognizer()
        
        logger.info("🎙️ Audio Prediction System Initialized")
        logger.info(f"🔊 Sample Rate: {self.RATE} Hz")
        logger.info(f"⏱️  Segment Duration: {self.RECORD_SECONDS}s")
        logger.info(f"🧠 Prediction Confidence: {self.min_prediction_confidence}")
    
    def init_database(self):
        """Initialize prediction database"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audio_segments (
                segment_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                duration REAL NOT NULL,
                transcription TEXT,
                predicted_thought TEXT,
                confidence REAL DEFAULT 0.0,
                environmental_context TEXT,
                audio_file_path TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thought_patterns (
                pattern_id TEXT PRIMARY KEY,
                audio_signature TEXT NOT NULL,
                likely_thoughts TEXT NOT NULL,
                confidence_scores TEXT NOT NULL,
                context_keywords TEXT NOT NULL,
                cycle_phase TEXT NOT NULL,
                prediction_accuracy REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prediction_accuracy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                segment_id TEXT NOT NULL,
                predicted_thought TEXT,
                actual_thought TEXT,
                accuracy_score REAL,
                timestamp TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def start_continuous_recording(self) -> str:
        """Start continuous audio recording"""
        self.recording = True
        
        session_id = f"audio_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create session directory
        session_dir = f"audio_sessions/{session_id}"
        os.makedirs(session_dir, exist_ok=True)
        
        logger.info(f"🎬 Starting continuous recording: {session_id}")
        logger.info(f"📂 Session directory: {session_dir}")
        
        # Start recording thread
        recording_thread = threading.Thread(target=self.recording_worker, args=(session_dir,))
        recording_thread.daemon = True
        recording_thread.start()
        
        # Start prediction thread
        prediction_thread = threading.Thread(target=self.prediction_worker)
        prediction_thread.daemon = True
        prediction_thread.start()
        
        return session_id
    
    def recording_worker(self, session_dir: str):
        """Continuous recording worker"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        logger.info("🎙️  Recording worker started")
        
        while self.recording:
            try:
                # Record audio segment
                frames = []
                for _ in range(0, int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
                    data = stream.read(self.CHUNK)
                    frames.append(data)
                
                # Convert to numpy array
                audio_data = np.frombuffer(b''.join(frames), dtype=np.float32)
                
                # Create audio segment
                segment = AudioSegment(
                    segment_id=f"seg_{int(time.time() * 1000)}",
                    timestamp=datetime.now(),
                    duration=self.RECORD_SECONDS,
                    audio_data=audio_data,
                    sample_rate=self.RATE,
                    environmental_context=self.analyze_environmental_context(audio_data)
                )
                
                # Save audio file
                audio_file = os.path.join(session_dir, f"{segment.segment_id}.wav")
                sf.write(audio_file, audio_data, self.RATE)
                
                # Add to queue
                self.audio_queue.put(segment)
                self.segments.append(segment)
                
                logger.info(f"📊 Recorded segment: {segment.segment_id}")
                
            except Exception as e:
                logger.error(f"❌ Recording error: {e}")
                time.sleep(5)
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        logger.info("🏁 Recording worker stopped")
    
    def analyze_environmental_context(self, audio_data: np.ndarray) -> Dict:
        """Analyze environmental context from audio"""
        try:
            # Basic audio features
            rms = np.sqrt(np.mean(audio_data**2))
            zcr = np.mean(librosa.feature.zero_crossing_rate(audio_data)[0])
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=self.RATE)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=self.RATE)[0]
            
            context = {
                "rms_energy": float(np.mean(rms)),
                "zero_crossing_rate": float(np.mean(zcr)),
                "spectral_centroid": float(np.mean(spectral_centroids)),
                "spectral_rolloff": float(np.mean(spectral_rolloff)),
                "silence_ratio": float(np.sum(np.abs(audio_data) < 0.01) / len(audio_data)),
                "dynamic_range": float(np.max(audio_data) - np.min(audio_data))
            }
            
            # Classify environment
            if context["silence_ratio"] > 0.8:
                context["environment_type"] = "quiet"
            elif context["rms_energy"] > 0.1:
                context["environment_type"] = "active"
            else:
                context["environment_type"] = "moderate"
            
            return context
            
        except Exception as e:
            logger.error(f"❌ Context analysis error: {e}")
            return {"error": str(e)}
    
    def transcribe_audio(self, segment: AudioSegment) -> Optional[str]:
        """Transcribe audio to text"""
        try:
            # Convert audio data to AudioFile format
            audio_file = f"temp_{segment.segment_id}.wav"
            sf.write(audio_file, segment.audio_data, self.RATE)
            
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
            
            # Try multiple recognition services
            text = None
            
            try:
                text = self.recognizer.recognize_google(audio)
            except:
                try:
                    text = self.recognizer.recognize_sphinx(audio)
                except:
                    pass
            
            # Clean up
            if os.path.exists(audio_file):
                os.remove(audio_file)
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return None
    
    def predict_thought(self, segment: AudioSegment) -> Tuple[Optional[str], float]:
        """Predict thought based on audio pattern"""
        try:
            # Extract audio features
            features = self.extract_audio_features(segment)
            
            # Find similar patterns
            similar_patterns = self.find_similar_patterns(features)
            
            if not similar_patterns:
                return None, 0.0
            
            # Get top prediction
            best_pattern = similar_patterns[0]
            predicted_thought = best_pattern.likely_thoughts[0]
            confidence = best_pattern.confidence_scores[0]
            
            # Enhance with context
            if segment.environmental_context:
                confidence *= self.context_confidence_boost(segment.environmental_context)
            
            return predicted_thought, min(confidence, 1.0)
            
        except Exception as e:
            logger.error(f"❌ Thought prediction error: {e}")
            return None, 0.0
    
    def extract_audio_features(self, segment: AudioSegment) -> np.ndarray:
        """Extract audio features for pattern matching"""
        try:
            # Extract various audio features
            mfccs = librosa.feature.mfcc(y=segment.audio_data, sr=self.RATE, n_mfcc=13)
            spectral_contrast = librosa.feature.spectral_contrast(y=segment.audio_data, sr=self.RATE)
            tonnetz = librosa.feature.tonnetz(y=segment.audio_data, sr=self.RATE)
            
            # Combine features
            features = np.concatenate([
                np.mean(mfccs, axis=1),
                np.mean(spectral_contrast, axis=1),
                np.mean(tonnetz, axis=1)
            ])
            
            return features
            
        except Exception as e:
            logger.error(f"❌ Feature extraction error: {e}")
            return np.array([])
    
    def find_similar_patterns(self, features: np.ndarray) -> List[ThoughtPattern]:
        """Find similar patterns in history"""
        if len(features) == 0 or not self.patterns:
            return []
        
        similarities = []
        
        for pattern in self.patterns:
            # Calculate similarity (simplified cosine similarity)
            pattern_features = np.array(pattern.audio_signature)
            
            if len(pattern_features) == len(features):
                similarity = np.dot(features, pattern_features) / (
                    np.linalg.norm(features) * np.linalg.norm(pattern_features)
                )
                
                if similarity >= self.pattern_similarity_threshold:
                    similarities.append((pattern, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [pattern for pattern, _ in similarities]
    
    def context_confidence_boost(self, context: Dict) -> float:
        """Boost confidence based on environmental context"""
        boost = 1.0
        
        # Boost for active environments
        if context.get("environment_type") == "active":
            boost *= 1.2
        
        # Boost for higher energy
        if context.get("rms_energy", 0) > 0.05:
            boost *= 1.1
        
        # Boost for clear audio
        if context.get("silence_ratio", 1.0) < 0.3:
            boost *= 1.15
        
        return min(boost, 1.5)
    
    def prediction_worker(self):
        """Worker for processing predictions"""
        logger.info("🧠 Prediction worker started")
        
        while self.recording:
            try:
                # Get segment from queue
                segment = self.audio_queue.get(timeout=1)
                
                # Transcribe audio
                transcription = self.transcribe_audio(segment)
                segment.transcription = transcription
                
                # Predict thought
                predicted_thought, confidence = self.predict_thought(segment)
                segment.predicted_thought = predicted_thought
                segment.confidence = confidence
                
                # Save to database
                self.save_segment(segment)
                
                # Update history
                self.audio_history.append(segment)
                if transcription:
                    self.transcription_history.append(transcription)
                if predicted_thought:
                    self.prediction_history.append(predicted_thought)
                
                logger.info(f"🧠 Predicted: {predicted_thought} (confidence: {confidence:.2f})")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Prediction worker error: {e}")
        
        logger.info("🏁 Prediction worker stopped")
    
    def save_segment(self, segment: AudioSegment):
        """Save segment to database"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO audio_segments 
            (segment_id, timestamp, duration, transcription, predicted_thought, 
             confidence, environmental_context, audio_file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            segment.segment_id,
            segment.timestamp.isoformat(),
            segment.duration,
            segment.transcription,
            segment.predicted_thought,
            segment.confidence,
            json.dumps(segment.environmental_context) if segment.environmental_context else None,
            f"audio_sessions/{segment.segment_id}.wav"
        ))
        
        conn.commit()
        conn.close()
    
    def learn_pattern(self, transcription: str, actual_thought: str, context: Dict):
        """Learn new thought pattern from user feedback"""
        try:
            # Create pattern from recent audio
            if self.audio_history:
                recent_segment = self.audio_history[-1]
                features = self.extract_audio_features(recent_segment)
                
                # Extract keywords
                keywords = self.extract_keywords(transcription)
                
                # Determine cycle phase
                cycle_phase = self.determine_cycle_phase(context)
                
                pattern = ThoughtPattern(
                    pattern_id=f"pattern_{int(time.time() * 1000)}",
                    audio_signature=features.tolist(),
                    likely_thoughts=[actual_thought],
                    confidence_scores=[1.0],
                    context_keywords=keywords,
                    cycle_phase=cycle_phase
                )
                
                self.patterns.append(pattern)
                
                logger.info(f"🎓 Learned new pattern: {actual_thought}")
                
        except Exception as e:
            logger.error(f"❌ Pattern learning error: {e}")
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from transcription"""
        if not text:
            return []
        
        # Simple keyword extraction (can be enhanced with NLP)
        words = text.lower().split()
        keywords = [word for word in words if len(word) > 3 and word.isalpha()]
        
        return list(set(keywords))
    
    def determine_cycle_phase(self, context: Dict) -> str:
        """Determine current work cycle phase"""
        if not context:
            return "unknown"
        
        energy = context.get("rms_energy", 0)
        silence_ratio = context.get("silence_ratio", 1.0)
        
        if energy > 0.1 and silence_ratio < 0.2:
            return "inspiration"
        elif energy > 0.05 and silence_ratio < 0.5:
            return "focus"
        elif silence_ratio > 0.8:
            return "break"
        else:
            return "frustration"
    
    def get_prediction_accuracy(self) -> Dict:
        """Get prediction accuracy statistics"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT AVG(accuracy_score) as avg_accuracy, COUNT(*) as total_predictions
            FROM prediction_accuracy
        ''')
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            "average_accuracy": result[0] or 0.0,
            "total_predictions": result[1] or 0
        }
    
    def setup_web_interface(self):
        """Setup Flask web interface"""
        app = Flask(__name__)
        
        AUDIO_PREDICTION_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Prediction System - Thought Analysis</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%); }
        .glass-effect { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); }
        .recording { animation: pulse 2s infinite; background: #ef4444; }
        .thinking { animation: pulse 3s infinite; background: #3b82f6; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body class="gradient-bg min-h-screen text-white">
    <div class="container mx-auto px-4 py-8">
        <header class="text-center mb-10">
            <h1 class="text-5xl font-bold mb-4">
                <i class="fas fa-brain mr-3"></i>Audio Prediction System
            </h1>
            <p class="text-xl opacity-90">Thought Prediction & Pattern Recognition</p>
            <div class="flex items-center justify-center mt-4">
                <div id="status-indicator" class="w-3 h-3 rounded-full mr-2 bg-gray-500"></div>
                <span id="status-text" class="text-lg">System Ready</span>
            </div>
        </header>

        <div class="glass-effect rounded-xl p-6 mb-10">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-microphone mr-2"></i>Audio Control
            </h2>
            
            <div class="grid md:grid-cols-3 gap-6">
                <button onclick="startRecording()" id="start-btn"
                        class="bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-bold">
                    <i class="fas fa-play mr-2"></i>Start Recording
                </button>
                <button onclick="stopRecording()" id="stop-btn"
                        class="bg-red-600 hover:bg-red-700 px-6 py-3 rounded-lg font-bold">
                    <i class="fas fa-stop mr-2"></i>Stop Recording
                </button>
                <button onclick="calibrateSystem()" 
                        class="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-bold">
                    <i class="fas fa-cog mr-2"></i>Calibrate
                </button>
            </div>
        </div>

        <div class="grid md:grid-cols-2 gap-6 mb-10">
            <div class="glass-effect rounded-xl p-6">
                <h2 class="text-2xl font-bold mb-6">
                    <i class="fas fa-waveform mr-2"></i>Environmental Context
                </h2>
                <div id="environmental-context" class="space-y-2">
                    <div class="text-center opacity-60">
                        <i class="fas fa-volume-up text-4xl mb-4"></i>
                        <p>Start recording to see context</p>
                    </div>
                </div>
            </div>
            
            <div class="glass-effect rounded-xl p-6">
                <h2 class="text-2xl font-bold mb-6">
                    <i class="fas fa-brain mr-2"></i>Predicted Thoughts
                </h2>
                <div id="predicted-thoughts" class="space-y-3">
                    <div class="text-center opacity-60">
                        <i class="fas fa-lightbulb text-4xl mb-4"></i>
                        <p>Predictions will appear here</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="glass-effect rounded-xl p-6">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-chart-line mr-2"></i>Pattern Learning
            </h2>
            
            <div class="mb-4">
                <input type="text" id="actual-thought" placeholder="Enter your actual thought..." 
                       class="w-full bg-white/20 rounded px-4 py-3 text-white placeholder-white/60">
            </div>
            
            <button onclick="submitFeedback()" 
                    class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-bold">
                <i class="fas fa-graduation-cap mr-2"></i>Teach System
            </button>
        </div>
    </div>

    <script>
        let recording = false;
        let predictionInterval;

        function updateStatus(active, text, type = 'ready') {
            const indicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('status-text');
            
            if (type === 'recording') {
                indicator.className = 'w-3 h-3 rounded-full mr-2 recording';
            } else if (type === 'thinking') {
                indicator.className = 'w-3 h-3 rounded-full mr-2 thinking';
            } else {
                indicator.className = 'w-3 h-3 rounded-full mr-2 bg-gray-500';
            }
            
            statusText.textContent = text;
        }

        async function startRecording() {
            try {
                const response = await fetch('/api/recording/start', {method: 'POST'});
                const result = await response.json();
                
                if (result.success) {
                    recording = true;
                    updateStatus(true, 'Recording Active', 'recording');
                    
                    // Start real-time updates
                    predictionInterval = setInterval(updatePredictions, 3000);
                    
                    alert('Recording started! The system is now predicting your thoughts.');
                } else {
                    alert('Failed to start recording: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }

        async function stopRecording() {
            try {
                const response = await fetch('/api/recording/stop', {method: 'POST'});
                const result = await response.json();
                
                if (result.success) {
                    recording = false;
                    updateStatus(false, 'Recording Stopped');
                    
                    // Stop updates
                    if (predictionInterval) {
                        clearInterval(predictionInterval);
                    }
                    
                    alert('Recording stopped and saved.');
                } else {
                    alert('Failed to stop recording: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }

        async function calibrateSystem() {
            updateStatus(true, 'Calibrating...', 'thinking');
            
            try {
                const response = await fetch('/api/calibrate', {method: 'POST'});
                const result = await response.json();
                
                updateStatus(false, 'System Ready');
                alert('System calibrated successfully!');
            } catch (error) {
                updateStatus(false, 'System Ready');
                alert('Calibration error: ' + error.message);
            }
        }

        async function updatePredictions() {
            try {
                const response = await fetch('/api/predictions');
                const result = await response.json();
                
                if (result.success) {
                    displayPredictions(result.predictions);
                    displayContext(result.context);
                }
            } catch (error) {
                console.error('Prediction update error:', error);
            }
        }

        function displayPredictions(predictions) {
            const container = document.getElementById('predicted-thoughts');
            
            if (!predictions || predictions.length === 0) {
                container.innerHTML = `
                    <div class="text-center opacity-60">
                        <i class="fas fa-lightbulb text-4xl mb-4"></i>
                        <p>No predictions yet</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = predictions.map(pred => `
                <div class="p-3 bg-white/10 rounded-lg">
                    <div class="text-sm opacity-70">Predicted Thought</div>
                    <div class="font-bold">${pred.thought}</div>
                    <div class="text-sm mt-1">
                        Confidence: ${pred.confidence.toFixed(2)} | Phase: ${pred.phase}
                    </div>
                </div>
            `).join('');
        }

        function displayContext(context) {
            const container = document.getElementById('environmental-context');
            
            if (!context) {
                container.innerHTML = `
                    <div class="text-center opacity-60">
                        <i class="fas fa-volume-up text-4xl mb-4"></i>
                        <p>No context data</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = `
                <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <div class="opacity-70">Environment</div>
                        <div class="font-bold">${context.environment_type || 'unknown'}</div>
                    </div>
                    <div>
                        <div class="opacity-70">Energy Level</div>
                        <div class="font-bold">${(context.rms_energy || 0).toFixed(3)}</div>
                    </div>
                    <div>
                        <div class="opacity-70">Silence Ratio</div>
                        <div class="font-bold">${(context.silence_ratio || 0).toFixed(2)}</div>
                    </div>
                    <div>
                        <div class="opacity-70">Dynamic Range</div>
                        <div class="font-bold">${(context.dynamic_range || 0).toFixed(3)}</div>
                    </div>
                </div>
            `;
        }

        async function submitFeedback() {
            const actualThought = document.getElementById('actual-thought').value;
            
            if (!actualThought) {
                alert('Please enter your actual thought');
                return;
            }
            
            try {
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({thought: actualThought})
                });
                
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('actual-thought').value = '';
                    alert('System learned from your feedback!');
                } else {
                    alert('Failed to submit feedback: ' + result.error);
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }

        // Initialize
        updateStatus(false, 'System Ready');
    </script>
</body>
</html>
        '''
        
        @app.route('/')
        def dashboard():
            return render_template_string(AUDIO_PREDICTION_TEMPLATE)
        
        @app.route('/api/recording/start', methods=['POST'])
        def start_recording():
            try:
                session_id = self.start_continuous_recording()
                return jsonify({"success": True, "session_id": session_id})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route('/api/recording/stop', methods=['POST'])
        def stop_recording():
            try:
                self.recording = False
                return jsonify({"success": True, "message": "Recording stopped"})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route('/api/predictions')
        def get_predictions():
            try:
                # Get recent predictions
                recent_predictions = []
                for segment in self.segments[-10:]:
                    if segment.predicted_thought:
                        recent_predictions.append({
                            "thought": segment.predicted_thought,
                            "confidence": segment.confidence,
                            "timestamp": segment.timestamp.isoformat(),
                            "phase": self.determine_cycle_phase(segment.environmental_context or {})
                        })
                
                # Get latest context
                latest_context = self.segments[-1].environmental_context if self.segments else None
                
                return jsonify({
                    "success": True,
                    "predictions": recent_predictions,
                    "context": latest_context
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route('/api/feedback', methods=['POST'])
        def submit_feedback():
            try:
                data = request.get_json()
                actual_thought = data.get('thought', '')
                
                if not actual_thought:
                    return jsonify({"success": False, "error": "No thought provided"}), 400
                
                # Learn from feedback
                if self.segments:
                    latest_segment = self.segments[-1]
                    transcription = latest_segment.transcription or ""
                    context = latest_segment.environmental_context or {}
                    
                    self.learn_pattern(transcription, actual_thought, context)
                
                return jsonify({"success": True, "message": "Feedback learned"})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @app.route('/api/calibrate', methods=['POST'])
        def calibrate_system():
            try:
                # Calibration logic here
                return jsonify({"success": True, "message": "System calibrated"})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        return app
    
    def run_web_interface(self, port: int = 8096):
        """Run web interface"""
        app = self.setup_web_interface()
        
        logger.info(f"🌐 Starting Audio Prediction Web Interface: http://localhost:{port}")
        webbrowser.open(f'http://localhost:{port}')
        
        app.run(host='0.0.0.0', port=port, debug=False)

# Main system
if __name__ == "__main__":
    system = AudioPredictionSystem()
    system.run_web_interface(port=8096)
