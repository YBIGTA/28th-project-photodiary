# Pipeline Architecture & Data Flow

This document explains the end-to-end flow of the **PicTrace** system, from raw photo ingestion to the chatbot interface.

## 1. Data Ingestion & Image Processing

The process begins with raw photos stored in a local directory (assumed `data/` or passed via CLI).

### Entry Point: `pipeline/save_keywords.py`
This script is the main driver for ingesting photos and running AI models.

**Flow:**
1.  **List Photos**: It queries the `photos` table in the database to get a list of target images (`db.crud.list_photos`). *Note: Initial file paths are assumed to be already in the DB or added via a separate ingestion script not shown here, typically `pipeline/save_to_db.py` or similar if it existed, but currently `save_keywords.py` relies on existing rows.*
2.  **RAM++ Tagging**:
    -   Calls `pipeline.ram_tagger.extract_tags_batch`.
    -   Model: **RAM++ (Recognize Anything Plus Plus)**.
    -   Output: List of tags with confidence scores (e.g., "dog(0.9)", "grass(0.8)").
    -   Storage: Saved to `photo_keywords` (link) and `keywords` (metadata) tables via `db.crud.bulk_insert_photo_keywords`.
3.  **Moondream Captioning**:
    -   Calls `pipeline.moondream_captioner.generate_captions_batch`.
    -   Model: **Moondream 2** (Vision Language Model).
    -   Output: A natural language description (e.g., "A dog playing on the grass").
    -   Storage: Saved to `photos.caption` column via `db.crud.update_caption`.

## 2. Event Clustering

### Component: `pipeline/event_clustering.py`
Groups individual photos into "Events" (e.g., "Lunch at Gangnam", "Trip to Busan").

**Logic (`cluster_events` function):**
-   **Input**: Stream of photos with `timestamp` and `GPS`.
-   **Rules**:
    -   **Time Split**: > 2 hours gap → New Event.
    -   **Distance Split**: > 500m move → New Event.
    -   **Stay Detection**: If within 50m of start, timeout extends to 12 hours (to keep "Home" or "Work" as one event).
-   **Storage**: Creates rows in `events` table and links photos via `photos.event_id`.

## 3. Embedding Generation (Vectorization)

### Component: `pipeline/save_embeddings.py`
Prepares photos for Semantic Search.

**Flow:**
1.  **Data gathering**: Fetches Tags + Caption + Place Metadata (GPS address) for each photo.
2.  **Text Combination** (`pipeline.embedder.build_photo_text`):
    -   Combines them into a single string: `"passage: tag1 tag2 | caption | location"`.
3.  **Vectorization** (`pipeline.embedder.embed_photo`):
    -   Model: `intfloat/multilingual-e5-base`.
    -   Output: 768-dimensional vector.
4.  **Storage**: Saved to `photo_embeddings` table (PostgreSQL `pgvector`).

## 4. Backend API (FastAPI)

### Entry Point: `backend/main.py`
-   Initializes the FastAPI app.
-   Mounts routers and static files.
-   **CORS**: Allows requests from Frontend (`localhost:5173`).

### Routers
-   **`backend/routers/photos.py`**:
    -   `POST /api/photos/search`:
        1.  Receives user query (e.g., "Pasta").
        2.  Converts query to vector (`pipeline.embedder.embed_query`).
        3.  Performs vector similarity search in DB (`db.crud.search_photos`).
        4.  Returns top matching photos with similarity scores.
-   **`backend/routers/events.py`**:
    -   `GET /api/events/last`: Returns the most recent clustered event for the Album view.

## 5. Frontend (React)

### API Client: `frontend/src/api/client.js`
-   Abstracts Axios calls to the Backend API.

### Components
-   **`ChatView.jsx`**:
    -   User types message → calls `api.searchPhotos(input)`.
    -   Displays AI response + Photo Gallery (sliding view).
-   **`AlbumView.jsx`**:
    -   Calls `api.getLastEvent()` on load.
    -   Displays summary of the user's latest activity.

## Summary Diagram

```mermaid
graph TD
    User[User/Camera] -->|Files| FS[File System]
    FS -->|Scan| Ingest[Ingestion Script]
    Ingest -->|Insert| DB[(PostgreSQL)]
    
    subgraph "AI Pipeline"
        DB -->|Read| RAM[RAM++]
        RAM -->|Tags| DB
        DB -->|Read| Moon[Moondream 2]
        Moon -->|Captions| DB
        DB -->|Read| Cluster[Event Clustering]
        Cluster -->|Events| DB
        DB -->|Read| Embed[Embedder (e5-base)]
        Embed -->|Vectors| DB
    end
    
    subgraph "Service"
        FastAPI[Backend API] -->|Query| DB
        FastAPI -->|Vector Search| DB
        React[Frontend] -->|JSON| FastAPI
        React -->|Images| FS
    end
```
