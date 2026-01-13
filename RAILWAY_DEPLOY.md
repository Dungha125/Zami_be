# Hướng dẫn Deploy Backend lên Railway

## Bước 1: Chuẩn bị

1. Đảm bảo bạn đã có tài khoản Railway tại https://railway.app
2. Đảm bảo code đã được commit lên Git repository (GitHub, GitLab, etc.)

## Bước 2: Tạo Project trên Railway

1. Đăng nhập vào Railway
2. Click "New Project"
3. Chọn "Deploy from GitHub repo" (hoặc GitLab/Bitbucket)
4. Chọn repository chứa code backend
5. Chọn root directory: `jagat-clone/backend`

## Bước 3: Thêm PostgreSQL Database

1. Trong Railway project, click "New" → "Database" → "Add PostgreSQL"
2. Railway sẽ tự động tạo PostgreSQL database và set environment variable `DATABASE_URL`
3. Lưu ý URL này - bạn sẽ cần nó

## Bước 4: Cấu hình

Railway sẽ tự động detect:
- **Build Command**: Từ Dockerfile (nếu có) hoặc từ requirements.txt
- **Start Command**: Sử dụng từ Procfile hoặc Dockerfile CMD
- **Python Version**: Từ runtime.txt (Python 3.11.0)

### Environment Variables (Recommended)

Bạn nên thêm biến môi trường trong Railway Dashboard → Variables:

**DATABASE_URL** (Automatic):
- Railway tự động set khi bạn thêm PostgreSQL database
- Format: `postgresql://user:password@host:port/database`
- **Không cần set manually** - Railway tự động inject

**ALLOWED_ORIGINS** (Recommended):
- Danh sách origins được phép, phân cách bởi dấu phẩy
- Ví dụ: `https://your-frontend.railway.app,https://yourdomain.com`
- Nếu không set, backend sẽ allow all origins (không khuyến khích cho production)

**Lưu ý**: 
- Set ALLOWED_ORIGINS với domain cụ thể để đảm bảo bảo mật
- WebSocket yêu cầu credentials, nên cần set ALLOWED_ORIGINS cụ thể

## Bước 5: Deploy

1. Railway sẽ tự động build và deploy
2. Database tables sẽ tự động được tạo khi app start (startup event)
3. Sau khi deploy thành công, Railway sẽ cung cấp:
   - **Public URL**: `https://your-app-name.railway.app`
   - **Port**: Railway tự động set PORT environment variable

## Bước 6: Kiểm tra

1. Truy cập `https://your-app-name.railway.app/health`
2. Nên thấy response: `{"status": "healthy", "database": "connected"}`
3. Truy cập `https://your-app-name.railway.app/` để xem API info

## Bước 7: Cập nhật Frontend

Sau khi có Railway URL, cập nhật frontend để sử dụng Railway backend:

### Cập nhật API URL trong frontend:

1. Tạo file `.env` trong thư mục `frontend/`:
```
VITE_API_URL=https://your-app-name.railway.app
```

2. Hoặc cập nhật trực tiếp trong code:
- Thay `http://localhost:8000` bằng Railway URL
- Thay `ws://localhost:8000` bằng `wss://your-app-name.railway.app` (WebSocket Secure)

## Lưu ý quan trọng

1. **PostgreSQL Database**: 
   - Railway tự động tạo và quản lý database
   - DATABASE_URL được tự động inject vào environment
   - Tables được tự động tạo khi app start (không cần migrations riêng)

2. **WebSocket**: Railway hỗ trợ WebSocket, nhưng cần sử dụng `wss://` (WebSocket Secure) thay vì `ws://`

3. **CORS**: 
   - **Khuyến khích**: Set `ALLOWED_ORIGINS` environment variable với domain frontend cụ thể
   - Nếu không set, backend sẽ allow all origins nhưng không hỗ trợ credentials (có thể gây lỗi WebSocket)
   - Ví dụ: `ALLOWED_ORIGINS=https://your-frontend.railway.app`

4. **HTTPS**: Railway tự động cung cấp HTTPS cho domain của bạn.

5. **Data Persistence**: 
   - Dữ liệu được lưu trong PostgreSQL database
   - Dữ liệu sẽ persist qua các lần restart
   - Railway cung cấp backup tự động cho database

6. **Monitoring**: Railway cung cấp logs và metrics trong Dashboard

## Deploy với Docker (Optional)

Nếu muốn sử dụng Docker:

1. Railway sẽ tự động detect Dockerfile
2. Build và deploy từ Dockerfile
3. Đảm bảo Dockerfile có trong `jagat-clone/backend/`

## Local Development với Docker

Để test local với PostgreSQL:

```bash
cd jagat-clone/backend
docker-compose up
```

Backend sẽ chạy tại http://localhost:8000
PostgreSQL sẽ chạy tại localhost:5432

## Troubleshooting

### Build fails
- Kiểm tra Python version trong runtime.txt
- Kiểm tra requirements.txt có đúng dependencies
- Kiểm tra Dockerfile nếu sử dụng Docker

### Database connection errors
- Kiểm tra DATABASE_URL environment variable
- Đảm bảo PostgreSQL service đã được start
- Kiểm tra logs trong Railway Dashboard

### Service không start
- Kiểm tra logs trong Railway Dashboard
- Đảm bảo PORT environment variable được sử dụng (Railway tự động set)
- Kiểm tra database connection

### WebSocket không hoạt động
- Đảm bảo frontend sử dụng `wss://` thay vì `ws://`
- Kiểm tra CORS configuration
- Kiểm tra ALLOWED_ORIGINS environment variable

### CORS errors
- **Quan trọng**: Set ALLOWED_ORIGINS environment variable với domain frontend của bạn
- Ví dụ: `ALLOWED_ORIGINS=https://your-frontend.railway.app`
- Nếu không set, backend sẽ allow all origins nhưng không hỗ trợ credentials (có thể gây lỗi WebSocket)

### Database tables not created
- Kiểm tra logs để xem có lỗi trong startup event
- Đảm bảo DATABASE_URL đúng format
- Kiểm tra database permissions

## Custom Domain (Optional)

1. Trong Railway Dashboard, vào Settings
2. Chọn "Domains"
3. Add custom domain
4. Follow instructions để config DNS
