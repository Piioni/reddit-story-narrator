-- Tabla principal de posts
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    subreddit TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    upvotes INTEGER NOT NULL,
    url TEXT NOT NULL,
    created_utc TIMESTAMP NOT NULL,
    media_type TEXT DEFAULT 'text',
    media_url TEXT,
    is_nsfw BOOLEAN DEFAULT FALSE,
    full_narrative TEXT,
    narrative_order INTEGER DEFAULT 0,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de updates/edits de posts
CREATE TABLE IF NOT EXISTS updates (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    update_text TEXT NOT NULL,
    update_order INTEGER NOT NULL,
    created_utc TIMESTAMP NOT NULL
);

-- Tabla de comentarios relevantes
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author TEXT,
    text TEXT NOT NULL,
    upvotes INTEGER NOT NULL,
    is_submitter BOOLEAN DEFAULT FALSE,
    is_premium BOOLEAN DEFAULT FALSE,
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

-- Vista para obtener posts con sus updates
CREATE OR REPLACE VIEW posts_with_updates AS
SELECT 
    p.*,
    COALESCE(
        json_agg(
            json_build_object(
                'id', u.id,
                'text', u.update_text,
                'order', u.update_order,
                'created_utc', u.created_utc
            ) ORDER BY u.update_order
        ) FILTER (WHERE u.id IS NOT NULL),
        '[]'::json
    ) as updates
FROM posts p
LEFT JOIN updates u ON p.id = u.post_id
GROUP BY p.id;

-- Vista para obtener posts con comentarios relevantes
CREATE OR REPLACE VIEW posts_with_comments AS
SELECT 
    p.*,
    COALESCE(
        json_agg(
            json_build_object(
                'id', c.id,
                'author', c.author,
                'text', c.text,
                'upvotes', c.upvotes,
                'is_submitter', c.is_submitter,
                'created_utc', c.created_utc
            ) ORDER BY c.upvotes DESC
        ) FILTER (WHERE c.id IS NOT NULL),
        '[]'::json
    ) as comments
FROM posts p
LEFT JOIN comments c ON p.id = c.post_id
GROUP BY p.id;