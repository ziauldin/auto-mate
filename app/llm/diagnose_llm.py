import os
import re
import logging
import traceback
from typing import List, Dict
from groq import Groq
from ultralytics import YOLO
from app.models import ChatSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/diagnose_llm.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DiagnoseLLM:
    def __init__(self):
        try:
            groq_api_key = os.environ.get("GROQ_API_KEY")
            if not groq_api_key:
                logger.warning("GROQ_API_KEY not found in environment variables")

            self.client = Groq(api_key=groq_api_key)
            logger.info("Groq client initialized successfully")

            weights = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "yolov8m.pt",
            )
            self.yolo_model = YOLO(weights if os.path.exists(weights) else "yolov8m.pt")
            logger.info("YOLOv8 model loaded successfully")

            self.base_prompt = (
                "You are AutoMate, an expert automotive diagnostic assistant. "
                "Your ONLY purpose is to help diagnose and repair vehicles. "
                "Rules you MUST follow:\n"
                "1. Always remember and reference the specific vehicle being discussed\n"
                "2. Only respond to automotive-related questions\n"
                "3. Reject all other topics with: 'I specialize in automotive diagnostics only'\n"
                "4. Be technical but clear in explanations\n"
                "5. If the user asks in Roman Urdu, always respond in Roman Urdu\n"
                "6. Provide concise, numbered steps when appropriate\n"
                "7. Never use special formatting or characters (e.g., **, *, etc.)\n"
                "8. Use numbered lists (e.g., 1., 2., etc.) for bullet points\n"
                "9. When asked about the vehicle, always respond with its full details\n"
                "10. Don't give recommended products every time. Give recommendations only when asked\n"
                "11. If someone asks about who created you, say: "
                "'I am AutoMate, built by Zia Ul Din, a data analyst and AI developer at IIUI.'"
            )

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            logger.error(traceback.format_exc())
            self.client = None
            self.yolo_model = None

    def _is_roman_urdu(self, text: str) -> bool:
        return bool(re.match(r"^[a-zA-Z0-9\s]+$", text))

    def _check_zia_mention(self, msg: str) -> bool:
        keywords = ["zia", "zia ul din", "who are you", "who built you", "who created you"]
        return any(k in msg.lower() for k in keywords)

    def _analyze_image(self, image_path: str) -> str:
        try:
            if not os.path.exists(image_path):
                logger.warning(f"Image path not found: {image_path}")
                return "Image not found."

            logger.info(f"Analyzing image at: {image_path}")
            results = self.yolo_model(image_path)[0]

            if not results.boxes or len(results.boxes.cls) == 0:
                return "No visible damage detected."

            names = self.yolo_model.names
            label_counts = {}

            for cls_id in results.boxes.cls:
                label = names[int(cls_id)]
                label_counts[label] = label_counts.get(label, 0) + 1

            logger.info(f"YOLO detected labels: {label_counts}")
            return ", ".join([f"{label} (x{count})" for label, count in label_counts.items()])

        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            logger.error(traceback.format_exc())
            return "Failed to analyze image."

    async def get_diagnosis(self, messages: List[Dict[str, str]], session: ChatSession, image_path: str = None) -> str:
        try:
            if not self.client:
                return "I'm having technical difficulties. Please try again later."

            logger.info(f"Image path received in diagnosis: {image_path}")
            user_messages = [m for m in messages if m["role"] == "user"]
            last_user_msg = user_messages[-1]["content"] if user_messages else ""

            if self._check_zia_mention(last_user_msg):
                return (
                    "I am AutoMate, an expert automotive diagnostic assistant built by Zia Ul Din, "
                    "a data analyst and AI developer currently pursuing a BS in Business Analytics at IIUI..."
                )

            prompt = self.base_prompt
            if self._is_roman_urdu(last_user_msg):
                prompt += "\nEnsure all responses are in Roman Urdu."

            vehicle_info = f"{session.year} {session.manufacturer} {session.model}"
            vehicle_context = f"Current Vehicle: {vehicle_info}\nAll responses must be specific to this vehicle."

            processed_messages = [
                {"role": "system", "content": prompt},
                {"role": "system", "content": vehicle_context}
            ]
            processed_messages.extend([m for m in messages if m["role"] != "system"])

            if image_path:
                image_description = self._analyze_image(image_path)
                logger.info(f"Image Analysis: {image_description}")
                processed_messages.append({
                    "role": "user",
                    "content": f"Detected objects in the image: {image_description}"
                })

            response = self.client.chat.completions.create(
                model="gemma2-9b-it",
                messages=processed_messages,
                temperature=0.0,
                max_tokens=1024,
                top_p=0.9
            )

            reply = response.choices[0].message.content.strip()
            reply = re.sub(r"\*\*", "", reply)

            if any(q in last_user_msg.lower() for q in ["what car", "which vehicle", "my car"]):
                return f"You have a {vehicle_info}. {reply}"

            return reply

        except Exception as e:
            logger.error(f"LLM diagnosis error: {e}")
            logger.error(traceback.format_exc())
            return "Sorry, I encountered a technical or internet issue. Please try again later."
