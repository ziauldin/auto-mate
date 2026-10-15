# app/migrate_add_car_image.py

import asyncio
from sqlalchemy import text
from database import engine

async def add_car_image_column():
    async with engine.begin() as conn:
        try:
            # Check if column already exists
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='messages' AND column_name='car_image'
            """))
            if result.first():
                print("✅ Column 'car_image' already exists in 'messages'.")
                return

            # Add the column
            await conn.execute(text("ALTER TABLE messages ADD COLUMN car_image VARCHAR;"))
            print("✅ Column 'car_image' added to 'messages' table.")

        except Exception as e:
            print(f"❌ Failed to add column: {e}")

if __name__ == "__main__":
    asyncio.run(add_car_image_column())
