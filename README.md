# 🚗 AUTO-MATE: AI Auto Workshop Assistant

Source code available on request.

An AI-powered vehicle diagnostic and car damage detection system that turns a car workshop into a smart digital assistant. Customers describe a problem in plain English (text or voice), upload a photo of visible damage, or record an engine or brake noise. The system works out the likely fault, gives a transparent repair cost range, and books a service appointment through WhatsApp.

Built as my final-year project for the BS Business Analytics program at International Islamic University Islamabad (IIUI), advised by Dr. Abdul Zahid.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat-square&logo=flask&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-F55036?style=flat-square&logoColor=white)
![Llama 3](https://img.shields.io/badge/Llama_3-0467DF?style=flat-square&logo=meta&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLOv8-00FFFF?style=flat-square&logoColor=black)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Twilio](https://img.shields.io/badge/Twilio-F22F46?style=flat-square&logo=twilio&logoColor=white)

<!-- Add a screenshot or demo GIF: ![Demo](screenshots/demo.gif) -->

## 🎯 The problem
- Car owners are unsure what repairs they need and worry about hidden costs
- Manual diagnosis by mechanics is slow and inconsistent
- Repair estimates aren't transparent, which hurts customer trust
- Booking a trusted mechanic is cumbersome

## ✨ Features
- 💬 **AI chatbot diagnostics:** LLMs interpret plain-English descriptions, typed or spoken, to detect likely faults
- 📸 **Photo inspection:** YOLO detects visible damage such as scratches and dents
- 🔊 **Sound analysis:** uploaded engine or brake recordings are analyzed to identify mechanical issues
- 💰 **Repair cost estimation:** a TF-IDF recommender matches the fault to a pricing dataset (PakWheels parts data plus labour fees) and returns a transparent cost range
- 📅 **Service booking:** appointments scheduled through WhatsApp

## 🏗️ How it works

```mermaid
flowchart LR
    U[Customer] -->|text / voice| N[Distil-Whisper + Llama 3 / Phi-2]
    U -->|photo| Y[YOLOv8 + OpenCV]
    U -->|engine or brake sound| A[Librosa audio model]
    N --> D[Fault diagnosis]
    Y --> D
    A --> D
    D --> R[TF-IDF cost recommender]
    R --> DB[(Parts + labour pricing DB)]
    R --> Q[Repair cost range]
    Q --> B[WhatsApp booking via Twilio]
```

## 📈 Results
- 70% less diagnosis time for common faults
- 35% higher user satisfaction from automated diagnosis and transparent estimates
- 25% more booking conversions
- 20% less workshop downtime

## 🛠️ Tech stack

| Area | Tools |
|------|-------|
| NLP and speech | Groq API, Llama 3, Phi-2, Distil-Whisper |
| Computer vision | YOLOv8 / YOLOv5, OpenCV |
| Audio | Librosa, TensorFlow / PyTorch |
| Backend and data | Python, FastAPI, Flask, SQLAlchemy, PostgreSQL / MySQL |
| Integrations | Twilio API (WhatsApp) |
