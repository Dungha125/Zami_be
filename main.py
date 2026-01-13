from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import json
import uvicorn
from datetime import datetime, timedelta
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete

from settings import get_settings
from database import (
    init_db, get_db, AsyncSessionLocal, UserProfile as DBUserProfile, 
    Friend as DBFriend, UserLocation as DBUserLocation, Message as DBMessage
)

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections (still in-memory for WebSocket)
active_connections: Dict[str, WebSocket] = {}
rooms: Dict[str, List[str]] = {}
typing_status: Dict[str, Dict[str, bool]] = {}  # {user_id: {friend_id: is_typing}}

# Background task to delete old messages
async def cleanup_old_messages():
    """Delete messages older than 7 days"""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            async with AsyncSessionLocal() as db:
                try:
                    cutoff_date = datetime.utcnow() - timedelta(days=7)
                    result = await db.execute(
                        delete(DBMessage).where(DBMessage.created_at < cutoff_date)
                    )
                    await db.commit()
                    deleted_count = result.rowcount
                    if deleted_count > 0:
                        print(f"Deleted {deleted_count} old messages")
                except Exception as e:
                    print(f"Error cleaning up old messages: {e}")
                    await db.rollback()
        except Exception as e:
            print(f"Error in cleanup task: {e}")

# Startup event to initialize database
@app.on_event("startup")
async def startup_event():
    await init_db()
    print("Database initialized")
    # Start background task to clean up old messages
    asyncio.create_task(cleanup_old_messages())

# Pydantic models
class UserProfile(BaseModel):
    username: str
    avatar: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[str] = None

class UpdateProfile(BaseModel):
    username: Optional[str] = None
    avatar: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[str] = None

class FriendRequest(BaseModel):
    friend_user_id: str

class MessageCreate(BaseModel):
    receiver_id: str
    content: Optional[str] = None
    sticker: Optional[str] = None

class MessageStatusUpdate(BaseModel):
    message_ids: list[int]
    status: str  # delivered, read

@app.get("/")
async def root():
    return {"message": "Jagat Clone API", "status": "running", "database": "PostgreSQL"}

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        # Test database connection
        await db.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

@app.get("/api/locations")
async def get_all_locations(db: AsyncSession = Depends(get_db)):
    """Get all user locations"""
    result = await db.execute(select(DBUserLocation))
    locations = result.scalars().all()
    return {
        "locations": [
            {
                "lat": loc.lat,
                "lng": loc.lng,
                "user_id": loc.user_id,
                "timestamp": loc.timestamp.isoformat(),
                "accuracy": loc.accuracy
            }
            for loc in locations
        ]
    }

# User Profile Endpoints
@app.post("/api/users/{user_id}/profile")
async def create_or_update_profile(
    user_id: str, 
    profile: UpdateProfile,
    db: AsyncSession = Depends(get_db)
):
    """Create or update user profile"""
    result = await db.execute(select(DBUserProfile).where(DBUserProfile.user_id == user_id))
    db_profile = result.scalar_one_or_none()
    
    if db_profile:
        # Update existing profile
        if profile.username:
            db_profile.username = profile.username
        if profile.avatar is not None:
            db_profile.avatar = profile.avatar
        if profile.bio is not None:
            db_profile.bio = profile.bio
        if profile.status is not None:
            db_profile.status = profile.status
        db_profile.updated_at = datetime.utcnow()
    else:
        # Create new profile
        db_profile = DBUserProfile(
            user_id=user_id,
            username=profile.username or f"User_{user_id[-6:]}",
            avatar=profile.avatar,
            bio=profile.bio or "",
            status=profile.status or ""
        )
        db.add(db_profile)
    
    await db.commit()
    await db.refresh(db_profile)
    
    return {
        "user_id": db_profile.user_id,
        "username": db_profile.username,
        "avatar": db_profile.avatar,
        "bio": db_profile.bio,
        "status": db_profile.status
    }

@app.get("/api/users/{user_id}/profile")
async def get_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get user profile"""
    result = await db.execute(select(DBUserProfile).where(DBUserProfile.user_id == user_id))
    db_profile = result.scalar_one_or_none()
    
    if not db_profile:
        return {
            "user_id": user_id,
            "username": f"User_{user_id[-6:]}",
            "avatar": None,
            "bio": "",
            "status": ""
        }
    
    return {
        "user_id": db_profile.user_id,
        "username": db_profile.username,
        "avatar": db_profile.avatar,
        "bio": db_profile.bio,
        "status": db_profile.status
    }

@app.get("/api/users/search")
async def search_users(query: str, current_user_id: str, db: AsyncSession = Depends(get_db)):
    """Search users by username"""
    query_lower = query.lower()
    
    # Search in database
    result = await db.execute(
        select(DBUserProfile).where(
            and_(
                DBUserProfile.user_id != current_user_id,
                DBUserProfile.username.ilike(f"%{query_lower}%")
            )
        )
    )
    db_profiles = result.scalars().all()
    
    # Get friend IDs for current user
    friend_result = await db.execute(
        select(DBFriend).where(DBFriend.user_id == current_user_id)
    )
    friend_ids = {f.friend_id for f in friend_result.scalars().all()}
    
    results = []
    for profile in db_profiles:
        results.append({
            "user_id": profile.user_id,
            "username": profile.username,
            "avatar": profile.avatar,
            "bio": profile.bio or "",
            "is_friend": profile.user_id in friend_ids
        })
    
    return {"users": results}

# Friends Endpoints
@app.post("/api/users/{user_id}/friends")
async def add_friend(
    user_id: str, 
    friend_request: FriendRequest,
    db: AsyncSession = Depends(get_db)
):
    """Add a friend"""
    friend_id = friend_request.friend_user_id
    
    if friend_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot add yourself as a friend")
    
    # Check if friendship already exists (either direction)
    result = await db.execute(
        select(DBFriend).where(
            or_(
                and_(DBFriend.user_id == user_id, DBFriend.friend_id == friend_id),
                and_(DBFriend.user_id == friend_id, DBFriend.friend_id == user_id)
            )
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Friendship already exists")
    
    # Create bidirectional friendship
    friendship1 = DBFriend(user_id=user_id, friend_id=friend_id)
    friendship2 = DBFriend(user_id=friend_id, friend_id=user_id)
    db.add(friendship1)
    db.add(friendship2)
    await db.commit()
    
    # Get all friends
    result = await db.execute(select(DBFriend).where(DBFriend.user_id == user_id))
    friends = result.scalars().all()
    
    return {
        "message": "Friend added successfully",
        "friends": [f.friend_id for f in friends]
    }

@app.delete("/api/users/{user_id}/friends/{friend_id}")
async def remove_friend(
    user_id: str, 
    friend_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Remove a friend"""
    # Remove both directions
    result = await db.execute(
        select(DBFriend).where(
            or_(
                and_(DBFriend.user_id == user_id, DBFriend.friend_id == friend_id),
                and_(DBFriend.user_id == friend_id, DBFriend.friend_id == user_id)
            )
        )
    )
    friendships = result.scalars().all()
    
    for friendship in friendships:
        await db.delete(friendship)
    
    await db.commit()
    return {"message": "Friend removed successfully"}

@app.get("/api/users/{user_id}/friends")
async def get_friends(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get user's friends list with profiles"""
    result = await db.execute(select(DBFriend).where(DBFriend.user_id == user_id))
    friendships = result.scalars().all()
    
    friend_profiles = []
    for friendship in friendships:
        profile_result = await db.execute(
            select(DBUserProfile).where(DBUserProfile.user_id == friendship.friend_id)
        )
        profile = profile_result.scalar_one_or_none()
        
        if profile:
            profile_data = {
                "user_id": profile.user_id,
                "username": profile.username,
                "avatar": profile.avatar,
                "bio": profile.bio or "",
                "status": profile.status or ""
            }
            # Add location if available
            loc_result = await db.execute(
                select(DBUserLocation).where(DBUserLocation.user_id == friendship.friend_id)
            )
            location = loc_result.scalar_one_or_none()
            if location:
                profile_data["location"] = {
                    "lat": location.lat,
                    "lng": location.lng,
                    "timestamp": location.timestamp.isoformat(),
                    "accuracy": location.accuracy
                }
            friend_profiles.append(profile_data)
    
    return {"friends": friend_profiles}

# Message Endpoints
@app.get("/api/users/{user_id}/messages/{friend_id}")
async def get_messages(
    user_id: str,
    friend_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get messages between two users (last 7 days)"""
    # Verify friendship
    result = await db.execute(
        select(DBFriend).where(
            or_(
                and_(DBFriend.user_id == user_id, DBFriend.friend_id == friend_id),
                and_(DBFriend.user_id == friend_id, DBFriend.friend_id == user_id)
            )
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Users are not friends")
    
    # Get messages between these two users
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(DBMessage).where(
            or_(
                and_(DBMessage.sender_id == user_id, DBMessage.receiver_id == friend_id),
                and_(DBMessage.sender_id == friend_id, DBMessage.receiver_id == user_id)
            ),
            DBMessage.created_at >= cutoff_date
        ).order_by(DBMessage.created_at.asc())
    )
    messages = result.scalars().all()
    
    return {
        "messages": [
            {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "receiver_id": msg.receiver_id,
                "content": msg.content,
                "sticker": msg.sticker,
                "status": msg.status,
                "created_at": msg.created_at.isoformat(),
                "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
                "read_at": msg.read_at.isoformat() if msg.read_at else None
            }
            for msg in messages
        ]
    }

@app.post("/api/users/{user_id}/messages/status")
async def update_message_status(
    user_id: str,
    status_update: MessageStatusUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update message status (delivered or read)"""
    now = datetime.utcnow()
    
    for msg_id in status_update.message_ids:
        result = await db.execute(
            select(DBMessage).where(
                DBMessage.id == msg_id,
                DBMessage.receiver_id == user_id
            )
        )
        msg = result.scalar_one_or_none()
        if msg:
            if status_update.status == "delivered" and not msg.delivered_at:
                msg.status = "delivered"
                msg.delivered_at = now
            elif status_update.status == "read" and not msg.read_at:
                msg.status = "read"
                msg.read_at = now
    
    await db.commit()
    return {"message": "Status updated successfully"}

# WebSocket endpoint for real-time features
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    active_connections[user_id] = websocket
    
    # Get initial locations from database (only friends + current user)
    async with AsyncSessionLocal() as db:
        try:
            # Get user's friends
            friend_result = await db.execute(
                select(DBFriend).where(DBFriend.user_id == user_id)
            )
            friend_ids = {f.friend_id for f in friend_result.scalars().all()}
            # Always include current user
            friend_ids.add(user_id)
            
            # Get locations only for friends
            result = await db.execute(
                select(DBUserLocation).where(DBUserLocation.user_id.in_(list(friend_ids)))
            )
            locations = result.scalars().all()
            
            # Get usernames
            user_ids = [loc.user_id for loc in locations]
            if user_ids:
                profile_result = await db.execute(
                    select(DBUserProfile).where(DBUserProfile.user_id.in_(user_ids))
                )
                profiles = {p.user_id: p for p in profile_result.scalars().all()}
            else:
                profiles = {}
            
            initial_locations = []
            for loc in locations:
                profile = profiles.get(loc.user_id)
                initial_locations.append({
                    "lat": loc.lat,
                    "lng": loc.lng,
                    "user_id": loc.user_id,
                    "username": profile.username if profile else f"User_{loc.user_id[-6:]}",
                    "timestamp": loc.timestamp.isoformat(),
                    "accuracy": loc.accuracy
                })
            
            await websocket.send_text(json.dumps({
                "type": "initial_locations",
                "locations": initial_locations
            }))
        except Exception as e:
            print(f"Error loading initial locations: {e}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "location_update":
                # Update location in database
                async with AsyncSessionLocal() as db:
                    try:
                        result = await db.execute(
                            select(DBUserLocation).where(DBUserLocation.user_id == user_id)
                        )
                        db_location = result.scalar_one_or_none()
                        
                        if db_location:
                            db_location.lat = message["lat"]
                            db_location.lng = message["lng"]
                            db_location.accuracy = message.get("accuracy", 0)
                            db_location.timestamp = datetime.utcnow()
                        else:
                            db_location = DBUserLocation(
                                user_id=user_id,
                                lat=message["lat"],
                                lng=message["lng"],
                                accuracy=message.get("accuracy", 0)
                            )
                            db.add(db_location)
                        
                        await db.commit()
                        
                        # Get username
                        profile_result = await db.execute(
                            select(DBUserProfile).where(DBUserProfile.user_id == user_id)
                        )
                        profile = profile_result.scalar_one_or_none()
                        username = profile.username if profile else message.get("username", user_id)
                        
                        location_data = {
                            "lat": db_location.lat,
                            "lng": db_location.lng,
                            "user_id": user_id,
                            "username": username,
                            "timestamp": db_location.timestamp.isoformat(),
                            "accuracy": db_location.accuracy
                        }
                        
                        # Broadcast to all connected clients
                        await broadcast_location_update(user_id, location_data)
                    except Exception as e:
                        print(f"Error updating location: {e}")
                        await db.rollback()
                
            elif message["type"] == "message":
                await handle_message(message, user_id)
            
            elif message["type"] == "typing_start":
                await handle_typing_status(user_id, message.get("receiver_id"), True)
            
            elif message["type"] == "typing_stop":
                await handle_typing_status(user_id, message.get("receiver_id"), False)
            
            elif message["type"] == "mark_delivered":
                await handle_mark_delivered(message.get("message_ids"), user_id)
            
            elif message["type"] == "mark_read":
                await handle_mark_read(message.get("message_ids"), user_id)
                
            elif message["type"] == "join_room":
                room_id = message.get("room_id")
                if room_id not in rooms:
                    rooms[room_id] = []
                if user_id not in rooms[room_id]:
                    rooms[room_id].append(user_id)
                await broadcast_to_room(room_id, {
                    "type": "user_joined",
                    "user_id": user_id,
                    "room_id": room_id
                })
                
            elif message["type"] == "webrtc_offer":
                await handle_webrtc_offer(message, user_id)
                
            elif message["type"] == "webrtc_answer":
                await handle_webrtc_answer(message, user_id)
                
            elif message["type"] == "webrtc_ice_candidate":
                await handle_webrtc_ice(message, user_id)
                
    except WebSocketDisconnect:
        if user_id in active_connections:
            del active_connections[user_id]
        # Clear typing status
        if user_id in typing_status:
            del typing_status[user_id]
        # Note: Keep location in database even after disconnect

async def broadcast_location_update(user_id: str, location: dict):
    """Broadcast location update only to friends of the user"""
    message = {
        "type": "location_update",
        "user_id": user_id,
        "location": location
    }
    
    # Get friends of the user who updated location
    async with AsyncSessionLocal() as db:
        try:
            friend_result = await db.execute(
                select(DBFriend).where(DBFriend.friend_id == user_id)
            )
            friend_user_ids = {f.user_id for f in friend_result.scalars().all()}
            # Also send to the user themselves
            friend_user_ids.add(user_id)
        except Exception as e:
            print(f"Error getting friends for broadcast: {e}")
            friend_user_ids = {user_id}  # Fallback: only send to self
    
    disconnected = []
    for uid, ws in active_connections.items():
        # Only send to friends (or the user themselves)
        if uid in friend_user_ids:
            try:
                await ws.send_text(json.dumps(message))
            except:
                disconnected.append(uid)
    
    for uid in disconnected:
        if uid in active_connections:
            del active_connections[uid]

async def handle_message(message: dict, sender_id: str):
    """Handle chat messages - save to DB and send to receiver"""
    receiver_id = message.get("receiver_id")
    if not receiver_id:
        return
    
    # Verify friendship
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(DBFriend).where(
                    or_(
                        and_(DBFriend.user_id == sender_id, DBFriend.friend_id == receiver_id),
                        and_(DBFriend.user_id == receiver_id, DBFriend.friend_id == sender_id)
                    )
                )
            )
            if not result.scalar_one_or_none():
                return  # Not friends, ignore message
            
            # Save message to database
            db_message = DBMessage(
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=message.get("content"),
                sticker=message.get("sticker"),
                status="sent"
            )
            db.add(db_message)
            await db.commit()
            await db.refresh(db_message)
            
            # Prepare message for WebSocket
            broadcast_message = {
                "type": "message",
                "id": db_message.id,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "content": db_message.content,
                "sticker": db_message.sticker,
                "status": db_message.status,
                "created_at": db_message.created_at.isoformat()
            }
            
            # Send to receiver if online
            if receiver_id in active_connections:
                try:
                    await active_connections[receiver_id].send_text(json.dumps(broadcast_message))
                    # Mark as delivered immediately if receiver is online
                    db_message.status = "delivered"
                    db_message.delivered_at = datetime.utcnow()
                    await db.commit()
                except:
                    pass
            
            # Also send back to sender for confirmation
            if sender_id in active_connections:
                try:
                    await active_connections[sender_id].send_text(json.dumps(broadcast_message))
                except:
                    pass
        except Exception as e:
            print(f"Error handling message: {e}")
            await db.rollback()

async def handle_typing_status(user_id: str, receiver_id: str, is_typing: bool):
    """Handle typing status updates"""
    if not receiver_id or receiver_id not in active_connections:
        return
    
    if user_id not in typing_status:
        typing_status[user_id] = {}
    typing_status[user_id][receiver_id] = is_typing
    
    try:
        await active_connections[receiver_id].send_text(json.dumps({
            "type": "typing_status",
            "sender_id": user_id,
            "is_typing": is_typing
        }))
    except:
        pass
    
    # Auto-clear typing status after 3 seconds
    if is_typing:
        async def clear_typing():
            await asyncio.sleep(3)
            if user_id in typing_status and receiver_id in typing_status[user_id]:
                typing_status[user_id][receiver_id] = False
                if receiver_id in active_connections:
                    try:
                        await active_connections[receiver_id].send_text(json.dumps({
                            "type": "typing_status",
                            "sender_id": user_id,
                            "is_typing": False
                        }))
                    except:
                        pass
        asyncio.create_task(clear_typing())

async def handle_mark_delivered(message_ids: list, user_id: str):
    """Mark messages as delivered"""
    if not message_ids:
        return
    
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()
            for msg_id in message_ids:
                result = await db.execute(
                    select(DBMessage).where(
                        DBMessage.id == msg_id,
                        DBMessage.receiver_id == user_id
                    )
                )
                msg = result.scalar_one_or_none()
                if msg and not msg.delivered_at:
                    msg.status = "delivered"
                    msg.delivered_at = now
            await db.commit()
        except Exception as e:
            print(f"Error marking messages as delivered: {e}")
            await db.rollback()

async def handle_mark_read(message_ids: list, user_id: str):
    """Mark messages as read"""
    if not message_ids:
        return
    
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()
            for msg_id in message_ids:
                result = await db.execute(
                    select(DBMessage).where(
                        DBMessage.id == msg_id,
                        DBMessage.receiver_id == user_id
                    )
                )
                msg = result.scalar_one_or_none()
                if msg and not msg.read_at:
                    msg.status = "read"
                    msg.read_at = now
            await db.commit()
            
            # Notify sender that messages were read
            result = await db.execute(
                select(DBMessage).where(DBMessage.id.in_(message_ids))
            )
            messages = result.scalars().all()
            sender_ids = {msg.sender_id for msg in messages if msg.sender_id != user_id}
            
            for sender_id in sender_ids:
                if sender_id in active_connections:
                    try:
                        await active_connections[sender_id].send_text(json.dumps({
                            "type": "messages_read",
                            "message_ids": message_ids,
                            "reader_id": user_id
                        }))
                    except:
                        pass
        except Exception as e:
            print(f"Error marking messages as read: {e}")
            await db.rollback()

async def broadcast_to_room(room_id: str, message: dict):
    """Broadcast message to all users in a room"""
    if room_id not in rooms:
        return
    
    disconnected = []
    for user_id in rooms[room_id]:
        if user_id in active_connections:
            try:
                await active_connections[user_id].send_text(json.dumps(message))
            except:
                disconnected.append(user_id)
    
    for uid in disconnected:
        if uid in active_connections:
            del active_connections[uid]

async def handle_webrtc_offer(message: dict, sender_id: str):
    """Handle WebRTC offer for video calls"""
    target_id = message.get("target_id")
    if target_id and target_id in active_connections:
        try:
            await active_connections[target_id].send_text(json.dumps({
                "type": "webrtc_offer",
                "offer": message.get("offer"),
                "sender_id": sender_id
            }))
        except:
            pass

async def handle_webrtc_answer(message: dict, sender_id: str):
    """Handle WebRTC answer for video calls"""
    target_id = message.get("target_id")
    if target_id and target_id in active_connections:
        try:
            await active_connections[target_id].send_text(json.dumps({
                "type": "webrtc_answer",
                "answer": message.get("answer"),
                "sender_id": sender_id
            }))
        except:
            pass

async def handle_webrtc_ice(message: dict, sender_id: str):
    """Handle WebRTC ICE candidate"""
    target_id = message.get("target_id")
    if target_id and target_id in active_connections:
        try:
            await active_connections[target_id].send_text(json.dumps({
                "type": "webrtc_ice_candidate",
                "candidate": message.get("candidate"),
                "sender_id": sender_id
            }))
        except:
            pass

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.server_port,
        reload=settings.debug
    )
