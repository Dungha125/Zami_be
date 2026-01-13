# Jagat Clone - Backend

Backend API cho ứng dụng Jagat Clone sử dụng FastAPI và WebSocket.

## Cài đặt

1. Tạo virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

3. Chạy server:
```bash
uvicorn main:app --reload
```

Server sẽ chạy tại: http://localhost:8000

## API Endpoints

### HTTP Endpoints
- `GET /` - Health check
- `GET /health` - Health status
- `GET /api/locations` - Lấy tất cả vị trí người dùng

### WebSocket Endpoints
- `WS /ws/{user_id}` - Kết nối WebSocket cho real-time features

## WebSocket Message Types

### Client → Server
- `location_update`: Cập nhật vị trí
- `message`: Gửi tin nhắn
- `join_room`: Tham gia phòng
- `webrtc_offer`: WebRTC offer cho video call
- `webrtc_answer`: WebRTC answer cho video call
- `webrtc_ice_candidate`: WebRTC ICE candidate

### Server → Client
- `location_update`: Nhận cập nhật vị trí từ người khác
- `initial_locations`: Vị trí ban đầu của tất cả người dùng
- `message`: Nhận tin nhắn
- `user_joined`: Người dùng tham gia phòng
- `user_left`: Người dùng rời phòng
- `webrtc_offer`: WebRTC offer từ người khác
- `webrtc_answer`: WebRTC answer từ người khác
- `webrtc_ice_candidate`: WebRTC ICE candidate từ người khác
