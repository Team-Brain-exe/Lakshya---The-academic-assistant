-- Faculty need a display name (students already have one on the students table).
ALTER TABLE users ADD COLUMN IF NOT EXISTS name text;
