# Jagat Clone - Backend

Backend API cho ứng dụng Jagat Clone sử dụng FastAPI, WebSocket và PostgreSQL.

## Cài đặt

### 1. Tạo virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

### 3. Cấu hình Environment Variables:

Copy file `env.example` thành `.env`:
```bash
# Linux/Mac
cp env.example .env

# Windows
copy env.example .env
```

Chỉnh sửa file `.env` với các giá trị phù hợp:
```env
DATABASE_URL=postgresql://jagat_user:jagat_password@localhost:5432/jagat_db
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 4. Chạy server:

**Option 1: Chạy trực tiếp (cần PostgreSQL đã setup)**
```bash
uvicorn main:app --reload
```

**Option 2: Chạy với Docker Compose (tự động setup PostgreSQL)**
```bash
docker-compose up
```

Server sẽ chạy tại: http://localhost:8000

## Environment Variables

Xem file `env.example` để biết tất cả các biến môi trường có thể config:

- `DATABASE_URL`: PostgreSQL connection string
- `ALLOWED_ORIGINS`: Comma-separated list of CORS allowed origins
- `DEBUG`: Enable debug mode (true/false)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)

**Lưu ý**: File `.env` không được commit lên Git (đã có trong .gitignore)

## API Endpoints

### HTTP Endpoints
- `GET /` - Health check
- `GET /health` - Health status với database connection check
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

## Database

Backend sử dụng PostgreSQL với SQLAlchemy (async).

Database schema được tự động tạo khi app start (startup event).

### Models:
- `user_profiles`: Thông tin user
- `friends`: Quan hệ bạn bè (bidirectional)
- `user_locations`: Vị trí real-time của users

## Deploy

Xem file `RAILWAY_DEPLOY.md` để biết cách deploy lên Railway.
