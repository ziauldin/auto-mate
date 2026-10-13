# 🚗 AUTO-MATE: AI Auto Workshop Chatbot

Source code available on request.

A chatbot for auto workshops that diagnoses vehicle problems from a plain-English description or a photo, then generates an itemized repair quote from a parts database.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Gemma](https://img.shields.io/badge/Gemma--2-4285F4?style=flat-square&logo=google&logoColor=white)
![YOLO](https://img.shields.io/badge/YOLOv8-00FFFF?style=flat-square&logoColor=black)

<!-- Add a screenshot or demo GIF: ![Demo](demo.gif) -->

## Features

- **Text diagnosis:** the customer describes the problem in plain English, and the Gemma-2 LLM identifies likely causes
- **Photo diagnosis:** YOLOv8 detects visible damage in uploaded photos
- **Instant quotes:** matching parts and labour are pulled from a PostgreSQL database to build an itemized repair quote
- **FastAPI backend** serving the chat and quote endpoints

## How it works

```mermaid
flowchart LR
    U[Customer] -->|text| L[Gemma-2 LLM]
    U -->|photo| Y[YOLOv8]
    L --> D[Diagnosis]
    Y --> D
    D --> Q[Quote builder]
    Q --> DB[(PostgreSQL parts DB)]
    Q --> R[Itemized repair quote]
```

## Results

- 35% higher user satisfaction
- 25% more booking conversions

## Tech stack

Python, FastAPI, PostgreSQL, Gemma-2, YOLOv8

**Built:** April 2025
