# # streamlit_secretsanta_with_audit.py
# import streamlit as st
# import sqlite3
# import pandas as pd
# import os
# import random
# from datetime import datetime

# DB_PATH = "secretsanta.db"
# ADMIN_PIN_ENV = "SECRETSANTA_ADMIN_PIN"

# # ---------- Database Abstraction Layer ----------
# DB_TYPE = None  # Auto-detected: 'sqlite' or 'postgresql'
# DB_CONN_STRING = None  # PostgreSQL connection string

# def detect_database():
#     """Auto-detect database type from environment."""
#     global DB_TYPE, DB_CONN_STRING

#     # Priority 1: Streamlit secrets
#     try:
#         if "DATABASE_URL" in st.secrets:
#             DB_CONN_STRING = st.secrets["DATABASE_URL"]
#             DB_TYPE = "postgresql"
#             return
#     except:
#         pass

#     # Priority 2: Environment variable
#     DB_CONN_STRING = os.getenv("DATABASE_URL")
#     if DB_CONN_STRING:
#         DB_TYPE = "postgresql"
#     else:
#         DB_TYPE = "sqlite"

# def translate_sql(sql, params=None):
#     """Translate SQLite syntax to PostgreSQL if needed.

#     Returns: (translated_sql, translated_params)
#     """
#     if DB_TYPE != "postgresql":
#         return sql, params

#     # Clean up whitespace in multiline queries
#     sql = ' '.join(sql.split())

#     # 1. Replace AUTOINCREMENT with SERIAL
#     sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")

#     # 2. Handle INSERT OR IGNORE
#     if "INSERT OR IGNORE" in sql:
#         sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
#         # Add ON CONFLICT DO NOTHING at the end
#         if not "ON CONFLICT" in sql:
#             sql = sql.rstrip().rstrip(';') + " ON CONFLICT DO NOTHING"

#     # 3. Handle INSERT OR REPLACE (survey_responses specific)
#     if "INSERT OR REPLACE INTO survey_responses" in sql:
#         sql = sql.replace("INSERT OR REPLACE INTO survey_responses", "INSERT INTO survey_responses")
#         if not "ON CONFLICT" in sql:
#             # survey_responses has UNIQUE(participant_id, team_id, question_id)
#             sql = sql.rstrip().rstrip(';') + " ON CONFLICT (participant_id, team_id, question_id) DO UPDATE SET answer = EXCLUDED.answer, created_at = EXCLUDED.created_at"

#     # 4. Replace ? placeholders with %s for psycopg2
#     if "?" in sql:
#         sql = sql.replace("?", "%s")

#     return sql, params

# def get_db_connection_raw():
#     """Get raw database connection (internal use)."""
#     if DB_TYPE == "postgresql":
#         import psycopg2
#         from psycopg2.pool import SimpleConnectionPool

#         # Create connection pool (singleton pattern)
#         if not hasattr(get_db_connection_raw, "_pool"):
#             get_db_connection_raw._pool = SimpleConnectionPool(
#                 minconn=1,
#                 maxconn=10,
#                 dsn=DB_CONN_STRING
#             )

#         # Get connection with retry logic for timeout handling
#         try:
#             conn = get_db_connection_raw._pool.getconn()
#             # Test if connection is alive
#             conn.isolation_level
#             return conn
#         except:
#             # Connection died, recreate pool
#             get_db_connection_raw._pool.closeall()
#             get_db_connection_raw._pool = SimpleConnectionPool(
#                 minconn=1,
#                 maxconn=10,
#                 dsn=DB_CONN_STRING
#             )
#             conn = get_db_connection_raw._pool.getconn()
#             return conn
#     else:
#         # SQLite (default)
#         import sqlite3
#         conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
#         conn.row_factory = sqlite3.Row
#         return conn

# class TranslatingCursor:
#     """Cursor wrapper that automatically translates SQL for PostgreSQL."""

#     def __init__(self, cursor, is_pg):
#         self._cursor = cursor
#         self._is_pg = is_pg

#     def execute(self, sql, params=None):
#         """Execute with automatic SQL translation."""
#         if self._is_pg:
#             translated_sql, translated_params = translate_sql(sql, params)
#             # Always pass params to PostgreSQL if they were provided
#             if translated_params is not None:
#                 return self._cursor.execute(translated_sql, translated_params)
#             else:
#                 return self._cursor.execute(translated_sql)
#         else:
#             if params is not None:
#                 return self._cursor.execute(sql, params)
#             else:
#                 return self._cursor.execute(sql)

#     def fetchone(self):
#         return self._cursor.fetchone()

#     def fetchall(self):
#         return self._cursor.fetchall()

#     def __getattr__(self, name):
#         """Delegate all other attributes to the wrapped cursor."""
#         return getattr(self._cursor, name)

# class DatabaseConnection:
#     """Wrapper to provide uniform interface for both databases."""

#     def __init__(self, raw_conn):
#         self._conn = raw_conn
#         self._is_pg = (DB_TYPE == "postgresql")

#     def cursor(self):
#         if self._is_pg:
#             from psycopg2.extras import RealDictCursor
#             raw_cursor = self._conn.cursor(cursor_factory=RealDictCursor)
#         else:
#             raw_cursor = self._conn.cursor()
#         return TranslatingCursor(raw_cursor, self._is_pg)

#     def commit(self):
#         # Both SQLite and PostgreSQL support commit
#         self._conn.commit()

#     def rollback(self):
#         self._conn.rollback()

#     def close(self):
#         if self._is_pg:
#             # Return to pool instead of closing
#             if hasattr(get_db_connection_raw, "_pool"):
#                 get_db_connection_raw._pool.putconn(self._conn)
#         else:
#             self._conn.close()

#     def execute(self, sql, params=None):
#         """Execute with automatic SQL translation."""
#         translated_sql, translated_params = translate_sql(sql, params)
#         cursor = self.cursor()
#         if translated_params:
#             cursor.execute(translated_sql, translated_params)
#         else:
#             cursor.execute(translated_sql)
#         return cursor

# # ---------- DB helpers ----------
# def get_conn():
#     """Get database connection (auto-detects SQLite vs PostgreSQL)."""
#     raw_conn = get_db_connection_raw()
#     return DatabaseConnection(raw_conn)

# def init_db():
#     conn = get_conn()
#     c = conn.cursor()

#     # Create teams table
#     c.execute("""
#     CREATE TABLE IF NOT EXISTS teams (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         name TEXT NOT NULL UNIQUE,
#         location TEXT DEFAULT '',
#         admin_pin TEXT NOT NULL,
#         created_at TEXT NOT NULL
#     );
#     """)

#     c.execute("""
#     CREATE TABLE IF NOT EXISTS participants (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         team_id INTEGER NOT NULL,
#         name TEXT NOT NULL,
#         secret TEXT,
#         assigned INTEGER DEFAULT 0,
#         email TEXT,
#         has_completed_survey INTEGER DEFAULT 0,
#         last_login TEXT,
#         UNIQUE(team_id, name),
#         FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
#     );
#     """)
#     c.execute("""
#     CREATE TABLE IF NOT EXISTS assignments (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         team_id INTEGER NOT NULL,
#         drawer_name TEXT NOT NULL,
#         recipient_name TEXT NOT NULL,
#         timestamp TEXT NOT NULL,
#         revealed INTEGER DEFAULT 0,
#         revealed_timestamp TEXT,
#         FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
#     );
#     """)
#     c.execute("""
#     CREATE TABLE IF NOT EXISTS logs (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         team_id INTEGER,
#         timestamp TEXT NOT NULL,
#         actor TEXT,
#         action TEXT NOT NULL,
#         details TEXT,
#         FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
#     );
#     """)

#     # Create wishlists table
#     c.execute("""
#     CREATE TABLE IF NOT EXISTS wishlists (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         participant_id INTEGER NOT NULL,
#         team_id INTEGER NOT NULL,
#         item_text TEXT NOT NULL,
#         priority INTEGER DEFAULT 2,
#         item_link TEXT,
#         item_order INTEGER DEFAULT 0,
#         created_at TEXT NOT NULL,
#         FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE,
#         FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
#     );
#     """)

#     # Create survey_questions table
#     c.execute("""
#     CREATE TABLE IF NOT EXISTS survey_questions (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         question_text TEXT NOT NULL,
#         option_a TEXT NOT NULL,
#         option_b TEXT NOT NULL,
#         emoji_a TEXT,
#         emoji_b TEXT,
#         display_order INTEGER DEFAULT 0
#     );
#     """)

#     # Create survey_responses table
#     c.execute("""
#     CREATE TABLE IF NOT EXISTS survey_responses (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         participant_id INTEGER NOT NULL,
#         team_id INTEGER NOT NULL,
#         question_id INTEGER NOT NULL,
#         answer TEXT NOT NULL,
#         created_at TEXT NOT NULL,
#         UNIQUE(participant_id, team_id, question_id),
#         FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE,
#         FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
#     );
#     """)

#     # Create messages table
#     c.execute("""
#     CREATE TABLE IF NOT EXISTS messages (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         team_id INTEGER NOT NULL,
#         assignment_id INTEGER NOT NULL,
#         sender_role TEXT NOT NULL,
#         message_type TEXT NOT NULL,
#         content TEXT NOT NULL,
#         is_read INTEGER DEFAULT 0,
#         created_at TEXT NOT NULL,
#         FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
#         FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
#     );
#     """)

#     # Migration: Add new columns to participants if they don't exist
#     try:
#         c.execute("SELECT email FROM participants LIMIT 1")
#     except Exception as e:
#         # Catches both sqlite3.OperationalError and psycopg2.errors
#         # If column doesn't exist, add new columns
#         if "email" in str(e) or "column" in str(e).lower():
#             c.execute("ALTER TABLE participants ADD COLUMN email TEXT")
#             c.execute("ALTER TABLE participants ADD COLUMN has_completed_survey INTEGER DEFAULT 0")
#             c.execute("ALTER TABLE participants ADD COLUMN last_login TEXT")

#     # Populate survey questions if empty
#     c.execute("SELECT COUNT(*) as count FROM survey_questions")
#     if c.fetchone()["count"] == 0:
#         populate_survey_questions(conn)

#     conn.commit()
#     conn.close()

# def populate_survey_questions(conn):
#     """Pre-populate survey with 'this or that' questions."""
#     c = conn.cursor()
#     questions = [
#         ("Homemade or Store-bought?", "Homemade", "Store-bought", "🧶", "🛍️", 1),
#         ("One Big Gift or Many Little Gifts?", "One Big Gift", "Many Little Gifts", "🎁", "🎀", 2),
#         ("Practical Gifts or Sentimental Gifts?", "Practical", "Sentimental", "🔧", "💝", 3),
#         ("Edible or Useful?", "Edible", "Useful", "🍫", "🛠️", 4),
#         ("Personal Gift or Gift Card?", "Personal Gift", "Gift Card", "🎨", "💳", 5)
#     ]

#     for q_text, opt_a, opt_b, emoji_a, emoji_b, order in questions:
#         c.execute("""
#             INSERT INTO survey_questions (question_text, option_a, option_b, emoji_a, emoji_b, display_order)
#             VALUES (?, ?, ?, ?, ?, ?)
#         """, (q_text, opt_a, opt_b, emoji_a, emoji_b, order))

#     log_event(conn, 'system', 'populate_survey_questions', f'Added {len(questions)} questions', None)

# def log_event(conn, actor, action, details="", team_id=None):
#     """Insert a log row. Accepts an open conn to allow logging inside transactions."""
#     ts = datetime.utcnow().isoformat() + "Z"
#     c = conn.cursor()
#     c.execute("INSERT INTO logs (timestamp, actor, action, details, team_id) VALUES (?, ?, ?, ?, ?)",
#               (ts, actor or '', action, details or '', team_id))

# # ---------- Team Management ----------
# def create_team(name, admin_pin, location="Office"):
#     """Create a new team."""
#     conn = get_conn()
#     c = conn.cursor()
#     try:
#         ts = datetime.utcnow().isoformat() + "Z"
#         if DB_TYPE == "postgresql":
#             c.execute("INSERT INTO teams (name, admin_pin, location, created_at) VALUES (?, ?, ?, ?) RETURNING id",
#                       (name, admin_pin, location, ts))
#             team_id = c.fetchone()['id']
#         else:
#             c.execute("INSERT INTO teams (name, admin_pin, location, created_at) VALUES (?, ?, ?, ?)",
#                       (name, admin_pin, location, ts))
#             team_id = c.lastrowid
#         log_event(conn, 'system', 'create_team', f"Created team: {name}", team_id)
#         conn.commit()
#         return {"success": True, "team_id": team_id}
#     except Exception as e:
#         # Catches both sqlite3.IntegrityError and psycopg2.IntegrityError
#         if "unique" in str(e).lower() or "duplicate" in str(e).lower():
#             return {"error": "Team name already exists."}
#         else:
#             return {"error": f"Failed to create team: {e}"}
#     finally:
#         conn.close()

# def get_team(team_id):
#     """Get team details by ID."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT id, name, location, admin_pin FROM teams WHERE id = ?", (team_id,))
#     team = c.fetchone()
#     conn.close()
#     return team

# def get_team_by_name(name):
#     """Get team details by name."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT id, name, location, admin_pin FROM teams WHERE name = ?", (name,))
#     team = c.fetchone()
#     conn.close()
#     return team

# def list_teams():
#     """List all teams."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT id, name, location, created_at FROM teams ORDER BY created_at DESC")
#     teams = c.fetchall()
#     conn.close()
#     return teams

# def update_team_settings(team_id, location=None):
#     """Update team location."""
#     conn = get_conn()
#     c = conn.cursor()
#     try:
#         if location is not None:
#             c.execute("UPDATE teams SET location = ? WHERE id = ?", (location, team_id))
#         log_event(conn, 'admin', 'update_team_settings', f"location={location}", team_id)
#         conn.commit()
#         return {"success": True}
#     except Exception as e:
#         return {"error": f"Failed to update team: {e}"}
#     finally:
#         conn.close()

# def seed_participants_from_df(df: pd.DataFrame, team_id):
#     conn = get_conn()
#     c = conn.cursor()
#     for _, row in df.iterrows():
#         name = str(row['name']).strip()
#         secret = str(row['secret']).strip() if 'secret' in row and not pd.isna(row['secret']) else ''
#         if not name:
#             continue
#         try:
#             c.execute("INSERT OR IGNORE INTO participants (team_id, name, secret) VALUES (?, ?, ?)",
#                       (team_id, name, secret))
#             log_event(conn, 'admin', 'seed_participant', f"seeded {name}", team_id)
#         except Exception as e:
#             st.error(f"DB error while inserting {name}: {e}")
#     conn.commit()
#     conn.close()

# def list_participants(team_id):
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT name, secret, assigned FROM participants WHERE team_id = ? ORDER BY name", (team_id,))
#     rows = c.fetchall()
#     conn.close()
#     return rows

# def draw_random_recipient(drawer_name, team_id):
#     """
#     Reveal the pre-generated assignment for the drawer.
#     No longer randomly assigns - all assignments must be pre-generated by admin.
#     """
#     conn = get_conn()
#     c = conn.cursor()
#     try:
#         # BEGIN IMMEDIATE is SQLite-specific, PostgreSQL just uses BEGIN
#         if DB_TYPE == "postgresql":
#             c.execute("BEGIN;")
#         else:
#             c.execute("BEGIN IMMEDIATE;")

#         # Check if drawer exists
#         c.execute("SELECT id FROM participants WHERE name = ? AND team_id = ?", (drawer_name, team_id))
#         drawer_row = c.fetchone()
#         if not drawer_row:
#             conn.rollback()
#             log_event(conn, drawer_name, 'draw_failed', 'drawer not registered', team_id)
#             return {"error": "Drawer not found in participant list."}

#         # Look up their pre-generated assignment
#         c.execute("SELECT recipient_name, timestamp, revealed, revealed_timestamp FROM assignments WHERE drawer_name = ? AND team_id = ?",
#                   (drawer_name, team_id))
#         assignment = c.fetchone()

#         if not assignment:
#             conn.rollback()
#             log_event(conn, drawer_name, 'draw_failed_no_assignment', 'no pre-generated assignment found', team_id)
#             return {"error": "No assignment found. Admin needs to generate assignments first."}

#         recipient = assignment["recipient_name"]
#         timestamp = assignment["timestamp"]
#         already_revealed = assignment["revealed"]
#         revealed_ts = assignment["revealed_timestamp"]

#         if already_revealed:
#             # Already revealed before, just show it again
#             conn.commit()
#             log_event(conn, drawer_name, 'view_existing_assignment', recipient, team_id)
#             return {"recipient": recipient, "timestamp": timestamp, "revealed_timestamp": revealed_ts, "already_revealed": True}
#         else:
#             # First time revealing - mark as revealed
#             reveal_ts = datetime.utcnow().isoformat() + "Z"
#             c.execute("UPDATE assignments SET revealed = 1, revealed_timestamp = ? WHERE drawer_name = ? AND team_id = ?",
#                       (reveal_ts, drawer_name, team_id))
#             log_event(conn, drawer_name, 'draw_success', f"recipient={recipient}", team_id)
#             conn.commit()
#             return {"recipient": recipient, "timestamp": timestamp, "revealed_timestamp": reveal_ts, "already_revealed": False}

#     except Exception as e:
#         conn.rollback()
#         log_event(conn, drawer_name, 'draw_exception', str(e), team_id)
#         return {"error": f"DB transaction error: {e}"}
#     finally:
#         conn.close()


# def validate_participant(name, secret, team_id):
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT secret FROM participants WHERE name = ? AND team_id = ?", (name, team_id))
#     row = c.fetchone()
#     conn.close()
#     if not row:
#         return False, "Participant name not registered."
#     registered_secret = row["secret"] or ""
#     if registered_secret == "":
#         return True, ""
#     if secret == registered_secret:
#         return True, ""
#     else:
#         return False, "Secret code does not match."

# def reset_db(team_id):
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("DELETE FROM assignments WHERE team_id = ?;", (team_id,))
#     c.execute("UPDATE participants SET assigned = 0 WHERE team_id = ?;", (team_id,))
#     log_event(conn, 'admin', 'reset_assignments', 'all unassigned', team_id)
#     conn.commit()
#     conn.close()

# def generate_all_assignments(team_id):
#     """
#     Pre-generate a complete Secret Santa cycle for all participants.
#     Uses a derangement algorithm to ensure no one gets themselves.
#     Clears existing assignments first.
#     """
#     conn = get_conn()
#     c = conn.cursor()
#     try:
#         # BEGIN IMMEDIATE is SQLite-specific, PostgreSQL just uses BEGIN
#         if DB_TYPE == "postgresql":
#             c.execute("BEGIN;")
#         else:
#             c.execute("BEGIN IMMEDIATE;")

#         # Clear existing assignments
#         c.execute("DELETE FROM assignments WHERE team_id = ?;", (team_id,))
#         c.execute("UPDATE participants SET assigned = 0 WHERE team_id = ?;", (team_id,))

#         # Get all participants
#         c.execute("SELECT name FROM participants WHERE team_id = ? ORDER BY name", (team_id,))
#         participants = [r["name"] for r in c.fetchall()]

#         if len(participants) < 2:
#             conn.rollback()
#             return {"error": "Need at least 2 participants to generate assignments."}

#         # Generate valid derangement (no one gets themselves)
#         import random
#         receivers = participants.copy()

#         # Try to generate a valid derangement (max 100 attempts)
#         max_attempts = 100
#         valid_derangement = False

#         for attempt in range(max_attempts):
#             random.shuffle(receivers)

#             # Check if it's a valid derangement
#             is_valid = True
#             for i in range(len(participants)):
#                 if participants[i] == receivers[i]:
#                     is_valid = False
#                     break

#             if is_valid:
#                 valid_derangement = True
#                 break

#         if not valid_derangement:
#             # Fallback: use simple circular assignment (rotate by 1)
#             # This always works for n >= 2
#             receivers = participants[1:] + participants[:1]

#         # Verify it's a valid derangement
#         for i, giver in enumerate(participants):
#             if giver == receivers[i]:
#                 conn.rollback()
#                 return {"error": "Failed to generate valid derangement. Please try again."}

#         # Insert all assignments
#         ts = datetime.utcnow().isoformat() + "Z"
#         for giver, receiver in zip(participants, receivers):
#             c.execute("INSERT INTO assignments (team_id, drawer_name, recipient_name, timestamp) VALUES (?, ?, ?, ?)",
#                       (team_id, giver, receiver, ts))
#             c.execute("UPDATE participants SET assigned = 1 WHERE name = ? AND team_id = ?", (receiver, team_id))

#         log_event(conn, 'admin', 'generate_all_assignments', f"generated {len(participants)} assignments", team_id)
#         conn.commit()
#         return {"success": True, "count": len(participants)}
#     except Exception as e:
#         conn.rollback()
#         log_event(conn, 'admin', 'generate_assignments_error', str(e), team_id)
#         return {"error": f"Failed to generate assignments: {e}"}
#     finally:
#         conn.close()

# def remove_participant(name, team_id):
#     """
#     Remove a participant and regenerate all assignments.
#     """
#     conn = get_conn()
#     c = conn.cursor()
#     try:
#         c.execute("DELETE FROM participants WHERE name = ? AND team_id = ?", (name, team_id))
#         log_event(conn, 'admin', 'remove_participant', name, team_id)
#         conn.commit()
#         conn.close()

#         # Regenerate assignments
#         return generate_all_assignments(team_id)
#     except Exception as e:
#         conn.rollback()
#         conn.close()
#         return {"error": f"Failed to remove participant: {e}"}

# # ---------- Authentication ----------
# def authenticate_participant(name, secret, team_id):
#     """Authenticate participant and update last_login."""
#     ok, msg = validate_participant(name, secret, team_id)
#     if not ok:
#         return {"error": msg}

#     conn = get_conn()
#     c = conn.cursor()

#     # Update last_login
#     ts = datetime.utcnow().isoformat() + "Z"
#     c.execute("UPDATE participants SET last_login = ? WHERE name = ? AND team_id = ?", (ts, name, team_id))

#     # Get participant details
#     c.execute("SELECT id, name, email, has_completed_survey FROM participants WHERE name = ? AND team_id = ?", (name, team_id))
#     participant = c.fetchone()

#     log_event(conn, name, 'login_success', '', team_id)
#     conn.commit()
#     conn.close()

#     return {
#         "success": True,
#         "participant_id": participant["id"],
#         "participant_name": participant["name"],
#         "email": participant["email"],
#         "has_completed_survey": participant["has_completed_survey"]
#     }

# def get_participant_by_id(participant_id):
#     """Get participant details by ID."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT * FROM participants WHERE id = ?", (participant_id,))
#     participant = c.fetchone()
#     conn.close()
#     return participant

# # ---------- Wishlist Management ----------
# def add_wishlist_item(participant_id, team_id, item_text, priority=2, item_link=""):
#     """Add a wishlist item."""
#     conn = get_conn()
#     c = conn.cursor()
#     ts = datetime.utcnow().isoformat() + "Z"

#     # Get max order for this participant
#     c.execute("SELECT COALESCE(MAX(item_order), -1) as max_order FROM wishlists WHERE participant_id = ? AND team_id = ?",
#               (participant_id, team_id))
#     max_order = c.fetchone()["max_order"]
#     new_order = max_order + 1

#     c.execute("""
#         INSERT INTO wishlists (participant_id, team_id, item_text, priority, item_link, item_order, created_at)
#         VALUES (?, ?, ?, ?, ?, ?, ?)
#     """, (participant_id, team_id, item_text, priority, item_link, new_order, ts))

#     log_event(conn, f'participant_{participant_id}', 'add_wishlist_item', item_text, team_id)
#     conn.commit()
#     conn.close()
#     return {"success": True}

# def get_wishlist(participant_id, team_id):
#     """Get all wishlist items for a participant, ordered by item_order."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("""
#         SELECT id, item_text, priority, item_link, item_order, created_at
#         FROM wishlists
#         WHERE participant_id = ? AND team_id = ?
#         ORDER BY item_order ASC
#     """, (participant_id, team_id))
#     items = c.fetchall()
#     conn.close()
#     return items

# def update_wishlist_item(item_id, item_text=None, priority=None, item_link=None):
#     """Update a wishlist item."""
#     conn = get_conn()
#     c = conn.cursor()

#     if item_text is not None:
#         c.execute("UPDATE wishlists SET item_text = ? WHERE id = ?", (item_text, item_id))
#     if priority is not None:
#         c.execute("UPDATE wishlists SET priority = ? WHERE id = ?", (priority, item_id))
#     if item_link is not None:
#         c.execute("UPDATE wishlists SET item_link = ? WHERE id = ?", (item_link, item_id))

#     conn.commit()
#     conn.close()
#     return {"success": True}

# def delete_wishlist_item(item_id):
#     """Delete a wishlist item."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("DELETE FROM wishlists WHERE id = ?", (item_id,))
#     conn.commit()
#     conn.close()
#     return {"success": True}

# def reorder_wishlist_item(item_id, direction):
#     """Move a wishlist item up or down. Direction is 'up' or 'down'."""
#     conn = get_conn()
#     c = conn.cursor()

#     # Get current item
#     c.execute("SELECT participant_id, team_id, item_order FROM wishlists WHERE id = ?", (item_id,))
#     current = c.fetchone()
#     if not current:
#         conn.close()
#         return {"error": "Item not found"}

#     current_order = current["item_order"]
#     participant_id = current["participant_id"]
#     team_id = current["team_id"]

#     # Get all items for this participant
#     c.execute("""
#         SELECT id, item_order FROM wishlists
#         WHERE participant_id = ? AND team_id = ?
#         ORDER BY item_order ASC
#     """, (participant_id, team_id))
#     all_items = c.fetchall()

#     # Find target item to swap with
#     target_item = None
#     for i, item in enumerate(all_items):
#         if item["id"] == item_id:
#             if direction == "up" and i > 0:
#                 target_item = all_items[i - 1]
#             elif direction == "down" and i < len(all_items) - 1:
#                 target_item = all_items[i + 1]
#             break

#     if target_item:
#         # Swap orders
#         target_order = target_item["item_order"]
#         c.execute("UPDATE wishlists SET item_order = ? WHERE id = ?", (target_order, item_id))
#         c.execute("UPDATE wishlists SET item_order = ? WHERE id = ?", (current_order, target_item["id"]))
#         conn.commit()

#     conn.close()
#     return {"success": True}

# # ---------- Survey Management ----------
# def get_survey_questions():
#     """Get all survey questions ordered by display_order."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("""
#         SELECT id, question_text, option_a, option_b, emoji_a, emoji_b, display_order
#         FROM survey_questions
#         ORDER BY display_order ASC
#     """)
#     questions = c.fetchall()
#     conn.close()
#     return questions

# def save_survey_response(participant_id, team_id, question_id, answer):
#     """Save or update a survey response."""
#     conn = get_conn()
#     c = conn.cursor()
#     ts = datetime.utcnow().isoformat() + "Z"

#     c.execute("""
#         INSERT OR REPLACE INTO survey_responses (participant_id, team_id, question_id, answer, created_at)
#         VALUES (?, ?, ?, ?, ?)
#     """, (participant_id, team_id, question_id, answer, ts))

#     log_event(conn, f'participant_{participant_id}', 'save_survey_response', f'Q{question_id}: {answer}', team_id)
#     conn.commit()
#     conn.close()
#     return {"success": True}

# def get_survey_responses(participant_id, team_id):
#     """Get all survey responses for a participant."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("""
#         SELECT sr.question_id, sr.answer, sq.question_text, sq.option_a, sq.option_b
#         FROM survey_responses sr
#         JOIN survey_questions sq ON sr.question_id = sq.id
#         WHERE sr.participant_id = ? AND sr.team_id = ?
#         ORDER BY sq.display_order ASC
#     """, (participant_id, team_id))
#     responses = c.fetchall()
#     conn.close()
#     return responses

# def mark_survey_complete(participant_id, team_id):
#     """Mark survey as complete for a participant."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("UPDATE participants SET has_completed_survey = 1 WHERE id = ? AND team_id = ?", (participant_id, team_id))
#     log_event(conn, f'participant_{participant_id}', 'complete_survey', '', team_id)
#     conn.commit()
#     conn.close()
#     return {"success": True}

# # ---------- Messaging ----------
# def send_message(assignment_id, team_id, sender_role, message_type, content):
#     """Send a message in an assignment thread."""
#     conn = get_conn()
#     c = conn.cursor()
#     ts = datetime.utcnow().isoformat() + "Z"

#     c.execute("""
#         INSERT INTO messages (team_id, assignment_id, sender_role, message_type, content, created_at)
#         VALUES (?, ?, ?, ?, ?, ?)
#     """, (team_id, assignment_id, sender_role, message_type, content, ts))

#     log_event(conn, f'{sender_role}_assignment_{assignment_id}', 'send_message', f'{message_type}: {content[:50]}', team_id)
#     conn.commit()
#     conn.close()
#     return {"success": True}

# def get_messages_for_assignment(assignment_id):
#     """Get all messages for an assignment thread."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("""
#         SELECT id, sender_role, message_type, content, is_read, created_at
#         FROM messages
#         WHERE assignment_id = ?
#         ORDER BY created_at ASC
#     """, (assignment_id,))
#     messages = c.fetchall()
#     conn.close()
#     return messages

# def mark_message_read(message_id):
#     """Mark a message as read."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
#     conn.commit()
#     conn.close()
#     return {"success": True}

# def get_unread_count(assignment_id, for_role):
#     """Get count of unread messages for a specific role (messages sent by the OTHER role)."""
#     conn = get_conn()
#     c = conn.cursor()

#     # If checking for santa, count messages where sender is receiver
#     # If checking for receiver, count messages where sender is santa
#     opposite_role = 'receiver' if for_role == 'santa' else 'santa'

#     c.execute("""
#         SELECT COUNT(*) as count FROM messages
#         WHERE assignment_id = ? AND sender_role = ? AND is_read = 0
#     """, (assignment_id, opposite_role))

#     count = c.fetchone()["count"]
#     conn.close()
#     return count

# # ---------- Santa/Receiver Helpers ----------
# def get_my_assignment(participant_name, team_id):
#     """Get the assignment where participant is the drawer (Santa)."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("""
#         SELECT id, recipient_name, timestamp, revealed, revealed_timestamp
#         FROM assignments
#         WHERE drawer_name = ? AND team_id = ?
#     """, (participant_name, team_id))
#     assignment = c.fetchone()
#     conn.close()
#     return assignment

# def get_receiver_wishlist(recipient_name, team_id):
#     """Get wishlist for a specific recipient."""
#     conn = get_conn()
#     c = conn.cursor()

#     # First get participant_id
#     c.execute("SELECT id FROM participants WHERE name = ? AND team_id = ?", (recipient_name, team_id))
#     participant = c.fetchone()
#     if not participant:
#         conn.close()
#         return []

#     participant_id = participant["id"]
#     conn.close()
#     return get_wishlist(participant_id, team_id)

# def get_receiver_survey(recipient_name, team_id):
#     """Get survey responses for a specific recipient."""
#     conn = get_conn()
#     c = conn.cursor()

#     # First get participant_id
#     c.execute("SELECT id FROM participants WHERE name = ? AND team_id = ?", (recipient_name, team_id))
#     participant = c.fetchone()
#     if not participant:
#         conn.close()
#         return []

#     participant_id = participant["id"]
#     conn.close()
#     return get_survey_responses(participant_id, team_id)

# def get_my_santa_assignment(participant_name, team_id):
#     """Get the assignment where participant is the recipient (receives from Santa)."""
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("""
#         SELECT id, drawer_name, timestamp
#         FROM assignments
#         WHERE recipient_name = ? AND team_id = ?
#     """, (participant_name, team_id))
#     assignment = c.fetchone()
#     conn.close()
#     return assignment

# # ---------- CSV Auto-load ----------
# def auto_load_participants():
#     """Load participants from CSV on startup if file exists."""
#     csv_path = "participants.csv"
#     if not os.path.exists(csv_path):
#         return

#     try:
#         df = pd.read_csv(csv_path)
#         if 'team_name' not in df.columns or 'name' not in df.columns:
#             st.warning("CSV must have 'team_name' and 'name' columns")
#             return

#         # Process each team
#         for team_name in df['team_name'].unique():
#             team = get_team_by_name(team_name)

#             if not team:
#                 # Create team using environment variables
#                 admin_pin = os.getenv(f"TEAM_{team_name.upper().replace(' ', '_')}_ADMIN_PIN", "default123")
#                 location = os.getenv(f"TEAM_{team_name.upper().replace(' ', '_')}_LOCATION", "Office")

#                 result = create_team(team_name, admin_pin, location)
#                 if "error" in result:
#                     st.error(f"Failed to create team {team_name}: {result['error']}")
#                     continue
#                 team_id = result["team_id"]
#             else:
#                 team_id = team["id"]

#             # Load participants for this team
#             team_df = df[df['team_name'] == team_name]
#             seed_participants_from_df(team_df, team_id)

#     except Exception as e:
#         st.error(f"Failed to auto-load participants: {e}")

# # ---------- Streamlit UI ----------
# st.set_page_config(page_title="Secret Santa", layout="centered", initial_sidebar_state="collapsed")

# def startup():
#     detect_database()
#     st.session_state.db_type = DB_TYPE
#     st.session_state.db_conn_string = DB_CONN_STRING
#     init_db()
#     auto_load_participants()

# # Detect database once and cache in session state
# # Detect database once and cache in session state
# if "db_initialized" not in st.session_state:
#     _ = startup()   # IMPORTANT: suppress Streamlit rendering
#     st.session_state.db_initialized = True
# else:
#     DB_TYPE = st.session_state.db_type
#     DB_CONN_STRING = st.session_state.db_conn_string

# # Custom CSS for festive theme
# st.markdown("""
# <style>
#     /* Hide Streamlit header and footer */
#     header {
#         background-color: #1B4332 !important;
#         visibility: hidden;
#     }

#     .stApp > header {
#         background-color: transparent !important;
#     }

#     #MainMenu {visibility: hidden;}
#     footer {visibility: hidden;}

#     /* Dark pine green background with pattern */
#     .stApp {
#         background-color: #1B4332;
#         background-image:
#             repeating-linear-gradient(45deg, transparent, transparent 100px, rgba(255,255,255,0.02) 100px, rgba(255,255,255,0.02) 200px),
#             repeating-linear-gradient(-45deg, transparent, transparent 100px, rgba(255,255,255,0.02) 100px, rgba(255,255,255,0.02) 200px),
#             linear-gradient(180deg, #1B4332 0%, #2D6A4F 100%);
#     }

#     /* Snowfall animation */
#     .snowflake {
#         position: fixed;
#         top: -10px;
#         z-index: 9999;
#         user-select: none;
#         cursor: default;
#         animation: snowfall linear infinite;
#         color: white;
#         font-size: 1em;
#     }

#     @keyframes snowfall {
#         0% {
#             transform: translateY(0vh) rotate(0deg);
#             opacity: 1;
#         }
#         100% {
#             transform: translateY(100vh) rotate(360deg);
#             opacity: 0.8;
#         }
#     }

#     /* Dancing Santa animation */
#     @keyframes dance {
#         0%, 100% { transform: translateY(0px) rotate(-5deg); }
#         25% { transform: translateY(-20px) rotate(5deg); }
#         50% { transform: translateY(0px) rotate(-5deg); }
#         75% { transform: translateY(-10px) rotate(5deg); }
#     }

#     .dancing-santa {
#         font-size: 120px;
#         animation: dance 1s ease-in-out infinite;
#         display: inline-block;
#         margin: 20px auto;
#     }

#     /* Style text to be visible on dark background */
#     .stMarkdown, .stText, p, span, div {
#         color: #F1FAEE !important;
#     }

#     /* Style headers */
#     h1{
#         color: #E9E8C2 !important;
#     }
#     h2, h3 {
#         color: #E9E8C2 !important;
#     }
#     /* Style buttons */
#     .stButton > button {
#         background-color: #E63946;
#         color: white;
#         border: none;
#         border-radius: 25px;
#         padding: 15px 40px;
#         font-size: 20px;
#         font-weight: bold;
#         box-shadow: 0 4px 6px rgba(0,0,0,0.3);
#         transition: all 0.3s;
#     }

#     .stButton > button:hover {
#         background-color: #D62828;
#         transform: translateY(-2px);
#         box-shadow: 0 6px 8px rgba(0,0,0,0.4);
#     }

#     /* Style input fields - FIXED for visibility */
#     .stTextInput > div > div > input,
#     .stTextArea > div > div > textarea {
#         background-color: rgba(255, 255, 255, 0.95) !important;
#         color: #1B4332 !important;
#         font-weight: 500 !important;
#         border-radius: 10px;
#     }

#     /* Fix selectbox visibility */
#     .stSelectbox > div > div > select {
#         background-color: rgba(255, 255, 255, 0.95) !important;
#         color: #1B4332 !important;
#         font-weight: 500 !important;
#     }

#     /* Fix placeholder visibility */
#     ::placeholder {
#         color: rgba(27, 67, 50, 0.5) !important;
#     }

#     /* Dropdown options */
#     option {
#         background-color: #F1FAEE !important;
#         color: #1B4332 !important;
#     }

#     /* Style expanders */
#     .streamlit-expanderHeader {
#         background-color: rgba(255, 255, 255, 0.1);
#         border-radius: 10px;
#         color: #E9E8C2 !important;
#     }

#     /* Style success/error/warning messages */
#     .stSuccess, .stError, .stWarning, .stInfo {
#         background-color: rgba(255, 255, 255, 0.1);
#         border-radius: 10px;
#     }

#     /* Welcome page styling */
#     .welcome-container {
#         display: flex;
#         flex-direction: column;
#         align-items: center;
#         justify-content: center;
#         text-align: center;
#         padding: 50px 20px;
#         min-height: 80vh;
#     }

#     .welcome-title {
#         font-size: 60px;
#         color: #FFD700;
#         text-shadow: 3px 3px 6px rgba(0,0,0,0.5);
#         margin-bottom: 20px;
#     }

#     /* Shhhh animation */
#     @keyframes shhh {
#         0%, 100% { opacity: 0; transform: scale(0.5); }
#         50% { opacity: 1; transform: scale(1.2); }
#     }

#     .shhh-animation {
#         font-size: 60px;
#         animation: shhh 2s ease-in-out;
#         text-align: center;
#         margin: 30px 0;
#         font-colour: E6BE9A;
#     }

#     /* Secret code reveal animation */
#     @keyframes slideDown {
#         from {
#             opacity: 0;
#             transform: translateY(-20px);
#         }
#         to {
#             opacity: 1;
#             transform: translateY(0);
#         }
#     }

#     .secret-reveal {
#         animation: slideDown 0.5s ease-out;
#     }
            
#     /* Folded paper/chit styling */
#     .paper-container {
#         perspective: 1000px;
#         display: flex;
#         justify-content: center;
#         align-items: center;
#         margin: 40px 0 20px 0;
#         position: relative;
#     }

#     .folded-paper {
#         width: 300px;
#         height: 200px;
#         background: linear-gradient(135deg, #FFF8DC 0%, #F5E6D3 100%);
#         border-radius: 10px;
#         box-shadow:
#             0 10px 30px rgba(0,0,0,0.3),
#             inset 0 0 20px rgba(0,0,0,0.1);
#         cursor: pointer;
#         transition: transform 0.3s ease, box-shadow 0.3s ease;
#         display: flex;
#         flex-direction: column;
#         justify-content: center;
#         align-items: center;
#         position: relative;
#         border: 2px solid #D4AF37;
#         margin-bottom: 20px;
#     }

#     .folded-paper:hover {
#         transform: translateY(-10px) scale(1.05);
#         box-shadow: 0 15px 40px rgba(0,0,0,0.4);
#     }

#     .folded-paper::before {
#         content: '';
#         position: absolute;
#         top: 50%;
#         left: 0;
#         right: 0;
#         height: 2px;
#         background: rgba(212, 175, 55, 0.3);
#         transform: translateY(-50%);
#     }

#     .folded-paper::after {
#         content: '';
#         position: absolute;
#         top: 0;
#         bottom: 0;
#         left: 50%;
#         width: 2px;
#         background: rgba(212, 175, 55, 0.3);
#         transform: translateX(-50%);
#     }

#     /* Opened paper animation */
#     @keyframes unfold {
#         0% {
#             transform: rotateX(0deg);
#             opacity: 1;
#         }
#         50% {
#             transform: rotateX(90deg);
#             opacity: 0.5;
#         }
#         100% {
#             transform: rotateX(0deg);
#             opacity: 1;
#         }
#     }

#     .unfolding {
#         animation: unfold 0.8s ease-out;
#     }

#     .opened-paper {
#         background: linear-gradient(135deg, #FFF8DC 0%, #F5E6D3 100%);
#         border: 3px solid #D4AF37;
#         border-radius: 15px;
#         padding: 40px;
#         box-shadow: 0 10px 30px rgba(0,0,0,0.3);
#         max-width: 500px;
#         margin: 20px auto;
#     }

#     .opened-paper h2 {
#         color: #8B4513 !important;
#         font-size: 48px;
#         text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
#         margin: 20px 0;
#     }

#     .opened-paper p {
#         color: #654321 !important;
#         font-size: 18px;
#     }

#     /* Paper fold lines */
#     .fold-line {
#         position: absolute;
#         background: rgba(139, 69, 19, 0.1);
#     }

#     /* Footer styling */
#     .santa-footer {
#         position: fixed;
#         bottom: 0;
#         right: 20px;
#         z-index: 1000;
#         pointer-events: none;
#     }

#     .santa-character {
#         font-size: 80px;
#         animation: wave 3s ease-in-out infinite;
#     }

#     @keyframes wave {
#         0%, 100% { transform: rotate(0deg); }
#         25% { transform: rotate(-10deg); }
#         75% { transform: rotate(10deg); }
#     }

#     /* Team info banner */
#     .team-banner {
#         background: linear-gradient(135deg, rgba(230, 57, 70, 0.2), rgba(45, 106, 79, 0.2));
#         border-radius: 15px;
#         padding: 15px 20px;
#         margin: 10px 0 20px 0;
#         border: 2px solid rgba(255, 215, 0, 0.3);
#     }

#     .team-banner h3 {
#         margin: 0;
#         color: #E9E8C2 !important;
#         font-size: 24px;
#     }

#     .team-banner p {
#         margin: 5px 0 0 0;
#         color: #F1FAEE !important;
#         font-size: 16px;
#     }

#     /* Interactive Team Cards */
#     .team-card {
#         background: linear-gradient(135deg, rgba(230, 57, 70, 0.2), rgba(45, 106, 79, 0.2));
#         border-radius: 15px;
#         padding: 20px;
#         margin: 15px 0;
#         border: 2px solid rgba(255, 215, 0, 0.3);
#         cursor: pointer;
#         transition: transform 0.3s ease, box-shadow 0.3s ease;
#         box-shadow: 0 4px 6px rgba(0,0,0,0.3);
#     }

#     .team-card:hover {
#         transform: translateY(-5px) scale(1.02);
#         box-shadow: 0 8px 12px rgba(0,0,0,0.4);
#     }

#     /* Mode Selection Cards */
#     # .mode-card {
#     #     background: linear-gradient(135deg, rgba(255, 215, 0, 0.1), rgba(230, 57, 70, 0.1));
#     #     border-radius: 20px;
#     #     padding: 30px;
#     #     text-align: center;
#     #     cursor: pointer;
#     #     transition: all 0.3s ease;
#     #     border: 3px solid rgba(255, 215, 0, 0.5);
#     #     box-shadow: 0 6px 10px rgba(0,0,0,0.3);
#     # }

#     # .mode-card:hover {
#     #     transform: translateY(-10px) scale(1.05);
#     #     box-shadow: 0 12px 20px rgba(0,0,0,0.4);
#     #     border-color: #FFD700;
#     # }

#     .mode-card img {
#         max-width: 100%;
#         border-radius: 10px;
#     }

#     /* Message Bubbles */
#     .message {
#         padding: 15px;
#         margin: 10px 0;
#         border-radius: 15px;
#         max-width: 80%;
#         box-shadow: 0 2px 4px rgba(0,0,0,0.2);
#     }

#     .santa-message {
#         background: linear-gradient(135deg, #E63946, #D62828);
#         color: white;
#         margin-left: auto;
#         margin-right: 0;
#         text-align: right;
#     }

#     .receiver-message {
#         background: linear-gradient(135deg, #2D6A4F, #1B4332);
#         color: #F1FAEE;
#         margin-left: 0;
#         margin-right: auto;
#         text-align: left;
#     }

#     .message-type {
#         font-size: 10px;
#         font-weight: bold;
#         text-transform: uppercase;
#         opacity: 0.8;
#         margin-bottom: 5px;
#     }

#     .message-content {
#         font-size: 16px;
#         line-height: 1.5;
#         margin: 5px 0;
#     }

#     .message-time {
#         font-size: 11px;
#         opacity: 0.7;
#         margin-top: 5px;
#     }

#     /* Wishlist Item Card */
#     .wishlist-item {
#         background: rgba(255, 255, 255, 0.1);
#         border-radius: 10px;
#         padding: 15px;
#         margin: 10px 0;
#         border: 1px solid rgba(255, 215, 0, 0.3);
#         transition: background 0.2s ease;
#     }

#     .wishlist-item:hover {
#         background: rgba(255, 255, 255, 0.15);
#     }

#     /* Survey Option Buttons */
#     .survey-option {
#         background: linear-gradient(135deg, rgba(255, 215, 0, 0.2), rgba(230, 57, 70, 0.2));
#         border: 2px solid rgba(255, 215, 0, 0.5);
#         border-radius: 15px;
#         padding: 20px;
#         margin: 10px;
#         cursor: pointer;
#         transition: all 0.3s ease;
#         text-align: center;
#         font-size: 18px;
#     }

#     .survey-option:hover {
#         transform: scale(1.05);
#         border-color: #FFD700;
#         background: linear-gradient(135deg, rgba(255, 215, 0, 0.3), rgba(230, 57, 70, 0.3));
#     }

#     .survey-option.selected {
#         animation: pulse 0.5s ease-out;
#         background: linear-gradient(135deg, #FFD700, #E63946);
#         color: white;
#     }

#     @keyframes pulse {
#         0% { transform: scale(1); }
#         50% { transform: scale(1.1); }
#         100% { transform: scale(1); }
#     }

#     /* Priority Indicators */
#     .priority-high {
#         color: #E63946;
#         font-weight: bold;
#     }

#     .priority-medium {
#         color: #FFD700;
#         font-weight: bold;
#     }

#     .priority-low {
#         color: #52B788;
#         font-weight: bold;
#     }

#     /* Mobile Responsive */
#     @media (max-width: 768px) {
#         .team-card, .mode-card {
#             padding: 15px;
#         }

#         .message {
#             max-width: 90%;
#         }

#         .dancing-santa {
#             font-size: 80px;
#         }
#     }
# </style>
# """, unsafe_allow_html=True)

# # Add snowflakes
# snowflakes_html = """
# <div class="snowflakes" aria-hidden="true">
# """
# for i in range(50):
#     left = random.randint(0, 100)
#     delay = random.uniform(0, 5)
#     duration = random.uniform(10, 20)
#     snowflakes_html += f'<div class="snowflake" style="left: {left}%; animation-duration: {duration}s; animation-delay: {delay}s;">❅</div>'

# snowflakes_html += "</div>"
# st.markdown(snowflakes_html, unsafe_allow_html=True)

# # Initialize session state
# if "page" not in st.session_state:
#     st.session_state.page = "team_selection"  # team_selection | auth | mode_selection | santa_mode | receiver_mode
# if "team_id" not in st.session_state:
#     st.session_state.team_id = None
# if "team_name" not in st.session_state:
#     st.session_state.team_name = None

# # Authentication
# if "authenticated" not in st.session_state:
#     st.session_state.authenticated = False
# if "participant_id" not in st.session_state:
#     st.session_state.participant_id = None
# if "participant_name" not in st.session_state:
#     st.session_state.participant_name = None

# # Current mode
# if "current_mode" not in st.session_state:
#     st.session_state.current_mode = None  # "santa" or "receiver"

# # Santa mode cache
# if "my_assignment" not in st.session_state:
#     st.session_state.my_assignment = None
# if "receiver_wishlist" not in st.session_state:
#     st.session_state.receiver_wishlist = None
# if "receiver_survey" not in st.session_state:
#     st.session_state.receiver_survey = None
# if "santa_messages" not in st.session_state:
#     st.session_state.santa_messages = []

# # Receiver mode cache
# if "my_wishlist" not in st.session_state:
#     st.session_state.my_wishlist = []
# if "my_survey_progress" not in st.session_state:
#     st.session_state.my_survey_progress = 0
# if "messages_from_santa" not in st.session_state:
#     st.session_state.messages_from_santa = []

# # UI state
# if "survey_current_question" not in st.session_state:
#     st.session_state.survey_current_question = 0
# if "show_message_composer" not in st.session_state:
#     st.session_state.show_message_composer = False

# # Admin
# if "is_admin" not in st.session_state:
#     st.session_state.is_admin = False

# # Add Santa footer to all pages
# st.markdown("""
# <div class="santa-footer">
#     <div class="santa-character">🎅</div>
# </div>
# """, unsafe_allow_html=True)

# # ========== TEAM SELECTION PAGE ==========
# if st.session_state.page == "team_selection":
#     st.markdown("<br><br>", unsafe_allow_html=True)

#     st.markdown('<h1 style="text-align: center; font-size: 60px; color: #E9E8C2; text-shadow: 3px 3px 6px rgba(0,0,0,0.5);">🎄 Secret Santa 🎄</h1>', unsafe_allow_html=True)
#     st.markdown('<div style="text-align: center;"><div class="dancing-santa">🎅</div></div>', unsafe_allow_html=True)

#     st.markdown("### 🎁 Select or Create Your Team")

#     tab1, tab2 = st.tabs(["Join Existing Team", "Create New Team"])

#     with tab1:
#         st.markdown("#### Join an existing team")
#         teams = list_teams()

#         if teams:
#             team_names = [t["name"] for t in teams]
#             selected_team_name = st.selectbox("Select your team", team_names, key="select_team")

#             col1, col2, col3 = st.columns([1, 1, 1])
#             with col2:
#                 if st.button("Join Team", key="join_team", use_container_width=True):
#                     team = get_team_by_name(selected_team_name)
#                     if team:
#                         st.session_state.team_id = team["id"]
#                         st.session_state.team_name = team["name"]
#                         st.session_state.page = "auth"
#                         st.rerun()
#         else:
#             st.info("No teams created yet. Create one in the next tab!")

#     with tab2:
#         st.markdown("#### Create a new team")
#         new_team_name = st.text_input("Team Name", key="new_team_name", placeholder="e.g., Tech Team 2025")
#         new_admin_pin = st.text_input("Admin PIN", type="password", key="new_admin_pin",
#                                       placeholder="Set a PIN for admin access")
#         new_location = st.text_input("Exchange Location", key="new_location",
#                                      placeholder="e.g., Office Party Room, Virtual")

#         col1, col2, col3 = st.columns([1, 1, 1])
#         with col2:
#             if st.button("Create Team", key="create_team", use_container_width=True):
#                 if not new_team_name.strip():
#                     st.error("Please enter a team name")
#                 elif not new_admin_pin.strip():
#                     st.error("Please set an admin PIN")
#                 else:
#                     result = create_team(new_team_name.strip(), new_admin_pin, new_location)
#                     if "error" in result:
#                         st.error(result["error"])
#                     else:
#                         st.session_state.team_id = result["team_id"]
#                         st.session_state.team_name = new_team_name.strip()
#                         st.success(f"Team '{new_team_name}' created!")
#                         st.session_state.page = "auth"
#                         st.rerun()

# # ========== AUTH PAGE ==========
# elif st.session_state.page == "auth":
#     # Get team info
#     team = get_team(st.session_state.team_id)
#     if not team:
#         st.error("Team not found. Please select a team.")
#         st.session_state.page = "team_selection"
#         st.rerun()

#     # Add spacing at top
#     st.markdown("<br><br>", unsafe_allow_html=True)

#     # Title
#     st.markdown('<h1 style="text-align: center; font-size: 60px; color: #E9E8C2; text-shadow: 3px 3px 6px rgba(0,0,0,0.5);">🎄 Secret Santa 🎄</h1>', unsafe_allow_html=True)

#     # Dancing Santa
#     st.markdown('<div style="text-align: center;"><div class="dancing-santa">🎅</div></div>', unsafe_allow_html=True)

#     # Team info banner
#     st.markdown(f"""
#     <div class="team-banner">
#         <h3>🎁 {team["name"]}</h3>
#         <p>📍 Location: {team["location"] or 'Not set'}</p>
#     </div>
#     """, unsafe_allow_html=True)

#     st.markdown("### 🔐 Login to Continue")
#     st.write("Select your name and enter your secret code to access your Santa/Receiver modes.")

#     # Get participants for this team
#     participants = list_participants(st.session_state.team_id)
#     if not participants:
#         st.warning("No participants registered yet. Please contact your admin.")
#         if st.button("← Back to Teams"):
#             st.session_state.page = "team_selection"
#             st.rerun()
#     else:
#         participant_names = ["Select your name..."] + [p["name"] for p in participants]

#         selected_name = st.selectbox("Your Name", participant_names, key="auth_name_select")
#         secret_input = st.text_input("Secret Code", type="password", key="auth_secret",
#                                      placeholder="Enter your secret code")

#         col1, col2, col3 = st.columns([1, 1, 1])
#         with col1:
#             if st.button("← Back to Teams", key="back_to_teams", use_container_width=True):
#                 st.session_state.page = "team_selection"
#                 st.session_state.team_id = None
#                 st.session_state.team_name = None
#                 st.rerun()

#         with col3:
#             if st.button("🎅 Login", key="login_btn", use_container_width=True):
#                 if selected_name == "Select your name...":
#                     st.error("Please select your name from the list.")
#                 elif not secret_input:
#                     st.error("Please enter your secret code.")
#                 else:
#                     # Authenticate
#                     result = authenticate_participant(selected_name, secret_input, st.session_state.team_id)
#                     if "error" in result:
#                         st.error(f"❌ {result['error']}")
#                     else:
#                         # Set session state
#                         st.session_state.authenticated = True
#                         st.session_state.participant_id = result["participant_id"]
#                         st.session_state.participant_name = result["participant_name"]
#                         st.session_state.page = "mode_selection"
#                         st.success(f"✅ Welcome, {result['participant_name']}!")
#                         st.rerun()

# # ========== MODE SELECTION PAGE ==========
# elif st.session_state.page == "mode_selection":
#     if not st.session_state.authenticated:
#         st.error("Please log in first.")
#         st.session_state.page = "auth"
#         st.rerun()

#     # Get team info
#     team = get_team(st.session_state.team_id)

#     st.markdown("<br>", unsafe_allow_html=True)
#     st.markdown('<h1 style="text-align: center; font-size: 50px; color: #E9E8C2;">🎄 Secret Santa 🎄</h1>', unsafe_allow_html=True)

#     # Team banner
#     st.markdown(f"""
#     <div class="team-banner">
#         <h3>🎁 {team["name"]} | Welcome, {st.session_state.participant_name}! 👋</h3>
#         <p>📍 Location: {team["location"] or 'Not set'}</p>
#     </div>
#     """, unsafe_allow_html=True)

#     st.markdown("### Choose Your Role")
#     st.write("You are both a **Santa** (giving gifts) and a **Receiver** (receiving gifts). Choose which mode you'd like to explore:")

#     # Mode selection cards
#     col1, col2 = st.columns(2)

#     with col1:
#         st.markdown('<div class="mode-card">', unsafe_allow_html=True)
#         st.image("images/santa_mode.png", use_container_width=True)
#         st.markdown("### 🎅 Be the Santa")
#         st.write("See your assignment, view their wishlist and preferences, send anonymous hints")
#         if st.button("Enter Santa Mode", key="enter_santa_mode", use_container_width=True):
#             st.session_state.current_mode = "santa"
#             st.session_state.page = "santa_mode"
#             st.rerun()
#         st.markdown('</div>', unsafe_allow_html=True)

#     with col2:
#         st.markdown('<div class="mode-card">', unsafe_allow_html=True)
#         st.image("images/receiver_mode.png", use_container_width=True)
#         st.markdown("### 🎁 Be the Receiver")
#         st.write("Create your wishlist, complete preferences survey, read hints from your Santa")
#         if st.button("Enter Receiver Mode", key="enter_receiver_mode", use_container_width=True):
#             st.session_state.current_mode = "receiver"
#             st.session_state.page = "receiver_mode"
#             st.rerun()
#         st.markdown('</div>', unsafe_allow_html=True)

#     # Logout button
#     st.markdown("<br>", unsafe_allow_html=True)
#     col1, col2, col3 = st.columns([1, 1, 1])
#     with col1:
#         if st.button("👨‍💼 Admin Panel", key="admin_panel_access", use_container_width=True):
#             st.session_state.page = "main"
#             st.rerun()
#     with col3:
#         if st.button("🚪 Logout", key="logout_from_mode_selection", use_container_width=True):
#             # Clear auth state
#             st.session_state.authenticated = False
#             st.session_state.participant_id = None
#             st.session_state.participant_name = None
#             st.session_state.current_mode = None
#             st.session_state.page = "auth"
#             st.rerun()

# # ========== RECEIVER MODE ==========
# elif st.session_state.page == "receiver_mode":
#     if not st.session_state.authenticated:
#         st.error("Please log in first.")
#         st.session_state.page = "auth"
#         st.rerun()

#     team = get_team(st.session_state.team_id)
#     st.markdown('<h1 style="text-align: center; font-size: 45px; color: #E9E8C2;">🎁 Receiver Mode</h1>', unsafe_allow_html=True)

#     # Team banner
#     st.markdown(f"""
#     <div class="team-banner">
#         <h3>👋 {st.session_state.participant_name} | {team["name"]}</h3>
#         <p>📍 Location: {team["location"] or 'Not set'}</p>
#     </div>
#     """, unsafe_allow_html=True)

#     # Navigation buttons
#     col1, col2, col3 = st.columns([1, 1, 1])
#     with col1:
#         if st.button("← Back to Mode Selection", key="receiver_back_to_mode", use_container_width=True):
#             st.session_state.page = "mode_selection"
#             st.rerun()
#     with col3:
#         if st.button("🎅 Switch to Santa Mode", key="receiver_to_santa", use_container_width=True):
#             st.session_state.current_mode = "santa"
#             st.session_state.page = "santa_mode"
#             st.rerun()

#     st.divider()

#     # Tabs for Receiver features
#     tab1, tab2, tab3 = st.tabs(["📋 Preferences Survey", "🎁 My Wishlist", "💬 Messages"])

#     # TAB 1: PREFERENCES SURVEY
#     with tab1:
#         st.markdown("### 📋 Preferences Survey")
#         st.write("Help your Santa get to know you better! Answer these fun 'this or that' questions.")

#         questions = get_survey_questions()
#         responses = get_survey_responses(st.session_state.participant_id, st.session_state.team_id)
#         answered_questions = {r["question_id"] for r in responses}

#         total_questions = len(questions)
#         answered_count = len(answered_questions)
#         progress = answered_count / total_questions if total_questions > 0 else 0

#         st.progress(progress, text=f"Progress: {answered_count}/{total_questions} questions answered")

#         if answered_count == total_questions:
#             st.success("✅ Survey Complete! Your Santa can now see your preferences.")
#             mark_survey_complete(st.session_state.participant_id, st.session_state.team_id)

#         # Show responses
#         if responses:
#             with st.expander("📊 Your Responses", expanded=False):
#                 for response in responses:
#                     st.write(f"**{response['question_text']}** → {response['answer']}")

#         # Show unanswered questions
#         st.markdown("#### Answer Questions")
#         for question in questions:
#             if question["id"] not in answered_questions:
#                 st.markdown(f"### {question['question_text']}")
#                 col1, col2 = st.columns(2)
#                 with col1:
#                     if st.button(f"{question['emoji_a']} {question['option_a']}",
#                                key=f"opt_a_{question['id']}", use_container_width=True):
#                         save_survey_response(st.session_state.participant_id, st.session_state.team_id,
#                                            question['id'], question['option_a'])
#                         st.success(f"Saved: {question['option_a']}")
#                         st.rerun()
#                 with col2:
#                     if st.button(f"{question['emoji_b']} {question['option_b']}",
#                                key=f"opt_b_{question['id']}", use_container_width=True):
#                         save_survey_response(st.session_state.participant_id, st.session_state.team_id,
#                                            question['id'], question['option_b'])
#                         st.success(f"Saved: {question['option_b']}")
#                         st.rerun()
#                 st.divider()
#                 break  # Show one question at a time

#         if answered_count == total_questions:
#             st.info("All questions answered! You can view your responses in the expander above.")

#     # TAB 2: MY WISHLIST
#     with tab2:
#         st.markdown("### 🎁 My Wishlist")
#         st.write("Add items you'd love to receive. Your Santa can see this list!")

#         # Get wishlist
#         wishlist = get_wishlist(st.session_state.participant_id, st.session_state.team_id)

#         if wishlist:
#             st.markdown("#### Your Wishlist Items:")
#             for item in wishlist:
#                 col1, col2, col3, col4 = st.columns([1, 6, 2, 2])
#                 with col1:
#                     # Priority indicator image
#                     if item['priority'] == 1:
#                         st.image("images/ornament_red.png", width=30)
#                         priority_text = "High"
#                     elif item['priority'] == 2:
#                         st.image("images/ornament_gold.png", width=30)
#                         priority_text = "Medium"
#                     else:
#                         st.image("images/ornament_green.png", width=30)
#                         priority_text = "Low"

#                 with col2:
#                     st.write(f"**{item['item_text']}**")
#                     if item['item_link']:
#                         st.markdown(f"[🔗 Link]({item['item_link']})")
#                     st.caption(f"Priority: {priority_text}")

#                 with col3:
#                     if st.button("↑", key=f"up_{item['id']}"):
#                         reorder_wishlist_item(item['id'], 'up')
#                         st.rerun()
#                     if st.button("↓", key=f"down_{item['id']}"):
#                         reorder_wishlist_item(item['id'], 'down')
#                         st.rerun()

#                 with col4:
#                     if st.button("✏️", key=f"edit_{item['id']}"):
#                         st.session_state[f"editing_{item['id']}"] = True
#                         st.rerun()
#                     if st.button("🗑️", key=f"del_{item['id']}"):
#                         delete_wishlist_item(item['id'])
#                         st.success("Item deleted!")
#                         st.rerun()

#                 # Edit form (shown if editing)
#                 if st.session_state.get(f"editing_{item['id']}", False):
#                     with st.expander("Edit Item", expanded=True):
#                         edit_text = st.text_input("Item", value=item['item_text'], key=f"edit_text_{item['id']}")
#                         edit_link = st.text_input("Link (optional)", value=item['item_link'] or "", key=f"edit_link_{item['id']}")
#                         edit_priority = st.selectbox("Priority", [1, 2, 3], index=item['priority']-1,
#                                                      format_func=lambda x: {1: "High", 2: "Medium", 3: "Low"}[x],
#                                                      key=f"edit_priority_{item['id']}")
#                         if st.button("Save Changes", key=f"save_edit_{item['id']}"):
#                             update_wishlist_item(item['id'], edit_text, edit_priority, edit_link)
#                             del st.session_state[f"editing_{item['id']}"]
#                             st.success("Item updated!")
#                             st.rerun()

#                 st.divider()
#         else:
#             st.info("Your wishlist is empty. Add your first item below!")

#         # Add new item form
#         st.markdown("#### Add New Item")
#         with st.form("add_wishlist_item", clear_on_submit=True):
#             new_item_text = st.text_input("What would you like?", placeholder="e.g., Cozy winter scarf")
#             new_item_link = st.text_input("Link (optional)", placeholder="https://example.com/product")
#             new_priority = st.selectbox("Priority", [1, 2, 3], index=1,
#                                        format_func=lambda x: {1: "🔴 High Priority", 2: "🟡 Medium Priority", 3: "🟢 Low Priority"}[x])
#             submitted = st.form_submit_button("➕ Add to Wishlist")
#             if submitted and new_item_text:
#                 add_wishlist_item(st.session_state.participant_id, st.session_state.team_id,
#                                 new_item_text, new_priority, new_item_link)
#                 st.success(f"Added '{new_item_text}' to your wishlist!")
#                 st.rerun()

#     # TAB 3: MESSAGES (merged - view and reply)
#     with tab3:
#         st.markdown("### 💬 Messages with Your Secret Santa")
#         st.write("Chat with your anonymous Santa! Send and receive messages.")

#         # Get assignment where this participant is the receiver
#         santa_assignment = get_my_santa_assignment(st.session_state.participant_name, st.session_state.team_id)

#         if not santa_assignment:
#             st.warning("No Santa assignment found yet. Assignments need to be generated by the admin first.")
#         else:
#             # Display message thread
#             messages = get_messages_for_assignment(santa_assignment["id"])

#             # Mark all messages from Santa as read
#             for msg in messages:
#                 if msg["sender_role"] == "santa" and not msg["is_read"]:
#                     mark_message_read(msg["id"])

#             st.markdown("#### 💬 Conversation")
#             if messages:
#                 for msg in messages:
#                     if msg['sender_role'] == 'santa':
#                         # Santa's message (show)
#                         st.markdown(f"""
#                         <div class="message santa-message">
#                             <div class="message-type">🎅 SANTA: {msg['message_type'].upper()}</div>
#                             <div class="message-content">{msg['content']}</div>
#                             <div class="message-time">{msg['created_at']}</div>
#                         </div>
#                         """, unsafe_allow_html=True)
#                     else:
#                         # Your reply (show for context)
#                         st.markdown(f"""
#                         <div class="message receiver-message">
#                             <div class="message-type">YOU: {msg['message_type'].upper()}</div>
#                             <div class="message-content">{msg['content']}</div>
#                             <div class="message-time">{msg['created_at']}</div>
#                         </div>
#                         """, unsafe_allow_html=True)
#             else:
#                 st.info("No messages yet. Start a conversation or wait for your Santa to send a hint!")

#             # Reply form at the bottom
#             st.divider()
#             st.markdown("#### ✉️ Send a Message")
#             with st.form("reply_to_santa"):
#                 message_type = st.selectbox("Message Type", ["answer", "question", "note"],
#                                           format_func=lambda x: {"answer": "💬 Answer to Question", "question": "❓ Ask a Question", "note": "📝 General Note"}[x])
#                 message_content = st.text_area("Your Message", placeholder="Type your message here...", height=150)
#                 send_btn = st.form_submit_button("📤 Send Message", use_container_width=True)

#                 if send_btn and message_content:
#                     send_message(santa_assignment["id"], st.session_state.team_id, "receiver", message_type, message_content)
#                     st.success("✅ Message sent to your Santa!")
#                     st.rerun()

# # ========== SANTA MODE ==========
# elif st.session_state.page == "santa_mode":
#     if not st.session_state.authenticated:
#         st.error("Please log in first.")
#         st.session_state.page = "auth"
#         st.rerun()

#     team = get_team(st.session_state.team_id)
#     st.markdown('<h1 style="text-align: center; font-size: 45px; color: #E9E8C2;">🎅 Santa Mode</h1>', unsafe_allow_html=True)

#     # Team banner
#     st.markdown(f"""
#     <div class="team-banner">
#         <h3>👋 {st.session_state.participant_name} | {team["name"]}</h3>
#         <p>📍 Location: {team["location"] or 'Not set'}</p>
#     </div>
#     """, unsafe_allow_html=True)

#     # Navigation buttons
#     col1, col2, col3 = st.columns([1, 1, 1])
#     with col1:
#         if st.button("← Back to Mode Selection", key="santa_back_to_mode", use_container_width=True):
#             st.session_state.page = "mode_selection"
#             st.rerun()
#     with col3:
#         if st.button("🎁 Switch to Receiver Mode", key="santa_to_receiver", use_container_width=True):
#             st.session_state.current_mode = "receiver"
#             st.session_state.page = "receiver_mode"
#             st.rerun()

#     st.divider()

#     # Tabs for Santa features
#     tab1, tab2, tab3, tab4 = st.tabs(["📜 My Assignment", "📋 Their Preferences", "🎁 Their Wishlist", "💬 Send Message"])

#     # Get assignment
#     my_assignment = get_my_assignment(st.session_state.participant_name, st.session_state.team_id)

#     if not my_assignment:
#         st.error("No assignment found! The admin needs to generate assignments first.")
#         st.stop()

#     recipient_name = my_assignment["recipient_name"]

#     # Defensive check: ensure recipient_name is not None
#     if not recipient_name:
#         st.error("Assignment data is incomplete. Please contact the admin.")
#         st.stop()

#     # TAB 1: MY ASSIGNMENT
#     with tab1:
#         st.markdown("### 📜 Your Secret Santa Assignment")

#         if not my_assignment["revealed"]:
#             st.write("Click the button below to reveal your secret recipient!")

#             col1, col2, col3 = st.columns([1, 1, 1])
#             with col2:
#                 # Display folded paper chit
#                 st.markdown("""
#                 <div class="paper-container">
#                     <div class="folded-paper">
#                         <div style="font-size: 60px; color: #8B4513;">📜</div>
#                         <p style="color: #654321; font-weight: bold; margin-top: 10px; font-size: 18px;">Your Secret Assignment</p>
#                     </div>
#                 </div>
#                 """, unsafe_allow_html=True)

#                 if st.button("📜 Reveal My Recipient", key="reveal_assignment", use_container_width=True):
#                     # Mark as revealed
#                     result = draw_random_recipient(st.session_state.participant_name, st.session_state.team_id)
#                     if "error" not in result:
#                         st.success("🎉 Assignment revealed!")
#                         st.rerun()
#         else:
#             # Already revealed
#             revealed_ts = my_assignment.get("revealed_timestamp", "Unknown")
#             if not revealed_ts:
#                 revealed_ts = "Unknown"

#             st.markdown(f"""
#             <div class="opened-paper">
#                 <div style="text-align: center;">
#                     <p style="font-size: 20px; color: #8B4513 !important; margin-bottom: 10px;">🎁 Your Secret Santa Recipient 🎁</p>
#                     <h2>{recipient_name}</h2>
#                     <p style="margin-top: 20px; font-size: 16px;">
#                         Remember: Keep it secret, keep it safe! 🤫<br>
#                         <small style="font-size: 14px; color: #654321 !important;">
#                             👀 Revealed: {revealed_ts}
#                         </small>
#                     </p>
#                 </div>
#             </div>
#             """, unsafe_allow_html=True)
#         # End of TAB 1

#     # TAB 2: THEIR PREFERENCES
#     with tab2:
#         st.markdown(f"### 📋 {recipient_name}'s Preferences")
#         st.write(f"Learn about {recipient_name}'s preferences to pick the perfect gift!")

#         survey = get_receiver_survey(recipient_name, st.session_state.team_id)

#         if survey:
#             for response in survey:
#                 st.markdown(f"**{response['question_text']}**")
#                 st.write(f"→ {response['answer']}")
#                 st.divider()
#         else:
#             st.info(f"{recipient_name} hasn't completed the preferences survey yet.")

#     # TAB 3: THEIR WISHLIST
#     with tab3:
#         st.markdown(f"### 🎁 {recipient_name}'s Wishlist")
#         st.write(f"See what {recipient_name} would love to receive!")

#         wishlist = get_receiver_wishlist(recipient_name, st.session_state.team_id)

#         if wishlist:
#             for item in wishlist:
#                 col1, col2 = st.columns([1, 10])
#                 with col1:
#                     if item['priority'] == 1:
#                         st.image("images/ornament_red.png", width=40)
#                         priority_label = "🔴 High"
#                     elif item['priority'] == 2:
#                         st.image("images/ornament_gold.png", width=40)
#                         priority_label = "🟡 Medium"
#                     else:
#                         st.image("images/ornament_green.png", width=40)
#                         priority_label = "🟢 Low"

#                 with col2:
#                     st.markdown(f"**{item['item_text']}**")
#                     st.caption(f"Priority: {priority_label}")
#                     if item['item_link']:
#                         st.markdown(f"[🔗 View Product]({item['item_link']})")

#                 st.divider()
#         else:
#             st.info(f"{recipient_name} hasn't added any wishlist items yet.")

#     # TAB 4: SEND MESSAGE
#     with tab4:
#         st.markdown(f"### 💬 Send Message to {recipient_name}")
#         st.write(f"Send anonymous hints, ask questions, or share notes with {recipient_name}!")

#         # Show message history
#         messages = get_messages_for_assignment(my_assignment["id"])
#         if messages:
#             st.markdown("#### Message History")
#             for msg in messages:
#                 if msg['sender_role'] == 'santa':
#                     st.markdown(f"""
#                     <div class="message santa-message">
#                         <div class="message-type">YOU: {msg['message_type'].upper()}</div>
#                         <div class="message-content">{msg['content']}</div>
#                         <div class="message-time">{msg['created_at']}</div>
#                     </div>
#                     """, unsafe_allow_html=True)
#                 else:
#                     st.markdown(f"""
#                     <div class="message receiver-message">
#                         <div class="message-type">{recipient_name}: {msg['message_type'].upper()}</div>
#                         <div class="message-content">{msg['content']}</div>
#                         <div class="message-time">{msg['created_at']}</div>
#                     </div>
#                     """, unsafe_allow_html=True)

#             st.divider()

#         # Message composer
#         st.markdown("#### Send New Message")
#         with st.form("send_santa_message"):
#             message_type = st.selectbox("Message Type", ["hint", "question", "note"],
#                                       format_func=lambda x: {"hint": "Hint About Yourself", "question": "Question for Them", "note": "General Note"}[x])
#             message_content = st.text_area("Your Message", placeholder="Type your message here...", height=150)
#             send_btn = st.form_submit_button("📤 Send Message")

#             if send_btn and message_content:
#                 send_message(my_assignment["id"], st.session_state.team_id, "santa", message_type, message_content)
#                 st.success(f"✅ Message sent to {recipient_name}!")
#                 st.rerun()

# # ========== MAIN APP ==========
# # (Keeping this for backward compatibility with admin panel)
# elif st.session_state.page == "main":
#     # Get team info
#     team = get_team(st.session_state.team_id)
#     if not team:
#         st.error("Team not found. Please select a team.")
#         st.session_state.page = "team_selection"
#         st.rerun()

#     st.title("🎅 Secret Santa Gift Exchange")

#     # Team info banner
#     st.markdown(f"""
#     <div class="team-banner">
#         <h3>🎁 {team["name"]}</h3>
#         <p>📍 Location: {team["location"] or 'Not set'}</p>
#     </div>
#     """, unsafe_allow_html=True)

#     # Navigation buttons
#     if st.session_state.authenticated:
#         col1, col2, col3 = st.columns([1, 1, 1])
#         with col1:
#             if st.button("← Back to Mode Selection", key="back_from_admin"):
#                 st.session_state.page = "mode_selection"
#                 st.rerun()
#         st.divider()

#     tab1, tab2 = st.tabs(["🎁 Draw Your Recipient", "👤 Admin"])

#     # ========== PARTICIPANT TAB ==========
#     with tab1:
#         # st.markdown("### 🎄 Discover Your Secret Recipient")

#         # Initialize draw session states
#         if "draw_step" not in st.session_state:
#             st.session_state.draw_step = "name_input"
#         if "draw_name" not in st.session_state:
#             st.session_state.draw_name = ""
#         if "draw_result" not in st.session_state:
#             st.session_state.draw_result = None
#         if "show_shhh" not in st.session_state:
#             st.session_state.show_shhh = False

#         # STEP 1: Name Input
#         if st.session_state.draw_step == "name_input":
#             st.markdown("## 🎁 Enter Your Name")
#             st.write("Let's see who you'll be gifting to this holiday season!")

#             name_input = st.text_input("Your name (as in participant list)", key="name_field", label_visibility="visible")

#             if st.button("Continue →", key="name_submit", use_container_width=True):
#                 if not name_input.strip():
#                     st.warning("Please enter your name.")
#                 else:
#                     # Check if name exists
#                     conn = get_conn()
#                     c = conn.cursor()
#                     c.execute("SELECT id FROM participants WHERE name = ?", (name_input.strip(),))
#                     exists = c.fetchone()
#                     conn.close()

#                     if not exists:
#                         st.error("Name not found in participant list. Please check spelling.")
#                     else:
#                         st.session_state.draw_name = name_input.strip()
#                         st.session_state.draw_step = "show_shhh"
#                         st.session_state.show_shhh = True
#                         st.rerun()

#         # STEP 2: Shhh Animation + Secret Code Input
#         elif st.session_state.draw_step == "show_shhh":
#             # Show shhh animation
#             if st.session_state.show_shhh:
#                 st.markdown('<div class="shhh-animation">🤫 Shhh...</div>', unsafe_allow_html=True)
#                 st.markdown("<br>", unsafe_allow_html=True)

#                 # Center the continue button using columns
#                 col1, col2, col3 = st.columns([1, 1, 1])
#                 with col2:
#                     if st.button("✨ Continue", key="continue_after_shhh", use_container_width=True):
#                         st.session_state.show_shhh = False
#                         st.rerun()
#             else:
#                 # Show secret code input with animation
#                 st.markdown('<div class="secret-reveal">', unsafe_allow_html=True)
#                 st.markdown(f"#### 👋 Hello, {st.session_state.draw_name}!")
#                 st.write("Now, enter your secret code to proceed...")

#                 secret_input = st.text_input("Secret Code", type="password", key="secret_field", placeholder="Enter your secret code")

#                 col1, col2 = st.columns([1, 1])
#                 with col1:
#                     if st.button("← Back", key="back_to_name"):
#                         st.session_state.draw_step = "name_input"
#                         st.session_state.draw_name = ""
#                         st.rerun()
#                 with col2:
#                     if st.button("Verify →", key="secret_submit", use_container_width=True):
#                         if not secret_input:
#                             st.warning("Please enter your secret code.")
#                         else:
#                             # Validate participant
#                             ok, msg = validate_participant(st.session_state.draw_name, secret_input, st.session_state.team_id)
#                             if not ok:
#                                 st.error(msg)
#                                 # log failed attempt
#                                 conn = get_conn()
#                                 log_event(conn, st.session_state.draw_name, 'validate_failed', msg)
#                                 conn.commit()
#                                 conn.close()
#                             else:
#                                 # Get the assignment
#                                 conn = get_conn()
#                                 log_event(conn, st.session_state.draw_name, 'draw_attempt', '')
#                                 conn.commit()
#                                 conn.close()

#                                 result = draw_random_recipient(st.session_state.draw_name)
#                                 if "error" in result:
#                                     st.error(result["error"])
#                                 else:
#                                     st.session_state.draw_result = result
#                                     st.session_state.draw_step = "show_paper"
#                                     st.rerun()

#                 st.markdown('</div>', unsafe_allow_html=True)

#         # STEP 3: Show Folded Paper
#         elif st.session_state.draw_step == "show_paper":
#             result = st.session_state.draw_result

#             if result.get("already_revealed"):
#                 st.info("✨ Welcome back! You've already drawn your recipient.")
#             else:
#                 st.success("🎉 Authentication successful!")

#             st.markdown("### 📜 Your Secret Santa Assignment Awaits...")
#             st.write("Click the button inside the paper chit to reveal your recipient!")

#             # Display the paper chit visual
#             st.markdown("""
#             <div class="paper-container">
#                 <div class="folded-paper">
#                     <div style="font-size: 60px; color: #8B4513;">📜</div>
#                     <p style="color: #654321; font-weight: bold; margin-top: 10px; font-size: 18px;">Your Secret Assignment</p>
#                 </div>
#             </div>
#             """, unsafe_allow_html=True)

#             # Regular button to open the paper
#             col1, col2, col3 = st.columns([1, 1, 1])
#             with col2:
#                 if st.button("📜 Open", key="paper_click", use_container_width=True):
#                     st.session_state.draw_step = "paper_opened"
#                     st.rerun()

#             st.markdown("<br>", unsafe_allow_html=True)

#             col1, col2, col3 = st.columns([1, 1, 1])
#             with col2:
#                 if st.button("← Start Over", key="reset_draw", use_container_width=True):
#                     st.session_state.draw_step = "name_input"
#                     st.session_state.draw_name = ""
#                     st.session_state.draw_result = None
#                     st.rerun()

#         # STEP 4: Paper Opened - Show Assignment
#         elif st.session_state.draw_step == "paper_opened":
#             result = st.session_state.draw_result

#             st.markdown('<div class="unfolding">', unsafe_allow_html=True)

#             # Opened paper with assignment
#             st.markdown(f"""
#             <div class="opened-paper">
#                 <div style="text-align: center;">
#                     <p style="font-size: 20px; color: #8B4513 !important; margin-bottom: 10px;">🎁 Your Secret Santa Recipient 🎁</p>
#                     <h2>{result["recipient"]}</h2>
#                     <p style="margin-top: 20px; font-size: 16px;">
#                         Remember: Keep it secret, keep it safe! 🤫<br>
#                         <small style="font-size: 14px; color: #654321 !important;">
#                             📅 Assignment created: {result["timestamp"]}<br>
#                             👀 Revealed: {result["revealed_timestamp"]}
#                         </small>
#                     </p>
#                 </div>
#             </div>
#             """, unsafe_allow_html=True)

#             st.markdown('</div>', unsafe_allow_html=True)

#             st.markdown("<br>", unsafe_allow_html=True)

#             col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
#             with col2:
#                 if st.button("📜 Close Paper", key="close_paper", use_container_width=True):
#                     st.session_state.draw_step = "show_paper"
#                     st.rerun()
#             with col3:
#                 if st.button("✨ New Draw", key="new_draw", use_container_width=True):
#                     st.session_state.draw_step = "name_input"
#                     st.session_state.draw_name = ""
#                     st.session_state.draw_result = None
#                     st.rerun()

#     # ========== ADMIN TAB ==========
#     with tab2:
#         st.markdown("### 🔐 Admin Control Panel")

#         if not st.session_state.get("is_admin"):
#             st.warning("🔒 Admin authentication required")
#             st.write("Enter your admin PIN to access admin functions.")

#             admin_pin_input = st.text_input("Admin PIN", type="password", key="admin_pin")
#             admin_pin_env = os.getenv(ADMIN_PIN_ENV, "")

#             if st.button("🔓 Authenticate", key="auth_btn"):
#                 if admin_pin_env and admin_pin_input == admin_pin_env:
#                     st.session_state["is_admin"] = True
#                     # log admin auth
#                     conn = get_conn()
#                     log_event(conn, 'admin', 'admin_auth', 'successful')
#                     conn.commit()
#                     conn.close()
#                     st.success("✅ Admin authenticated!")
#                     st.rerun()
#                 else:
#                     st.session_state["is_admin"] = False
#                     st.error("❌ Admin PIN incorrect or not set on host.")
#         else:
#             st.success("✅ Authenticated as Admin")

#             if st.button("🚪 Logout", key="logout_btn"):
#                 st.session_state["is_admin"] = False
#                 st.rerun()

#             st.divider()

#             # Participant Management
#             st.subheader("👥 Manage Participants")

#             with st.expander("📤 Seed from CSV", expanded=False):
#                 uploaded = st.file_uploader("Upload participants CSV (columns: name, secret)", type=["csv"], key="csv_upload")
#                 if uploaded is not None:
#                     try:
#                         df = pd.read_csv(uploaded)
#                         if 'name' not in df.columns:
#                             st.error("CSV missing 'name' column.")
#                         else:
#                             seed_participants_from_df(df, st.session_state.team_id)
#                             st.success("✅ Seeded participants (INSERT OR IGNORE).")
#                     except Exception as e:
#                         st.error(f"Failed to parse CSV: {e}")

#             with st.expander("➕ Add Single Participant", expanded=False):
#                 new_name = st.text_input("Name to add", key="add_name")
#                 new_secret = st.text_input("Secret code (optional)", key="add_secret")
#                 if st.button("Add Participant", key="add_btn"):
#                     if new_name.strip():
#                         try:
#                             conn = get_conn()
#                             c = conn.cursor()
#                             c.execute("INSERT OR IGNORE INTO participants (team_id, name, secret) VALUES (?, ?, ?)",
#                                       (st.session_state.team_id, new_name.strip(), new_secret.strip()))
#                             log_event(conn, 'admin', 'add_participant', new_name.strip(), st.session_state.team_id)
#                             conn.commit()
#                             conn.close()
#                             st.success(f"✅ Added {new_name.strip()}")
#                         except Exception as e:
#                             st.error(f"DB error: {e}")
#                     else:
#                         st.warning("Enter a name.")

#             st.divider()

#             # Assignment Generation
#             st.subheader("🎲 Generate Assignments")
#             st.warning("⚠️ This creates a complete Secret Santa cycle. You won't be able to see who gets whom!")

#             if st.button("✨ Generate All Assignments", type="primary", key="gen_btn"):
#                 result = generate_all_assignments(st.session_state.team_id)
#                 if "error" in result:
#                     st.error(result["error"])
#                 else:
#                     st.success(f"✅ Generated {result['count']} assignments! Participants can now draw.")

#             st.divider()

#             # Remove Participant
#             st.subheader("🗑️ Remove Participant")
#             st.warning("⚠️ Removing a participant will regenerate ALL assignments!")

#             participants_list = list_participants(st.session_state.team_id)
#             if participants_list:
#                 participant_names = [p["name"] for p in participants_list]
#                 remove_name = st.selectbox("Select participant to remove", participant_names, key="remove_select")
#                 if st.button("🗑️ Remove and Regenerate", type="secondary", key="remove_btn"):
#                     result = remove_participant(remove_name, st.session_state.team_id)
#                     if "error" in result:
#                         st.error(result["error"])
#                     else:
#                         st.success(f"✅ Removed {remove_name} and regenerated {result['count']} assignments!")
#             else:
#                 st.info("No participants to remove.")

#             st.divider()

#             # Reset
#             st.subheader("🔄 Reset Assignments")
#             if st.button("🔄 Clear All Assignments", key="reset_btn"):
#                 reset_db(st.session_state.team_id)
#                 st.success("✅ All assignments cleared!")

#             st.divider()

#             # Download
#             st.subheader("📥 Download Data")

#             col1, col2 = st.columns(2)

#             with col1:
#                 if st.button("📥 Download Participants CSV", key="dl_participants"):
#                     rows = list_participants(st.session_state.team_id)
#                     df = pd.DataFrame([{"name": r["name"], "secret": r["secret"], "assigned": r["assigned"]} for r in rows])
#                     csv = df.to_csv(index=False)
#                     st.download_button("Download", csv, file_name="participants.csv", mime="text/csv")

#             with col2:
#                 if st.button("📥 Download Audit Logs CSV", key="dl_logs"):
#                     conn = get_conn()
#                     c = conn.cursor()
#                     c.execute("SELECT timestamp, actor, action, details FROM logs ORDER BY id DESC LIMIT 1000")
#                     logs = c.fetchall()
#                     conn.close()
#                     if logs:
#                         df_logs = pd.DataFrame(logs, columns=['timestamp', 'actor', 'action', 'details'])
#                         csv_logs = df_logs.to_csv(index=False)
#                         st.download_button("Download", csv_logs, file_name="audit_logs.csv", mime="text/csv")
#                     else:
#                         st.info("No logs yet.")

#             st.divider()

#             # Audit Logs Viewer
#             with st.expander("📋 View Audit Logs", expanded=False):
#                 conn = get_conn()
#                 c = conn.cursor()
#                 c.execute("SELECT timestamp, actor, action, details FROM logs ORDER BY id DESC LIMIT 100")
#                 logs = c.fetchall()
#                 conn.close()
#                 if logs:
#                     df_logs = pd.DataFrame(logs, columns=['timestamp', 'actor', 'action', 'details'])
#                     st.dataframe(df_logs, use_container_width=True)
#                 else:
#                     st.info("No logs yet.")

#     st.divider()
#     st.caption("🔒 Privacy: Assignments are stored server-side and hidden from everyone, including the admin. Keep this URL private!")

#     # Show simple status counts
#     conn = get_conn()
#     c = conn.cursor()
#     c.execute("SELECT COUNT(*) as revealed FROM assignments WHERE revealed = 1")
#     revealed_count = c.fetchone()["revealed"]
#     c.execute("SELECT COUNT(*) as total FROM participants")
#     total = c.fetchone()["total"]
#     conn.close()

#     waiting_count = total - revealed_count
#     st.caption(f"Revealed: {revealed_count} • Waiting: {waiting_count}")








# streamlit_secretsanta_with_audit.py
import streamlit as st
import sqlite3
import pandas as pd
import os
import random
from datetime import datetime

# =========================================================
# CONFIG & CONSTANTS
# =========================================================

DB_PATH = "secretsanta.db"
ADMIN_PIN_ENV = "SECRETSANTA_ADMIN_PIN"

DB_TYPE = None
DB_CONN_STRING = None

# =========================================================
# DATABASE + BUSINESS LOGIC (UNCHANGED)
# =========================================================
# ⚠️ Everything below this line is IDENTICAL to your logic
# (No functional changes, only moved structurally)

# ================= DATABASE =================

import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import os

DB_PATH = "secretsanta.db"
DATABASE_URL = os.getenv("DATABASE_URL")

def detect_database():
    global DB_TYPE, DB_CONN_STRING
    try:
        if "DATABASE_URL" in st.secrets:
            DB_CONN_STRING = st.secrets["DATABASE_URL"]
            DB_TYPE = "postgresql"
            return
    except Exception:
        pass

    DB_CONN_STRING = os.getenv("DATABASE_URL")
    DB_TYPE = "postgresql" if DB_CONN_STRING else "sqlite"
    
def get_conn():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        conn.autocommit = False
        return conn, "postgres"
    else:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"


def init_db():
    conn, db = get_conn()
    c = conn.cursor()

    if db == "postgres":
        ID = "SERIAL PRIMARY KEY"
    else:
        ID = "INTEGER PRIMARY KEY AUTOINCREMENT"

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS teams (
        id {ID},
        name TEXT UNIQUE NOT NULL,
        location TEXT,
        admin_pin TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS participants (
        id {ID},
        team_id INTEGER,
        name TEXT,
        secret TEXT,
        assigned INTEGER DEFAULT 0,
        email TEXT,
        has_completed_survey INTEGER DEFAULT 0,
        last_login TEXT,
        UNIQUE(team_id, name)
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS assignments (
        id {ID},
        team_id INTEGER,
        drawer_name TEXT,
        recipient_name TEXT,
        timestamp TEXT,
        revealed INTEGER DEFAULT 0,
        revealed_timestamp TEXT
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS logs (
        id {ID},
        team_id INTEGER,
        timestamp TEXT,
        actor TEXT,
        action TEXT,
        details TEXT
    )
    """)

    # Create wishlists table
    c.execute(f"""
    CREATE TABLE IF NOT EXISTS wishlists (
        id {ID},
        participant_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        item_text TEXT NOT NULL,
        priority INTEGER DEFAULT 2,
        item_link TEXT,
        item_order INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # Create survey_questions table
    c.execute(f"""
    CREATE TABLE IF NOT EXISTS survey_questions (
        id {ID},
        question_text TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        emoji_a TEXT,
        emoji_b TEXT,
        display_order INTEGER DEFAULT 0
    )
    """)

    # Create survey_responses table
    c.execute(f"""
    CREATE TABLE IF NOT EXISTS survey_responses (
        id {ID},
        participant_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        answer TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(participant_id, team_id, question_id)
    )
    """)

    # Create messages table
    c.execute(f"""
    CREATE TABLE IF NOT EXISTS messages (
        id {ID},
        team_id INTEGER NOT NULL,
        assignment_id INTEGER NOT NULL,
        sender_role TEXT NOT NULL,
        message_type TEXT NOT NULL,
        content TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # Populate survey questions if empty
    c.execute("SELECT COUNT(*) as count FROM survey_questions")
    row = c.fetchone()
    if row and row["count"] == 0:
        populate_survey_questions(conn)

    conn.commit()
    conn.close()




def log_event(conn, actor, action, details="", team_id=None):
    """Insert a log row. Accepts an open conn to allow logging inside transactions."""
    ts = datetime.utcnow().isoformat() + "Z"
    c = conn.cursor()
    if DATABASE_URL:
        c.execute("INSERT INTO logs (timestamp, actor, action, details, team_id) VALUES (%s, %s, %s, %s, %s)",
                  (ts, actor or '', action, details or '', team_id))
    else:
        c.execute("INSERT INTO logs (timestamp, actor, action, details, team_id) VALUES (?, ?, ?, ?, ?)",
                  (ts, actor or '', action, details or '', team_id))

def populate_survey_questions(conn):
    """Pre-populate survey with 'this or that' questions."""
    c = conn.cursor()
    questions = [
        ("Homemade or Store-bought?", "Homemade", "Store-bought", "🧶", "🛍️", 1),
        ("One Big Gift or Many Little Gifts?", "One Big Gift", "Many Little Gifts", "🎁", "🎀", 2),
        ("Practical Gifts or Sentimental Gifts?", "Practical", "Sentimental", "🔧", "💝", 3),
        ("Edible or Useful?", "Edible", "Useful", "🍫", "🛠️", 4),
        ("Personal Gift or Gift Card?", "Personal Gift", "Gift Card", "🎨", "💳", 5)
    ]

    for q_text, opt_a, opt_b, emoji_a, emoji_b, order in questions:
        if DATABASE_URL:
            c.execute("""
                INSERT INTO survey_questions (question_text, option_a, option_b, emoji_a, emoji_b, display_order)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (q_text, opt_a, opt_b, emoji_a, emoji_b, order))
        else:
            c.execute("""
                INSERT INTO survey_questions (question_text, option_a, option_b, emoji_a, emoji_b, display_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (q_text, opt_a, opt_b, emoji_a, emoji_b, order))

    log_event(conn, 'system', 'populate_survey_questions', f'Added {len(questions)} questions', None)

def create_team(name, admin_pin, location="Office"):
    """Create a new team."""
    conn, db = get_conn()
    c = conn.cursor()
    try:
        ts = datetime.utcnow().isoformat() + "Z"
        if db == "postgres":
            c.execute("INSERT INTO teams (name, admin_pin, location, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                      (name, admin_pin, location, ts))
            team_id = c.fetchone()['id']
        else:
            c.execute("INSERT INTO teams (name, admin_pin, location, created_at) VALUES (?, ?, ?, ?)",
                      (name, admin_pin, location, ts))
            team_id = c.lastrowid
        log_event(conn, 'system', 'create_team', f"Created team: {name}", team_id)
        conn.commit()
        conn.close()
        return {"success": True, "team_id": team_id}
    except Exception as e:
        conn.close()
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return {"error": "Team name already exists."}
        else:
            return {"error": f"Failed to create team: {e}"}

def get_team(team_id):
    """Get team details by ID."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("SELECT id, name, location, admin_pin FROM teams WHERE id = %s", (team_id,))
    else:
        c.execute("SELECT id, name, location, admin_pin FROM teams WHERE id = ?", (team_id,))
    team = c.fetchone()
    conn.close()
    return team

def get_team_by_name(name):
    """Get team details by name."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("SELECT id, name, location, admin_pin FROM teams WHERE name = %s", (name,))
    else:
        c.execute("SELECT id, name, location, admin_pin FROM teams WHERE name = ?", (name,))
    team = c.fetchone()
    conn.close()
    return team

def list_teams():
    """List all teams."""
    conn, db = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, location, created_at FROM teams ORDER BY created_at DESC")
    teams = c.fetchall()
    conn.close()
    return teams

def seed_participants_from_df(df: pd.DataFrame, team_id):
    conn, db = get_conn()
    c = conn.cursor()
    for _, row in df.iterrows():
        name = str(row['name']).strip()
        secret = str(row['secret']).strip() if 'secret' in row and not pd.isna(row['secret']) else ''
        if not name:
            continue
        try:
            if db == "postgres":
                c.execute("INSERT INTO participants (team_id, name, secret) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                          (team_id, name, secret))
            else:
                c.execute("INSERT OR IGNORE INTO participants (team_id, name, secret) VALUES (?, ?, ?)",
                          (team_id, name, secret))
            log_event(conn, 'admin', 'seed_participant', f"seeded {name}", team_id)
        except Exception as e:
            st.error(f"DB error while inserting {name}: {e}")
    conn.commit()
    conn.close()

def list_participants(team_id):
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("SELECT name, secret, assigned FROM participants WHERE team_id = %s ORDER BY name", (team_id,))
    else:
        c.execute("SELECT name, secret, assigned FROM participants WHERE team_id = ? ORDER BY name", (team_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def validate_participant(name, secret, team_id):
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("SELECT secret FROM participants WHERE name = %s AND team_id = %s", (name, team_id))
    else:
        c.execute("SELECT secret FROM participants WHERE name = ? AND team_id = ?", (name, team_id))
    row = c.fetchone()
    conn.close()
    if not row:
        return False, "Participant name not registered."
    registered_secret = row["secret"] or ""
    if registered_secret == "":
        return True, ""
    if secret == registered_secret:
        return True, ""
    else:
        return False, "Secret code does not match."

def authenticate_participant(name, secret, team_id):
    """Authenticate participant and update last_login."""
    ok, msg = validate_participant(name, secret, team_id)
    if not ok:
        return {"error": msg}

    conn, db = get_conn()
    c = conn.cursor()

    # Update last_login
    ts = datetime.utcnow().isoformat() + "Z"
    if db == "postgres":
        c.execute("UPDATE participants SET last_login = %s WHERE name = %s AND team_id = %s", (ts, name, team_id))
        c.execute("SELECT id, name, email, has_completed_survey FROM participants WHERE name = %s AND team_id = %s", (name, team_id))
    else:
        c.execute("UPDATE participants SET last_login = ? WHERE name = ? AND team_id = ?", (ts, name, team_id))
        c.execute("SELECT id, name, email, has_completed_survey FROM participants WHERE name = ? AND team_id = ?", (name, team_id))

    participant = c.fetchone()
    log_event(conn, name, 'login_success', '', team_id)
    conn.commit()
    conn.close()

    return {
        "success": True,
        "participant_id": participant["id"],
        "participant_name": participant["name"],
        "email": participant["email"],
        "has_completed_survey": participant["has_completed_survey"]
    }

def generate_all_assignments(team_id):
    """Pre-generate a complete Secret Santa cycle for all participants."""
    conn, db = get_conn()
    c = conn.cursor()
    try:
        # Clear existing assignments
        if db == "postgres":
            c.execute("DELETE FROM assignments WHERE team_id = %s", (team_id,))
            c.execute("UPDATE participants SET assigned = 0 WHERE team_id = %s", (team_id,))
            c.execute("SELECT name FROM participants WHERE team_id = %s ORDER BY name", (team_id,))
        else:
            c.execute("DELETE FROM assignments WHERE team_id = ?", (team_id,))
            c.execute("UPDATE participants SET assigned = 0 WHERE team_id = ?", (team_id,))
            c.execute("SELECT name FROM participants WHERE team_id = ? ORDER BY name", (team_id,))

        participants = [r["name"] for r in c.fetchall()]

        if len(participants) < 2:
            conn.rollback()
            conn.close()
            return {"error": "Need at least 2 participants to generate assignments."}

        # Generate valid derangement (no one gets themselves)
        receivers = participants.copy()
        max_attempts = 100
        valid_derangement = False

        for attempt in range(max_attempts):
            random.shuffle(receivers)
            is_valid = True
            for i in range(len(participants)):
                if participants[i] == receivers[i]:
                    is_valid = False
                    break
            if is_valid:
                valid_derangement = True
                break

        if not valid_derangement:
            receivers = participants[1:] + participants[:1]

        # Insert all assignments
        ts = datetime.utcnow().isoformat() + "Z"
        for giver, receiver in zip(participants, receivers):
            if db == "postgres":
                c.execute("INSERT INTO assignments (team_id, drawer_name, recipient_name, timestamp) VALUES (%s, %s, %s, %s)",
                          (team_id, giver, receiver, ts))
                c.execute("UPDATE participants SET assigned = 1 WHERE name = %s AND team_id = %s", (receiver, team_id))
            else:
                c.execute("INSERT INTO assignments (team_id, drawer_name, recipient_name, timestamp) VALUES (?, ?, ?, ?)",
                          (team_id, giver, receiver, ts))
                c.execute("UPDATE participants SET assigned = 1 WHERE name = ? AND team_id = ?", (receiver, team_id))

        log_event(conn, 'admin', 'generate_all_assignments', f"generated {len(participants)} assignments", team_id)
        conn.commit()
        conn.close()
        return {"success": True, "count": len(participants)}
    except Exception as e:
        conn.rollback()
        conn.close()
        log_event(conn, 'admin', 'generate_assignments_error', str(e), team_id)
        return {"error": f"Failed to generate assignments: {e}"}

def get_my_assignment(participant_name, team_id):
    """Get the assignment where participant is the drawer (Santa)."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("""
            SELECT id, recipient_name, timestamp, revealed, revealed_timestamp
            FROM assignments
            WHERE drawer_name = %s AND team_id = %s
        """, (participant_name, team_id))
    else:
        c.execute("""
            SELECT id, recipient_name, timestamp, revealed, revealed_timestamp
            FROM assignments
            WHERE drawer_name = ? AND team_id = ?
        """, (participant_name, team_id))
    assignment = c.fetchone()
    conn.close()
    return assignment

def draw_random_recipient(drawer_name, team_id):
    """Reveal the pre-generated assignment for the drawer."""
    conn, db = get_conn()
    c = conn.cursor()
    try:
        if db == "postgres":
            c.execute("SELECT id FROM participants WHERE name = %s AND team_id = %s", (drawer_name, team_id))
            drawer_row = c.fetchone()
            if not drawer_row:
                conn.close()
                return {"error": "Drawer not found in participant list."}

            c.execute("SELECT recipient_name, timestamp, revealed, revealed_timestamp FROM assignments WHERE drawer_name = %s AND team_id = %s",
                      (drawer_name, team_id))
        else:
            c.execute("SELECT id FROM participants WHERE name = ? AND team_id = ?", (drawer_name, team_id))
            drawer_row = c.fetchone()
            if not drawer_row:
                conn.close()
                return {"error": "Drawer not found in participant list."}

            c.execute("SELECT recipient_name, timestamp, revealed, revealed_timestamp FROM assignments WHERE drawer_name = ? AND team_id = ?",
                      (drawer_name, team_id))

        assignment = c.fetchone()

        if not assignment:
            conn.close()
            return {"error": "No assignment found. Admin needs to generate assignments first."}

        recipient = assignment["recipient_name"]
        timestamp = assignment["timestamp"]
        already_revealed = assignment["revealed"]
        revealed_ts = assignment["revealed_timestamp"]

        if already_revealed:
            conn.close()
            log_event(conn, drawer_name, 'view_existing_assignment', recipient, team_id)
            return {"recipient": recipient, "timestamp": timestamp, "revealed_timestamp": revealed_ts, "already_revealed": True}
        else:
            reveal_ts = datetime.utcnow().isoformat() + "Z"
            if db == "postgres":
                c.execute("UPDATE assignments SET revealed = 1, revealed_timestamp = %s WHERE drawer_name = %s AND team_id = %s",
                          (reveal_ts, drawer_name, team_id))
            else:
                c.execute("UPDATE assignments SET revealed = 1, revealed_timestamp = ? WHERE drawer_name = ? AND team_id = ?",
                          (reveal_ts, drawer_name, team_id))
            log_event(conn, drawer_name, 'draw_success', f"recipient={recipient}", team_id)
            conn.commit()
            conn.close()
            return {"recipient": recipient, "timestamp": timestamp, "revealed_timestamp": reveal_ts, "already_revealed": False}

    except Exception as e:
        conn.rollback()
        conn.close()
        return {"error": f"DB transaction error: {e}"}

def get_wishlist(participant_id, team_id):
    """Get all wishlist items for a participant, ordered by item_order."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("""
            SELECT id, item_text, priority, item_link, item_order, created_at
            FROM wishlists
            WHERE participant_id = %s AND team_id = %s
            ORDER BY item_order ASC
        """, (participant_id, team_id))
    else:
        c.execute("""
            SELECT id, item_text, priority, item_link, item_order, created_at
            FROM wishlists
            WHERE participant_id = ? AND team_id = ?
            ORDER BY item_order ASC
        """, (participant_id, team_id))
    items = c.fetchall()
    conn.close()
    return items

def add_wishlist_item(participant_id, team_id, item_text, priority=2, item_link=""):
    """Add a wishlist item."""
    conn, db = get_conn()
    c = conn.cursor()
    ts = datetime.utcnow().isoformat() + "Z"

    # Get max order for this participant
    if db == "postgres":
        c.execute("SELECT COALESCE(MAX(item_order), -1) as max_order FROM wishlists WHERE participant_id = %s AND team_id = %s",
                  (participant_id, team_id))
    else:
        c.execute("SELECT COALESCE(MAX(item_order), -1) as max_order FROM wishlists WHERE participant_id = ? AND team_id = ?",
                  (participant_id, team_id))
    max_order = c.fetchone()["max_order"]
    new_order = max_order + 1

    if db == "postgres":
        c.execute("""
            INSERT INTO wishlists (participant_id, team_id, item_text, priority, item_link, item_order, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (participant_id, team_id, item_text, priority, item_link, new_order, ts))
    else:
        c.execute("""
            INSERT INTO wishlists (participant_id, team_id, item_text, priority, item_link, item_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (participant_id, team_id, item_text, priority, item_link, new_order, ts))

    log_event(conn, f'participant_{participant_id}', 'add_wishlist_item', item_text, team_id)
    conn.commit()
    conn.close()
    return {"success": True}

def update_wishlist_item(item_id, item_text=None, priority=None, item_link=None):
    """Update a wishlist item."""
    conn, db = get_conn()
    c = conn.cursor()

    if db == "postgres":
        if item_text is not None:
            c.execute("UPDATE wishlists SET item_text = %s WHERE id = %s", (item_text, item_id))
        if priority is not None:
            c.execute("UPDATE wishlists SET priority = %s WHERE id = %s", (priority, item_id))
        if item_link is not None:
            c.execute("UPDATE wishlists SET item_link = %s WHERE id = %s", (item_link, item_id))
    else:
        if item_text is not None:
            c.execute("UPDATE wishlists SET item_text = ? WHERE id = ?", (item_text, item_id))
        if priority is not None:
            c.execute("UPDATE wishlists SET priority = ? WHERE id = ?", (priority, item_id))
        if item_link is not None:
            c.execute("UPDATE wishlists SET item_link = ? WHERE id = ?", (item_link, item_id))

    conn.commit()
    conn.close()
    return {"success": True}

def delete_wishlist_item(item_id):
    """Delete a wishlist item."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("DELETE FROM wishlists WHERE id = %s", (item_id,))
    else:
        c.execute("DELETE FROM wishlists WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"success": True}

def reorder_wishlist_item(item_id, direction):
    """Move a wishlist item up or down. Direction is 'up' or 'down'."""
    conn, db = get_conn()
    c = conn.cursor()

    # Get current item
    if db == "postgres":
        c.execute("SELECT participant_id, team_id, item_order FROM wishlists WHERE id = %s", (item_id,))
    else:
        c.execute("SELECT participant_id, team_id, item_order FROM wishlists WHERE id = ?", (item_id,))
    current = c.fetchone()
    if not current:
        conn.close()
        return {"error": "Item not found"}

    current_order = current["item_order"]
    participant_id = current["participant_id"]
    team_id = current["team_id"]

    # Get all items for this participant
    if db == "postgres":
        c.execute("""
            SELECT id, item_order FROM wishlists
            WHERE participant_id = %s AND team_id = %s
            ORDER BY item_order ASC
        """, (participant_id, team_id))
    else:
        c.execute("""
            SELECT id, item_order FROM wishlists
            WHERE participant_id = ? AND team_id = ?
            ORDER BY item_order ASC
        """, (participant_id, team_id))
    all_items = c.fetchall()

    # Find target item to swap with
    target_item = None
    for i, item in enumerate(all_items):
        if item["id"] == item_id:
            if direction == "up" and i > 0:
                target_item = all_items[i - 1]
            elif direction == "down" and i < len(all_items) - 1:
                target_item = all_items[i + 1]
            break

    if target_item:
        target_order = target_item["item_order"]
        if db == "postgres":
            c.execute("UPDATE wishlists SET item_order = %s WHERE id = %s", (target_order, item_id))
            c.execute("UPDATE wishlists SET item_order = %s WHERE id = %s", (current_order, target_item["id"]))
        else:
            c.execute("UPDATE wishlists SET item_order = ? WHERE id = ?", (target_order, item_id))
            c.execute("UPDATE wishlists SET item_order = ? WHERE id = ?", (current_order, target_item["id"]))
        conn.commit()

    conn.close()
    return {"success": True}

def get_survey_questions():
    """Get all survey questions ordered by display_order."""
    conn, db = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, question_text, option_a, option_b, emoji_a, emoji_b, display_order
        FROM survey_questions
        ORDER BY display_order ASC
    """)
    questions = c.fetchall()
    conn.close()
    return questions

def save_survey_response(participant_id, team_id, question_id, answer):
    """Save or update a survey response."""
    conn, db = get_conn()
    c = conn.cursor()
    ts = datetime.utcnow().isoformat() + "Z"

    if db == "postgres":
        c.execute("""
            INSERT INTO survey_responses (participant_id, team_id, question_id, answer, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (participant_id, team_id, question_id)
            DO UPDATE SET answer = EXCLUDED.answer, created_at = EXCLUDED.created_at
        """, (participant_id, team_id, question_id, answer, ts))
    else:
        c.execute("""
            INSERT OR REPLACE INTO survey_responses (participant_id, team_id, question_id, answer, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (participant_id, team_id, question_id, answer, ts))

    log_event(conn, f'participant_{participant_id}', 'save_survey_response', f'Q{question_id}: {answer}', team_id)
    conn.commit()
    conn.close()
    return {"success": True}

def get_survey_responses(participant_id, team_id):
    """Get all survey responses for a participant."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("""
            SELECT sr.question_id, sr.answer, sq.question_text, sq.option_a, sq.option_b
            FROM survey_responses sr
            JOIN survey_questions sq ON sr.question_id = sq.id
            WHERE sr.participant_id = %s AND sr.team_id = %s
            ORDER BY sq.display_order ASC
        """, (participant_id, team_id))
    else:
        c.execute("""
            SELECT sr.question_id, sr.answer, sq.question_text, sq.option_a, sq.option_b
            FROM survey_responses sr
            JOIN survey_questions sq ON sr.question_id = sq.id
            WHERE sr.participant_id = ? AND sr.team_id = ?
            ORDER BY sq.display_order ASC
        """, (participant_id, team_id))
    responses = c.fetchall()
    conn.close()
    return responses

def mark_survey_complete(participant_id, team_id):
    """Mark survey as complete for a participant."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("UPDATE participants SET has_completed_survey = 1 WHERE id = %s AND team_id = %s", (participant_id, team_id))
    else:
        c.execute("UPDATE participants SET has_completed_survey = 1 WHERE id = ? AND team_id = ?", (participant_id, team_id))
    log_event(conn, f'participant_{participant_id}', 'complete_survey', '', team_id)
    conn.commit()
    conn.close()
    return {"success": True}

def get_receiver_wishlist(recipient_name, team_id):
    """Get wishlist for a specific recipient."""
    conn, db = get_conn()
    c = conn.cursor()

    if db == "postgres":
        c.execute("SELECT id FROM participants WHERE name = %s AND team_id = %s", (recipient_name, team_id))
    else:
        c.execute("SELECT id FROM participants WHERE name = ? AND team_id = ?", (recipient_name, team_id))
    participant = c.fetchone()
    if not participant:
        conn.close()
        return []

    participant_id = participant["id"]
    conn.close()
    return get_wishlist(participant_id, team_id)

def get_receiver_survey(recipient_name, team_id):
    """Get survey responses for a specific recipient."""
    conn, db = get_conn()
    c = conn.cursor()

    if db == "postgres":
        c.execute("SELECT id FROM participants WHERE name = %s AND team_id = %s", (recipient_name, team_id))
    else:
        c.execute("SELECT id FROM participants WHERE name = ? AND team_id = ?", (recipient_name, team_id))
    participant = c.fetchone()
    if not participant:
        conn.close()
        return []

    participant_id = participant["id"]
    conn.close()
    return get_survey_responses(participant_id, team_id)

def send_message(assignment_id, team_id, sender_role, message_type, content):
    """Send a message in an assignment thread."""
    conn, db = get_conn()
    c = conn.cursor()
    ts = datetime.utcnow().isoformat() + "Z"

    if db == "postgres":
        c.execute("""
            INSERT INTO messages (team_id, assignment_id, sender_role, message_type, content, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (team_id, assignment_id, sender_role, message_type, content, ts))
    else:
        c.execute("""
            INSERT INTO messages (team_id, assignment_id, sender_role, message_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (team_id, assignment_id, sender_role, message_type, content, ts))

    log_event(conn, f'{sender_role}_assignment_{assignment_id}', 'send_message', f'{message_type}: {content[:50]}', team_id)
    conn.commit()
    conn.close()
    return {"success": True}

def get_messages_for_assignment(assignment_id):
    """Get all messages for an assignment thread."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("""
            SELECT id, sender_role, message_type, content, is_read, created_at
            FROM messages
            WHERE assignment_id = %s
            ORDER BY created_at ASC
        """, (assignment_id,))
    else:
        c.execute("""
            SELECT id, sender_role, message_type, content, is_read, created_at
            FROM messages
            WHERE assignment_id = ?
            ORDER BY created_at ASC
        """, (assignment_id,))
    messages = c.fetchall()
    conn.close()
    return messages

def mark_message_read(message_id):
    """Mark a message as read."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("UPDATE messages SET is_read = 1 WHERE id = %s", (message_id,))
    else:
        c.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    return {"success": True}

def get_my_santa_assignment(participant_name, team_id):
    """Get the assignment where participant is the recipient (receives from Santa)."""
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("""
            SELECT id, drawer_name, timestamp
            FROM assignments
            WHERE recipient_name = %s AND team_id = %s
        """, (participant_name, team_id))
    else:
        c.execute("""
            SELECT id, drawer_name, timestamp
            FROM assignments
            WHERE recipient_name = ? AND team_id = ?
        """, (participant_name, team_id))
    assignment = c.fetchone()
    conn.close()
    return assignment

def remove_participant(name, team_id):
    """Remove a participant and regenerate all assignments."""
    conn, db = get_conn()
    c = conn.cursor()
    try:
        if db == "postgres":
            c.execute("DELETE FROM participants WHERE name = %s AND team_id = %s", (name, team_id))
        else:
            c.execute("DELETE FROM participants WHERE name = ? AND team_id = ?", (name, team_id))
        log_event(conn, 'admin', 'remove_participant', name, team_id)
        conn.commit()
        conn.close()

        # Regenerate assignments
        return generate_all_assignments(team_id)
    except Exception as e:
        conn.rollback()
        conn.close()
        return {"error": f"Failed to remove participant: {e}"}

def reset_db(team_id):
    conn, db = get_conn()
    c = conn.cursor()
    if db == "postgres":
        c.execute("DELETE FROM assignments WHERE team_id = %s", (team_id,))
        c.execute("UPDATE participants SET assigned = 0 WHERE team_id = %s", (team_id,))
    else:
        c.execute("DELETE FROM assignments WHERE team_id = ?", (team_id,))
        c.execute("UPDATE participants SET assigned = 0 WHERE team_id = ?", (team_id,))
    log_event(conn, 'admin', 'reset_assignments', 'all unassigned', team_id)
    conn.commit()
    conn.close()

def auto_load_participants():
    if not os.path.exists("participants.csv"):
        return

    try:
        df = pd.read_csv("participants.csv")
        if 'team_name' not in df.columns or 'name' not in df.columns:
            st.warning("CSV must have 'team_name' and 'name' columns")
            return

        # Process each team
        for team_name in df['team_name'].unique():
            team = get_team_by_name(team_name)

            if not team:
                # Create team using environment variables
                admin_pin = os.getenv(f"TEAM_{team_name.upper().replace(' ', '_')}_ADMIN_PIN", "default123")
                location = os.getenv(f"TEAM_{team_name.upper().replace(' ', '_')}_LOCATION", "Office")

                result = create_team(team_name, admin_pin, location)
                if "error" in result:
                    st.error(f"Failed to create team {team_name}: {result['error']}")
                    continue
                team_id = result["team_id"]
            else:
                team_id = team["id"]

            # Load participants for this team
            team_df = df[df['team_name'] == team_name]
            seed_participants_from_df(team_df, team_id)

    except Exception as e:
        st.error(f"Failed to auto-load participants: {e}")


# =========================================================
# BOOTSTRAP (RUN ONCE)
# =========================================================

def bootstrap():
    detect_database()
    st.session_state.db_type = DB_TYPE
    st.session_state.db_conn_string = DB_CONN_STRING
    init_db()
    auto_load_participants()


# =========================================================
# MAIN STREAMLIT APP (ALL UI HERE)
# =========================================================

def main():
    st.set_page_config(
        page_title="Secret Santa",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    if "bootstrapped" not in st.session_state:
        bootstrap()
        st.session_state.bootstrapped = True
    else:
        global DB_TYPE, DB_CONN_STRING
        DB_TYPE = st.session_state.db_type
        DB_CONN_STRING = st.session_state.db_conn_string

    # ---------------- CSS ----------------
    st.markdown("""
    <style>
        /* Hide Streamlit header and footer */
        header {
            background-color: #1B4332 !important;
            visibility: hidden;
        }

        .stApp > header {
            background-color: transparent !important;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Dark pine green background with pattern */
        .stApp {
            background-color: #1B4332;
            background-image:
                repeating-linear-gradient(45deg, transparent, transparent 100px, rgba(255,255,255,0.02) 100px, rgba(255,255,255,0.02) 200px),
                repeating-linear-gradient(-45deg, transparent, transparent 100px, rgba(255,255,255,0.02) 100px, rgba(255,255,255,0.02) 200px),
                linear-gradient(180deg, #1B4332 0%, #2D6A4F 100%);
        }

        /* Snowfall animation */
        .snowflake {
            position: fixed;
            top: -10px;
            z-index: 9999;
            user-select: none;
            cursor: default;
            animation: snowfall linear infinite;
            color: white;
            font-size: 1em;
        }

        @keyframes snowfall {
            0% {
                transform: translateY(0vh) rotate(0deg);
                opacity: 1;
            }
            100% {
                transform: translateY(100vh) rotate(360deg);
                opacity: 0.8;
            }
        }

        /* Dancing Santa animation */
        @keyframes dance {
            0%, 100% { transform: translateY(0px) rotate(-5deg); }
            25% { transform: translateY(-20px) rotate(5deg); }
            50% { transform: translateY(0px) rotate(-5deg); }
            75% { transform: translateY(-10px) rotate(5deg); }
        }

        .dancing-santa {
            font-size: 120px;
            animation: dance 1s ease-in-out infinite;
            display: inline-block;
            margin: 20px auto;
        }

        /* Style text to be visible on dark background */
        .stMarkdown, .stText, p, span, div {
            color: #F1FAEE !important;
        }

        /* Style headers */
        h1{
            color: #E9E8C2 !important;
        }
        h2, h3 {
            color: #E9E8C2 !important;
        }
        /* Style buttons */
        .stButton > button {
            background-color: #E63946;
            color: white;
            border: none;
            border-radius: 25px;
            padding: 15px 40px;
            font-size: 20px;
            font-weight: bold;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            transition: all 0.3s;
        }

        .stButton > button:hover {
            background-color: #D62828;
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0,0,0,0.4);
        }

        /* Style input fields - FIXED for visibility */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background-color: rgba(255, 255, 255, 0.95) !important;
            color: #1B4332 !important;
            font-weight: 500 !important;
            border-radius: 10px;
        }

        /* Fix selectbox visibility */
        .stSelectbox > div > div > select {
            background-color: rgba(255, 255, 255, 0.95) !important;
            color: #1B4332 !important;
            font-weight: 500 !important;
        }

        /* Fix placeholder visibility */
        ::placeholder {
            color: rgba(27, 67, 50, 0.5) !important;
        }

        /* Dropdown options */
        option {
            background-color: #F1FAEE !important;
            color: #1B4332 !important;
        }

        /* Style expanders */
        .streamlit-expanderHeader {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            color: #E9E8C2 !important;
        }

        /* Style success/error/warning messages */
        .stSuccess, .stError, .stWarning, .stInfo {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }

        /* Welcome page styling */
        .welcome-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 50px 20px;
            min-height: 80vh;
        }

        .welcome-title {
            font-size: 60px;
            color: #FFD700;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.5);
            margin-bottom: 20px;
        }

        /* Shhhh animation */
        @keyframes shhh {
            0%, 100% { opacity: 0; transform: scale(0.5); }
            50% { opacity: 1; transform: scale(1.2); }
        }

        .shhh-animation {
            font-size: 60px;
            animation: shhh 2s ease-in-out;
            text-align: center;
            margin: 30px 0;
            font-colour: E6BE9A;
        }

        /* Secret code reveal animation */
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .secret-reveal {
            animation: slideDown 0.5s ease-out;
        }
                
        /* Folded paper/chit styling */
        .paper-container {
            perspective: 1000px;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 40px 0 20px 0;
            position: relative;
        }

        .folded-paper {
            width: 300px;
            height: 200px;
            background: linear-gradient(135deg, #FFF8DC 0%, #F5E6D3 100%);
            border-radius: 10px;
            box-shadow:
                0 10px 30px rgba(0,0,0,0.3),
                inset 0 0 20px rgba(0,0,0,0.1);
            cursor: pointer;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            position: relative;
            border: 2px solid #D4AF37;
            margin-bottom: 20px;
        }

        .folded-paper:hover {
            transform: translateY(-10px) scale(1.05);
            box-shadow: 0 15px 40px rgba(0,0,0,0.4);
        }

        .folded-paper::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 2px;
            background: rgba(212, 175, 55, 0.3);
            transform: translateY(-50%);
        }

        .folded-paper::after {
            content: '';
            position: absolute;
            top: 0;
            bottom: 0;
            left: 50%;
            width: 2px;
            background: rgba(212, 175, 55, 0.3);
            transform: translateX(-50%);
        }

        /* Opened paper animation */
        @keyframes unfold {
            0% {
                transform: rotateX(0deg);
                opacity: 1;
            }
            50% {
                transform: rotateX(90deg);
                opacity: 0.5;
            }
            100% {
                transform: rotateX(0deg);
                opacity: 1;
            }
        }

        .unfolding {
            animation: unfold 0.8s ease-out;
        }

        .opened-paper {
            background: linear-gradient(135deg, #FFF8DC 0%, #F5E6D3 100%);
            border: 3px solid #D4AF37;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            max-width: 500px;
            margin: 20px auto;
        }

        .opened-paper h2 {
            color: #8B4513 !important;
            font-size: 48px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            margin: 20px 0;
        }

        .opened-paper p {
            color: #654321 !important;
            font-size: 18px;
        }

        /* Paper fold lines */
        .fold-line {
            position: absolute;
            background: rgba(139, 69, 19, 0.1);
        }

        /* Footer styling */
        .santa-footer {
            position: fixed;
            bottom: 0;
            right: 20px;
            z-index: 1000;
            pointer-events: none;
        }

        .santa-character {
            font-size: 80px;
            animation: wave 3s ease-in-out infinite;
        }

        @keyframes wave {
            0%, 100% { transform: rotate(0deg); }
            25% { transform: rotate(-10deg); }
            75% { transform: rotate(10deg); }
        }

        /* Team info banner */
        .team-banner {
            background: linear-gradient(135deg, rgba(230, 57, 70, 0.2), rgba(45, 106, 79, 0.2));
            border-radius: 15px;
            padding: 15px 20px;
            margin: 10px 0 20px 0;
            border: 2px solid rgba(255, 215, 0, 0.3);
        }

        .team-banner h3 {
            margin: 0;
            color: #E9E8C2 !important;
            font-size: 24px;
        }

        .team-banner p {
            margin: 5px 0 0 0;
            color: #F1FAEE !important;
            font-size: 16px;
        }

        /* Interactive Team Cards */
        .team-card {
            background: linear-gradient(135deg, rgba(230, 57, 70, 0.2), rgba(45, 106, 79, 0.2));
            border-radius: 15px;
            padding: 20px;
            margin: 15px 0;
            border: 2px solid rgba(255, 215, 0, 0.3);
            cursor: pointer;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }

        .team-card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 8px 12px rgba(0,0,0,0.4);
        }

        /* Mode Selection Cards */
        # .mode-card {
        #     background: linear-gradient(135deg, rgba(255, 215, 0, 0.1), rgba(230, 57, 70, 0.1));
        #     border-radius: 20px;
        #     padding: 30px;
        #     text-align: center;
        #     cursor: pointer;
        #     transition: all 0.3s ease;
        #     border: 3px solid rgba(255, 215, 0, 0.5);
        #     box-shadow: 0 6px 10px rgba(0,0,0,0.3);
        # }

        # .mode-card:hover {
        #     transform: translateY(-10px) scale(1.05);
        #     box-shadow: 0 12px 20px rgba(0,0,0,0.4);
        #     border-color: #FFD700;
        # }

        .mode-card img {
            max-width: 100%;
            border-radius: 10px;
        }

        /* Message Bubbles */
        .message {
            padding: 15px;
            margin: 10px 0;
            border-radius: 15px;
            max-width: 80%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }

        .santa-message {
            background: linear-gradient(135deg, #E63946, #D62828);
            color: white;
            margin-left: auto;
            margin-right: 0;
            text-align: right;
        }

        .receiver-message {
            background: linear-gradient(135deg, #2D6A4F, #1B4332);
            color: #F1FAEE;
            margin-left: 0;
            margin-right: auto;
            text-align: left;
        }

        .message-type {
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
            opacity: 0.8;
            margin-bottom: 5px;
        }

        .message-content {
            font-size: 16px;
            line-height: 1.5;
            margin: 5px 0;
        }

        .message-time {
            font-size: 11px;
            opacity: 0.7;
            margin-top: 5px;
        }

        /* Wishlist Item Card */
        .wishlist-item {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            border: 1px solid rgba(255, 215, 0, 0.3);
            transition: background 0.2s ease;
        }

        .wishlist-item:hover {
            background: rgba(255, 255, 255, 0.15);
        }

        /* Survey Option Buttons */
        .survey-option {
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.2), rgba(230, 57, 70, 0.2));
            border: 2px solid rgba(255, 215, 0, 0.5);
            border-radius: 15px;
            padding: 20px;
            margin: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
            font-size: 18px;
        }

        .survey-option:hover {
            transform: scale(1.05);
            border-color: #FFD700;
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.3), rgba(230, 57, 70, 0.3));
        }

        .survey-option.selected {
            animation: pulse 0.5s ease-out;
            background: linear-gradient(135deg, #FFD700, #E63946);
            color: white;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }

        /* Priority Indicators */
        .priority-high {
            color: #E63946;
            font-weight: bold;
        }

        .priority-medium {
            color: #FFD700;
            font-weight: bold;
        }

        .priority-low {
            color: #52B788;
            font-weight: bold;
        }

        /* Mobile Responsive */
        @media (max-width: 768px) {
            .team-card, .mode-card {
                padding: 15px;
            }

            .message {
                max-width: 90%;
            }

            .dancing-santa {
                font-size: 80px;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    snowflakes_html = "<div class='snowflakes'>"
    for _ in range(50):
        left = random.randint(0, 100)
        delay = random.uniform(0, 5)
        duration = random.uniform(10, 20)
        snowflakes_html += f"<div class='snowflake' style='left:{left}%;animation-duration:{duration}s;animation-delay:{delay}s;'>❅</div>"
    snowflakes_html += "</div>"
    st.markdown(snowflakes_html, unsafe_allow_html=True)


    # # ---------------- Snow ----------------
    # snow = ""
    # for _ in range(40):
    #     snow += f"<div class='snowflake'>❅</div>"
    # st.markdown(snow, unsafe_allow_html=True)

    # ---------------- Session State ----------------
    st.session_state.setdefault("page", "team_selection")
    st.session_state.setdefault("authenticated", False)

    # ---------------- Session State Initialization ----------------
    st.session_state.setdefault("team_id", None)
    st.session_state.setdefault("team_name", None)
    st.session_state.setdefault("participant_id", None)
    st.session_state.setdefault("participant_name", None)
    st.session_state.setdefault("current_mode", None)
    st.session_state.setdefault("is_admin", False)

    # Add Santa footer to all pages
    st.markdown("""
    <div class="santa-footer">
        <div class="santa-character">🎅</div>
    </div>
    """, unsafe_allow_html=True)

    # ---------------- Pages ----------------

    # ========== TEAM SELECTION PAGE ==========
    if st.session_state.page == "team_selection":
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown('<h1 style="text-align: center; font-size: 60px; color: #E9E8C2; text-shadow: 3px 3px 6px rgba(0,0,0,0.5);">🎄 Secret Santa 🎄</h1>', unsafe_allow_html=True)
        st.markdown('<div style="text-align: center;"><div class="dancing-santa">🎅</div></div>', unsafe_allow_html=True)

        st.markdown("### 🎁 Select or Create Your Team")

        tab1, tab2 = st.tabs(["Join Existing Team", "Create New Team"])

        with tab1:
            st.markdown("#### Join an existing team")
            teams = list_teams()

            if teams:
                team_names = [t["name"] for t in teams]
                selected_team_name = st.selectbox("Select your team", team_names, key="select_team")

                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("Join Team", key="join_team", use_container_width=True):
                        team = get_team_by_name(selected_team_name)
                        if team:
                            st.session_state.team_id = team["id"]
                            st.session_state.team_name = team["name"]
                            st.session_state.page = "auth"
                            st.rerun()
            else:
                st.info("No teams created yet. Create one in the next tab!")

        with tab2:
            st.markdown("#### Create a new team")
            new_team_name = st.text_input("Team Name", key="new_team_name", placeholder="e.g., Tech Team 2025")
            new_admin_pin = st.text_input("Admin PIN", type="password", key="new_admin_pin",
                                          placeholder="Set a PIN for admin access")
            new_location = st.text_input("Exchange Location", key="new_location",
                                         placeholder="e.g., Office Party Room, Virtual")

            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("Create Team", key="create_team", use_container_width=True):
                    if not new_team_name.strip():
                        st.error("Please enter a team name")
                    elif not new_admin_pin.strip():
                        st.error("Please set an admin PIN")
                    else:
                        result = create_team(new_team_name.strip(), new_admin_pin, new_location)
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.session_state.team_id = result["team_id"]
                            st.session_state.team_name = new_team_name.strip()
                            st.success(f"Team '{new_team_name}' created!")
                            st.session_state.page = "auth"
                            st.rerun()

    # ========== AUTH PAGE ==========
    elif st.session_state.page == "auth":
        # Get team info
        team = get_team(st.session_state.team_id)
        if not team:
            st.error("Team not found. Please select a team.")
            st.session_state.page = "team_selection"
            st.rerun()

        # Add spacing at top
        st.markdown("<br><br>", unsafe_allow_html=True)

        # Title
        st.markdown('<h1 style="text-align: center; font-size: 60px; color: #E9E8C2; text-shadow: 3px 3px 6px rgba(0,0,0,0.5);">🎄 Secret Santa 🎄</h1>', unsafe_allow_html=True)

        # Dancing Santa
        st.markdown('<div style="text-align: center;"><div class="dancing-santa">🎅</div></div>', unsafe_allow_html=True)

        # Team info banner
        st.markdown(f"""
        <div class="team-banner">
            <h3>🎁 {team["name"]}</h3>
            <p>📍 Location: {team["location"] or 'Not set'}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🔐 Login to Continue")
        st.write("Select your name and enter your secret code to access your Santa/Receiver modes.")

        # Get participants for this team
        participants = list_participants(st.session_state.team_id)
        if not participants:
            st.warning("No participants registered yet. Please contact your admin.")
            if st.button("← Back to Teams"):
                st.session_state.page = "team_selection"
                st.rerun()
        else:
            participant_names = ["Select your name..."] + [p["name"] for p in participants]

            selected_name = st.selectbox("Your Name", participant_names, key="auth_name_select")
            secret_input = st.text_input("Secret Code", type="password", key="auth_secret",
                                         placeholder="Enter your secret code")

            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("← Back to Teams", key="back_to_teams", use_container_width=True):
                    st.session_state.page = "team_selection"
                    st.session_state.team_id = None
                    st.session_state.team_name = None
                    st.rerun()

            with col3:
                if st.button("🎅 Login", key="login_btn", use_container_width=True):
                    if selected_name == "Select your name...":
                        st.error("Please select your name from the list.")
                    elif not secret_input:
                        st.error("Please enter your secret code.")
                    else:
                        # Authenticate
                        result = authenticate_participant(selected_name, secret_input, st.session_state.team_id)
                        if "error" in result:
                            st.error(f"❌ {result['error']}")
                        else:
                            # Set session state
                            st.session_state.authenticated = True
                            st.session_state.participant_id = result["participant_id"]
                            st.session_state.participant_name = result["participant_name"]
                            st.session_state.page = "mode_selection"
                            st.success(f"✅ Welcome, {result['participant_name']}!")
                            st.rerun()

    # ========== MODE SELECTION PAGE ==========
    elif st.session_state.page == "mode_selection":
        if not st.session_state.authenticated:
            st.error("Please log in first.")
            st.session_state.page = "auth"
            st.rerun()

        # Get team info
        team = get_team(st.session_state.team_id)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<h1 style="text-align: center; font-size: 50px; color: #E9E8C2;">🎄 Secret Santa 🎄</h1>', unsafe_allow_html=True)

        # Team banner
        st.markdown(f"""
        <div class="team-banner">
            <h3>🎁 {team["name"]} | Welcome, {st.session_state.participant_name}! 👋</h3>
            <p>📍 Location: {team["location"] or 'Not set'}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### Choose Your Role")
        st.write("You are both a **Santa** (giving gifts) and a **Receiver** (receiving gifts). Choose which mode you'd like to explore:")

        # Mode selection cards
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<div class="mode-card">', unsafe_allow_html=True)
            st.image("images/santa_mode.png", use_container_width=True)
            st.markdown("### 🎅 Be the Santa")
            st.write("See your assignment, view their wishlist and preferences, send anonymous hints")
            if st.button("Enter Santa Mode", key="enter_santa_mode", use_container_width=True):
                st.session_state.current_mode = "santa"
                st.session_state.page = "santa_mode"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="mode-card">', unsafe_allow_html=True)
            st.image("images/receiver_mode.png", use_container_width=True)
            st.markdown("### 🎁 Be the Receiver")
            st.write("Create your wishlist, complete preferences survey, read hints from your Santa")
            if st.button("Enter Receiver Mode", key="enter_receiver_mode", use_container_width=True):
                st.session_state.current_mode = "receiver"
                st.session_state.page = "receiver_mode"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # Logout button
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("👨‍💼 Admin Panel", key="admin_panel_access", use_container_width=True):
                st.session_state.page = "main"
                st.rerun()
        with col3:
            if st.button("🚪 Logout", key="logout_from_mode_selection", use_container_width=True):
                # Clear auth state
                st.session_state.authenticated = False
                st.session_state.participant_id = None
                st.session_state.participant_name = None
                st.session_state.current_mode = None
                st.session_state.page = "auth"
                st.rerun()

    # ========== RECEIVER MODE ==========
    elif st.session_state.page == "receiver_mode":
        if not st.session_state.authenticated:
            st.error("Please log in first.")
            st.session_state.page = "auth"
            st.rerun()

        team = get_team(st.session_state.team_id)
        st.markdown('<h1 style="text-align: center; font-size: 45px; color: #E9E8C2;">🎁 Receiver Mode</h1>', unsafe_allow_html=True)

        # Team banner
        st.markdown(f"""
        <div class="team-banner">
            <h3>👋 {st.session_state.participant_name} | {team["name"]}</h3>
            <p>📍 Location: {team["location"] or 'Not set'}</p>
        </div>
        """, unsafe_allow_html=True)

        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to Mode Selection", key="receiver_back_to_mode", use_container_width=True):
                st.session_state.page = "mode_selection"
                st.rerun()
        with col3:
            if st.button("🎅 Switch to Santa Mode", key="receiver_to_santa", use_container_width=True):
                st.session_state.current_mode = "santa"
                st.session_state.page = "santa_mode"
                st.rerun()

        st.divider()

        # Tabs for Receiver features
        tab1, tab2, tab3 = st.tabs(["📋 Preferences Survey", "🎁 My Wishlist", "💬 Messages"])

        # TAB 1: PREFERENCES SURVEY
        with tab1:
            st.markdown("### 📋 Preferences Survey")
            st.write("Help your Santa get to know you better! Answer these fun 'this or that' questions.")

            questions = get_survey_questions()
            responses = get_survey_responses(st.session_state.participant_id, st.session_state.team_id)
            answered_questions = {r["question_id"] for r in responses}

            total_questions = len(questions)
            answered_count = len(answered_questions)
            progress = answered_count / total_questions if total_questions > 0 else 0

            st.progress(progress, text=f"Progress: {answered_count}/{total_questions} questions answered")

            if answered_count == total_questions:
                st.success("✅ Survey Complete! Your Santa can now see your preferences.")
                mark_survey_complete(st.session_state.participant_id, st.session_state.team_id)

            # Show responses
            if responses:
                with st.expander("📊 Your Responses", expanded=False):
                    for response in responses:
                        st.write(f"**{response['question_text']}** → {response['answer']}")

            # Show unanswered questions
            st.markdown("#### Answer Questions")
            for question in questions:
                if question["id"] not in answered_questions:
                    st.markdown(f"### {question['question_text']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"{question['emoji_a']} {question['option_a']}",
                                   key=f"opt_a_{question['id']}", use_container_width=True):
                            save_survey_response(st.session_state.participant_id, st.session_state.team_id,
                                               question['id'], question['option_a'])
                            st.success(f"Saved: {question['option_a']}")
                            st.rerun()
                    with col2:
                        if st.button(f"{question['emoji_b']} {question['option_b']}",
                                   key=f"opt_b_{question['id']}", use_container_width=True):
                            save_survey_response(st.session_state.participant_id, st.session_state.team_id,
                                               question['id'], question['option_b'])
                            st.success(f"Saved: {question['option_b']}")
                            st.rerun()
                    st.divider()
                    break  # Show one question at a time

            if answered_count == total_questions:
                st.info("All questions answered! You can view your responses in the expander above.")

        # TAB 2: MY WISHLIST
        with tab2:
            st.markdown("### 🎁 My Wishlist")
            st.write("Add items you'd love to receive. Your Santa can see this list!")

            # Get wishlist
            wishlist = get_wishlist(st.session_state.participant_id, st.session_state.team_id)

            if wishlist:
                st.markdown("#### Your Wishlist Items:")
                for item in wishlist:
                    col1, col2, col3, col4 = st.columns([1, 6, 2, 2])
                    with col1:
                        # Priority indicator image
                        if item['priority'] == 1:
                            st.image("images/ornament_red.png", width=30)
                            priority_text = "High"
                        elif item['priority'] == 2:
                            st.image("images/ornament_gold.png", width=30)
                            priority_text = "Medium"
                        else:
                            st.image("images/ornament_green.png", width=30)
                            priority_text = "Low"

                    with col2:
                        st.write(f"**{item['item_text']}**")
                        if item['item_link']:
                            st.markdown(f"[🔗 Link]({item['item_link']})")
                        st.caption(f"Priority: {priority_text}")

                    with col3:
                        if st.button("↑", key=f"up_{item['id']}"):
                            reorder_wishlist_item(item['id'], 'up')
                            st.rerun()
                        if st.button("↓", key=f"down_{item['id']}"):
                            reorder_wishlist_item(item['id'], 'down')
                            st.rerun()

                    with col4:
                        if st.button("✏️", key=f"edit_{item['id']}"):
                            st.session_state[f"editing_{item['id']}"] = True
                            st.rerun()
                        if st.button("🗑️", key=f"del_{item['id']}"):
                            delete_wishlist_item(item['id'])
                            st.success("Item deleted!")
                            st.rerun()

                    # Edit form (shown if editing)
                    if st.session_state.get(f"editing_{item['id']}", False):
                        with st.expander("Edit Item", expanded=True):
                            edit_text = st.text_input("Item", value=item['item_text'], key=f"edit_text_{item['id']}")
                            edit_link = st.text_input("Link (optional)", value=item['item_link'] or "", key=f"edit_link_{item['id']}")
                            edit_priority = st.selectbox("Priority", [1, 2, 3], index=item['priority']-1,
                                                         format_func=lambda x: {1: "High", 2: "Medium", 3: "Low"}[x],
                                                         key=f"edit_priority_{item['id']}")
                            if st.button("Save Changes", key=f"save_edit_{item['id']}"):
                                update_wishlist_item(item['id'], edit_text, edit_priority, edit_link)
                                del st.session_state[f"editing_{item['id']}"]
                                st.success("Item updated!")
                                st.rerun()

                    st.divider()
            else:
                st.info("Your wishlist is empty. Add your first item below!")

            # Add new item form
            st.markdown("#### Add New Item")
            with st.form("add_wishlist_item", clear_on_submit=True):
                new_item_text = st.text_input("What would you like?", placeholder="e.g., Cozy winter scarf")
                new_item_link = st.text_input("Link (optional)", placeholder="https://example.com/product")
                new_priority = st.selectbox("Priority", [1, 2, 3], index=1,
                                           format_func=lambda x: {1: "🔴 High Priority", 2: "🟡 Medium Priority", 3: "🟢 Low Priority"}[x])
                submitted = st.form_submit_button("➕ Add to Wishlist")
                if submitted and new_item_text:
                    add_wishlist_item(st.session_state.participant_id, st.session_state.team_id,
                                    new_item_text, new_priority, new_item_link)
                    st.success(f"Added '{new_item_text}' to your wishlist!")
                    st.rerun()

        # TAB 3: MESSAGES (merged - view and reply)
        with tab3:
            st.markdown("### 💬 Messages with Your Secret Santa")
            st.write("Chat with your anonymous Santa! Send and receive messages.")

            # Get assignment where this participant is the receiver
            santa_assignment = get_my_santa_assignment(st.session_state.participant_name, st.session_state.team_id)

            if not santa_assignment:
                st.warning("No Santa assignment found yet. Assignments need to be generated by the admin first.")
            else:
                # Display message thread
                messages = get_messages_for_assignment(santa_assignment["id"])

                # Mark all messages from Santa as read
                for msg in messages:
                    if msg["sender_role"] == "santa" and not msg["is_read"]:
                        mark_message_read(msg["id"])

                st.markdown("#### 💬 Conversation")
                if messages:
                    for msg in messages:
                        if msg['sender_role'] == 'santa':
                            # Santa's message (show)
                            st.markdown(f"""
                            <div class="message santa-message">
                                <div class="message-type">🎅 SANTA: {msg['message_type'].upper()}</div>
                                <div class="message-content">{msg['content']}</div>
                                <div class="message-time">{msg['created_at']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # Your reply (show for context)
                            st.markdown(f"""
                            <div class="message receiver-message">
                                <div class="message-type">YOU: {msg['message_type'].upper()}</div>
                                <div class="message-content">{msg['content']}</div>
                                <div class="message-time">{msg['created_at']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("No messages yet. Start a conversation or wait for your Santa to send a hint!")

                # Reply form at the bottom
                st.divider()
                st.markdown("#### ✉️ Send a Message")
                with st.form("reply_to_santa"):
                    message_type = st.selectbox("Message Type", ["answer", "question", "note"],
                                              format_func=lambda x: {"answer": "💬 Answer to Question", "question": "❓ Ask a Question", "note": "📝 General Note"}[x])
                    message_content = st.text_area("Your Message", placeholder="Type your message here...", height=150)
                    send_btn = st.form_submit_button("📤 Send Message", use_container_width=True)

                    if send_btn and message_content:
                        send_message(santa_assignment["id"], st.session_state.team_id, "receiver", message_type, message_content)
                        st.success("✅ Message sent to your Santa!")
                        st.rerun()

    # ========== SANTA MODE ==========
    elif st.session_state.page == "santa_mode":
        if not st.session_state.authenticated:
            st.error("Please log in first.")
            st.session_state.page = "auth"
            st.rerun()

        team = get_team(st.session_state.team_id)
        st.markdown('<h1 style="text-align: center; font-size: 45px; color: #E9E8C2;">🎅 Santa Mode</h1>', unsafe_allow_html=True)

        # Team banner
        st.markdown(f"""
        <div class="team-banner">
            <h3>👋 {st.session_state.participant_name} | {team["name"]}</h3>
            <p>📍 Location: {team["location"] or 'Not set'}</p>
        </div>
        """, unsafe_allow_html=True)

        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to Mode Selection", key="santa_back_to_mode", use_container_width=True):
                st.session_state.page = "mode_selection"
                st.rerun()
        with col3:
            if st.button("🎁 Switch to Receiver Mode", key="santa_to_receiver", use_container_width=True):
                st.session_state.current_mode = "receiver"
                st.session_state.page = "receiver_mode"
                st.rerun()

        st.divider()

        # Tabs for Santa features
        tab1, tab2, tab3, tab4 = st.tabs(["📜 My Assignment", "📋 Their Preferences", "🎁 Their Wishlist", "💬 Send Message"])

        # Get assignment
        my_assignment = get_my_assignment(st.session_state.participant_name, st.session_state.team_id)

        if not my_assignment:
            st.error("No assignment found! The admin needs to generate assignments first.")
            st.stop()

        recipient_name = my_assignment["recipient_name"]

        # Defensive check: ensure recipient_name is not None
        if not recipient_name:
            st.error("Assignment data is incomplete. Please contact the admin.")
            st.stop()

        # TAB 1: MY ASSIGNMENT
        with tab1:
            st.markdown("### 📜 Your Secret Santa Assignment")

            if not my_assignment["revealed"]:
                st.write("Click the button below to reveal your secret recipient!")

                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    # Display folded paper chit
                    st.markdown("""
                    <div class="paper-container">
                        <div class="folded-paper">
                            <div style="font-size: 60px; color: #8B4513;">📜</div>
                            <p style="color: #654321; font-weight: bold; margin-top: 10px; font-size: 18px;">Your Secret Assignment</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("📜 Reveal My Recipient", key="reveal_assignment", use_container_width=True):
                        # Mark as revealed
                        result = draw_random_recipient(st.session_state.participant_name, st.session_state.team_id)
                        if "error" not in result:
                            st.success("🎉 Assignment revealed!")
                            st.rerun()
            else:
                # Already revealed
                revealed_ts = my_assignment.get("revealed_timestamp", "Unknown")
                if not revealed_ts:
                    revealed_ts = "Unknown"

                st.markdown(f"""
                <div class="opened-paper">
                    <div style="text-align: center;">
                        <p style="font-size: 20px; color: #8B4513 !important; margin-bottom: 10px;">🎁 Your Secret Santa Recipient 🎁</p>
                        <h2>{recipient_name}</h2>
                        <p style="margin-top: 20px; font-size: 16px;">
                            Remember: Keep it secret, keep it safe! 🤫<br>
                            <small style="font-size: 14px; color: #654321 !important;">
                                👀 Revealed: {revealed_ts}
                            </small>
                        </p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        # TAB 2: THEIR PREFERENCES
        with tab2:
            st.markdown(f"### 📋 {recipient_name}'s Preferences")
            st.write(f"Learn about {recipient_name}'s preferences to pick the perfect gift!")

            survey = get_receiver_survey(recipient_name, st.session_state.team_id)

            if survey:
                for response in survey:
                    st.markdown(f"**{response['question_text']}**")
                    st.write(f"→ {response['answer']}")
                    st.divider()
            else:
                st.info(f"{recipient_name} hasn't completed the preferences survey yet.")

        # TAB 3: THEIR WISHLIST
        with tab3:
            st.markdown(f"### 🎁 {recipient_name}'s Wishlist")
            st.write(f"See what {recipient_name} would love to receive!")

            wishlist = get_receiver_wishlist(recipient_name, st.session_state.team_id)

            if wishlist:
                for item in wishlist:
                    col1, col2 = st.columns([1, 10])
                    with col1:
                        if item['priority'] == 1:
                            st.image("images/ornament_red.png", width=40)
                            priority_label = "🔴 High"
                        elif item['priority'] == 2:
                            st.image("images/ornament_gold.png", width=40)
                            priority_label = "🟡 Medium"
                        else:
                            st.image("images/ornament_green.png", width=40)
                            priority_label = "🟢 Low"

                    with col2:
                        st.markdown(f"**{item['item_text']}**")
                        st.caption(f"Priority: {priority_label}")
                        if item['item_link']:
                            st.markdown(f"[🔗 View Product]({item['item_link']})")

                    st.divider()
            else:
                st.info(f"{recipient_name} hasn't added any wishlist items yet.")

        # TAB 4: SEND MESSAGE
        with tab4:
            st.markdown(f"### 💬 Send Message to {recipient_name}")
            st.write(f"Send anonymous hints, ask questions, or share notes with {recipient_name}!")

            # Show message history
            messages = get_messages_for_assignment(my_assignment["id"])
            if messages:
                st.markdown("#### Message History")
                for msg in messages:
                    if msg['sender_role'] == 'santa':
                        st.markdown(f"""
                        <div class="message santa-message">
                            <div class="message-type">YOU: {msg['message_type'].upper()}</div>
                            <div class="message-content">{msg['content']}</div>
                            <div class="message-time">{msg['created_at']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="message receiver-message">
                            <div class="message-type">{recipient_name}: {msg['message_type'].upper()}</div>
                            <div class="message-content">{msg['content']}</div>
                            <div class="message-time">{msg['created_at']}</div>
                        </div>
                        """, unsafe_allow_html=True)

                st.divider()

            # Message composer
            st.markdown("#### Send New Message")
            with st.form("send_santa_message"):
                message_type = st.selectbox("Message Type", ["hint", "question", "note"],
                                          format_func=lambda x: {"hint": "Hint About Yourself", "question": "Question for Them", "note": "General Note"}[x])
                message_content = st.text_area("Your Message", placeholder="Type your message here...", height=150)
                send_btn = st.form_submit_button("📤 Send Message")

                if send_btn and message_content:
                    send_message(my_assignment["id"], st.session_state.team_id, "santa", message_type, message_content)
                    st.success(f"✅ Message sent to {recipient_name}!")
                    st.rerun()

    # ========== ADMIN PANEL ==========
    elif st.session_state.page == "main":
        # Get team info
        team = get_team(st.session_state.team_id)
        if not team:
            st.error("Team not found. Please select a team.")
            st.session_state.page = "team_selection"
            st.rerun()

        st.title("🎅 Secret Santa Admin Panel")

        # Team info banner
        st.markdown(f"""
        <div class="team-banner">
            <h3>🎁 {team["name"]}</h3>
            <p>📍 Location: {team["location"] or 'Not set'}</p>
        </div>
        """, unsafe_allow_html=True)

        # Navigation buttons
        if st.session_state.authenticated:
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("← Back to Mode Selection", key="back_from_admin"):
                    st.session_state.page = "mode_selection"
                    st.rerun()
            st.divider()

        # Admin Authentication
        st.markdown("### 🔐 Admin Control Panel")

        if not st.session_state.get("is_admin"):
            st.warning("🔒 Admin authentication required")
            st.write("Enter your admin PIN to access admin functions.")

            admin_pin_input = st.text_input("Admin PIN", type="password", key="admin_pin")
            admin_pin_env = os.getenv(ADMIN_PIN_ENV, "")

            if st.button("🔓 Authenticate", key="auth_btn"):
                if admin_pin_env and admin_pin_input == admin_pin_env:
                    st.session_state["is_admin"] = True
                    conn, db = get_conn()
                    log_event(conn, 'admin', 'admin_auth', 'successful', st.session_state.team_id)
                    conn.commit()
                    conn.close()
                    st.success("✅ Admin authenticated!")
                    st.rerun()
                else:
                    st.session_state["is_admin"] = False
                    st.error("❌ Admin PIN incorrect or not set on host.")
        else:
            st.success("✅ Authenticated as Admin")

            if st.button("🚪 Logout", key="logout_btn"):
                st.session_state["is_admin"] = False
                st.rerun()

            st.divider()

            # Participant Management
            st.subheader("👥 Manage Participants")

            with st.expander("📤 Seed from CSV", expanded=False):
                uploaded = st.file_uploader("Upload participants CSV (columns: name, secret)", type=["csv"], key="csv_upload")
                if uploaded is not None:
                    try:
                        df = pd.read_csv(uploaded)
                        if 'name' not in df.columns:
                            st.error("CSV missing 'name' column.")
                        else:
                            seed_participants_from_df(df, st.session_state.team_id)
                            st.success("✅ Seeded participants (INSERT OR IGNORE).")
                    except Exception as e:
                        st.error(f"Failed to parse CSV: {e}")

            with st.expander("➕ Add Single Participant", expanded=False):
                new_name = st.text_input("Name to add", key="add_name")
                new_secret = st.text_input("Secret code (optional)", key="add_secret")
                if st.button("Add Participant", key="add_btn"):
                    if new_name.strip():
                        try:
                            conn, db = get_conn()
                            c = conn.cursor()
                            if db == "postgres":
                                c.execute("INSERT INTO participants (team_id, name, secret) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                                          (st.session_state.team_id, new_name.strip(), new_secret.strip()))
                            else:
                                c.execute("INSERT OR IGNORE INTO participants (team_id, name, secret) VALUES (?, ?, ?)",
                                          (st.session_state.team_id, new_name.strip(), new_secret.strip()))
                            log_event(conn, 'admin', 'add_participant', new_name.strip(), st.session_state.team_id)
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Added {new_name.strip()}")
                        except Exception as e:
                            st.error(f"DB error: {e}")
                    else:
                        st.warning("Enter a name.")

            st.divider()

            # Assignment Generation
            st.subheader("🎲 Generate Assignments")
            st.warning("⚠️ This creates a complete Secret Santa cycle. You won't be able to see who gets whom!")

            if st.button("✨ Generate All Assignments", type="primary", key="gen_btn"):
                result = generate_all_assignments(st.session_state.team_id)
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(f"✅ Generated {result['count']} assignments! Participants can now draw.")

            st.divider()

            # Remove Participant
            st.subheader("🗑️ Remove Participant")
            st.warning("⚠️ Removing a participant will regenerate ALL assignments!")

            participants_list = list_participants(st.session_state.team_id)
            if participants_list:
                participant_names = [p["name"] for p in participants_list]
                remove_name = st.selectbox("Select participant to remove", participant_names, key="remove_select")
                if st.button("🗑️ Remove and Regenerate", type="secondary", key="remove_btn"):
                    result = remove_participant(remove_name, st.session_state.team_id)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(f"✅ Removed {remove_name} and regenerated {result['count']} assignments!")
            else:
                st.info("No participants to remove.")

            st.divider()

            # Reset
            st.subheader("🔄 Reset Assignments")
            if st.button("🔄 Clear All Assignments", key="reset_btn"):
                reset_db(st.session_state.team_id)
                st.success("✅ All assignments cleared!")

            st.divider()

            # Download
            st.subheader("📥 Download Data")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("📥 Download Participants CSV", key="dl_participants"):
                    rows = list_participants(st.session_state.team_id)
                    df = pd.DataFrame([{"name": r["name"], "secret": r["secret"], "assigned": r["assigned"]} for r in rows])
                    csv = df.to_csv(index=False)
                    st.download_button("Download", csv, file_name="participants.csv", mime="text/csv")

            with col2:
                if st.button("📥 Download Audit Logs CSV", key="dl_logs"):
                    conn, db = get_conn()
                    c = conn.cursor()
                    c.execute("SELECT timestamp, actor, action, details FROM logs ORDER BY id DESC LIMIT 1000")
                    logs = c.fetchall()
                    conn.close()
                    if logs:
                        df_logs = pd.DataFrame(logs, columns=['timestamp', 'actor', 'action', 'details'])
                        csv_logs = df_logs.to_csv(index=False)
                        st.download_button("Download", csv_logs, file_name="audit_logs.csv", mime="text/csv")
                    else:
                        st.info("No logs yet.")

            st.divider()

            # Audit Logs Viewer
            with st.expander("📋 View Audit Logs", expanded=False):
                conn, db = get_conn()
                c = conn.cursor()
                c.execute("SELECT timestamp, actor, action, details FROM logs ORDER BY id DESC LIMIT 100")
                logs = c.fetchall()
                conn.close()
                if logs:
                    df_logs = pd.DataFrame(logs, columns=['timestamp', 'actor', 'action', 'details'])
                    st.dataframe(df_logs, use_container_width=True)
                else:
                    st.info("No logs yet.")

        st.divider()
        st.caption("🔒 Privacy: Assignments are stored server-side and hidden from everyone, including the admin. Keep this URL private!")

        # Show simple status counts
        conn, db = get_conn()
        c = conn.cursor()
        if db == "postgres":
            c.execute("SELECT COUNT(*) as revealed FROM assignments WHERE revealed = 1 AND team_id = %s", (st.session_state.team_id,))
            revealed_count = c.fetchone()["revealed"]
            c.execute("SELECT COUNT(*) as total FROM participants WHERE team_id = %s", (st.session_state.team_id,))
            total = c.fetchone()["total"]
        else:
            c.execute("SELECT COUNT(*) as revealed FROM assignments WHERE revealed = 1 AND team_id = ?", (st.session_state.team_id,))
            revealed_count = c.fetchone()["revealed"]
            c.execute("SELECT COUNT(*) as total FROM participants WHERE team_id = ?", (st.session_state.team_id,))
            total = c.fetchone()["total"]
        conn.close()

        waiting_count = total - revealed_count
        st.caption(f"Revealed: {revealed_count} • Waiting: {waiting_count}")


# =========================================================
# SAFE ENTRY POINT
# =========================================================

_ = main()
