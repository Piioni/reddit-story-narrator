-- Tabla principal de posts
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    author TEXT NOT NULL,
    subreddit TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    upvotes INTEGER NOT NULL,
    url TEXT NOT NULL,
    created_utc TIMESTAMP NOT NULL,
    is_nsfw BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de updates/edits de posts
CREATE TABLE IF NOT EXISTS updates (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    update_text TEXT NOT NULL,
    update_order INTEGER NOT NULL,
    created_utc TIMESTAMP NOT NULL,
    upvotes INTEGER NOT NULL,
    url TEXT NOT NULL
);

-- Tabla de comentarios relevantes
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author TEXT,
    text TEXT NOT NULL,
    upvotes INTEGER NOT NULL,
    created_utc TIMESTAMP NOT NULL
);

-- Índices para mejor performance
CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_posts_upvotes ON posts(upvotes DESC);
CREATE INDEX IF NOT EXISTS idx_updates_post_id ON updates(post_id);
CREATE INDEX IF NOT EXISTS idx_updates_order ON updates(post_id, update_order);
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);
CREATE INDEX IF NOT EXISTS idx_comments_upvotes ON comments(upvotes DESC);