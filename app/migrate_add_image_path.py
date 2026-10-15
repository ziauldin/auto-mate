import asyncio
from sqlalchemy import text
from database import engine

async def add_image_path_column():
    async with engine.begin() as conn:
        try:
            # Check if column already exists
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='chat_sessions' AND column_name='image_path'
            """))
            if result.first():
                print("✅ Column 'image_path' already exists.")
                return

            # Add column
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN image_path VARCHAR;"))
            print("✅ Column 'image_path' added to 'chat_sessions' table.")

        except Exception as e:
            print(f"❌ Failed to add column: {e}")

if __name__ == "__main__":
    asyncio.run(add_image_path_column())
