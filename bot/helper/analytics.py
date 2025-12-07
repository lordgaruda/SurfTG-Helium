"""
Analytics tracking system for monitoring bot usage, bandwidth, and performance
"""
import time
import psutil
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
from bot.telegram import multi_clients, work_loads

class Analytics:
    def __init__(self):
        self.requests_count = 0
        self.total_bandwidth = 0  # in bytes
        self.stream_count = 0
        self.download_count = 0
        self.search_count = 0
        self.active_streams = 0
        self.error_count = 0
        self.start_time = time.time()
        
        # Hourly tracking
        self.hourly_requests = defaultdict(int)
        self.hourly_bandwidth = defaultdict(int)
        
        # Per-client tracking
        self.client_requests = defaultdict(int)
        self.client_bandwidth = defaultdict(int)
        
        # Recent requests (last 100)
        self.recent_requests: List[Dict] = []
        self.max_recent = 100
        
        # Peak stats
        self.peak_active_streams = 0
        self.peak_bandwidth_hour = 0
        
    def track_request(self, request_type: str, client_id: int = 0):
        """Track incoming requests"""
        self.requests_count += 1
        hour_key = datetime.now().strftime("%Y-%m-%d %H:00")
        self.hourly_requests[hour_key] += 1
        self.client_requests[client_id] += 1
        
        if request_type == 'stream':
            self.stream_count += 1
        elif request_type == 'download':
            self.download_count += 1
        elif request_type == 'search':
            self.search_count += 1
            
        # Store recent request
        self.recent_requests.append({
            'timestamp': datetime.now().isoformat(),
            'type': request_type,
            'client_id': client_id
        })
        if len(self.recent_requests) > self.max_recent:
            self.recent_requests.pop(0)
    
    def track_bandwidth(self, bytes_transferred: int, client_id: int = 0):
        """Track bandwidth usage"""
        self.total_bandwidth += bytes_transferred
        hour_key = datetime.now().strftime("%Y-%m-%d %H:00")
        self.hourly_bandwidth[hour_key] += bytes_transferred
        self.client_bandwidth[client_id] += bytes_transferred
        
        # Update peak
        if self.hourly_bandwidth[hour_key] > self.peak_bandwidth_hour:
            self.peak_bandwidth_hour = self.hourly_bandwidth[hour_key]
    
    def track_stream_start(self):
        """Track active stream start"""
        self.active_streams += 1
        if self.active_streams > self.peak_active_streams:
            self.peak_active_streams = self.active_streams
    
    def track_stream_end(self):
        """Track active stream end"""
        if self.active_streams > 0:
            self.active_streams -= 1
    
    def track_error(self):
        """Track errors"""
        self.error_count += 1
    
    def get_uptime(self) -> str:
        """Get formatted uptime"""
        uptime_seconds = int(time.time() - self.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        return f"{days}d {hours}h {minutes}m {seconds}s"
    
    def get_bandwidth_human(self, bytes_val: int = None) -> str:
        """Convert bytes to human readable format"""
        if bytes_val is None:
            bytes_val = self.total_bandwidth
            
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"
    
    def get_system_stats(self) -> Dict:
        """Get system resource usage"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu_usage': f"{cpu_percent}%",
            'ram_usage': f"{memory.percent}%",
            'ram_used': self.get_bandwidth_human(memory.used),
            'ram_total': self.get_bandwidth_human(memory.total),
            'disk_usage': f"{disk.percent}%",
            'disk_used': self.get_bandwidth_human(disk.used),
            'disk_total': self.get_bandwidth_human(disk.total)
        }
    
    def get_client_stats(self) -> List[Dict]:
        """Get statistics for all clients"""
        stats = []
        for client_id, client in multi_clients.items():
            stats.append({
                'id': client_id,
                'username': getattr(client, 'username', f'Client {client_id}'),
                'workload': work_loads.get(client_id, 0),
                'requests': self.client_requests[client_id],
                'bandwidth': self.get_bandwidth_human(self.client_bandwidth[client_id])
            })
        return stats
    
    def get_hourly_stats(self, hours: int = 24) -> Dict:
        """Get hourly statistics for the last N hours"""
        now = datetime.now()
        hourly_data = {
            'labels': [],
            'requests': [],
            'bandwidth': []
        }
        
        for i in range(hours):
            hour = now - timedelta(hours=hours - i - 1)
            hour_key = hour.strftime("%Y-%m-%d %H:00")
            hourly_data['labels'].append(hour.strftime("%H:00"))
            hourly_data['requests'].append(self.hourly_requests.get(hour_key, 0))
            hourly_data['bandwidth'].append(
                round(self.hourly_bandwidth.get(hour_key, 0) / (1024 * 1024), 2)  # Convert to MB
            )
        
        return hourly_data
    
    def get_summary(self) -> Dict:
        """Get complete analytics summary"""
        system_stats = self.get_system_stats()
        
        return {
            'uptime': self.get_uptime(),
            'total_requests': self.requests_count,
            'stream_count': self.stream_count,
            'download_count': self.download_count,
            'search_count': self.search_count,
            'active_streams': self.active_streams,
            'peak_streams': self.peak_active_streams,
            'total_bandwidth': self.get_bandwidth_human(),
            'total_bandwidth_bytes': self.total_bandwidth,
            'peak_bandwidth_hour': self.get_bandwidth_human(self.peak_bandwidth_hour),
            'error_count': self.error_count,
            'error_rate': f"{(self.error_count / max(self.requests_count, 1) * 100):.2f}%",
            'avg_bandwidth_per_request': self.get_bandwidth_human(
                self.total_bandwidth // max(self.requests_count, 1)
            ),
            'clients_count': len(multi_clients),
            'system': system_stats,
            'clients': self.get_client_stats(),
            'hourly': self.get_hourly_stats(),
            'recent_requests': self.recent_requests[-20:]  # Last 20 requests
        }
    
    def reset_stats(self):
        """Reset all statistics (admin action)"""
        self.requests_count = 0
        self.total_bandwidth = 0
        self.stream_count = 0
        self.download_count = 0
        self.search_count = 0
        self.error_count = 0
        self.hourly_requests.clear()
        self.hourly_bandwidth.clear()
        self.client_requests.clear()
        self.client_bandwidth.clear()
        self.recent_requests.clear()
        self.start_time = time.time()

# Global analytics instance
analytics = Analytics()
