# MedAssist AI — container for Hugging Face Spaces (port 7860) or Render (sets $PORT).
FROM python:3.11-slim

# Hugging Face Spaces runs containers as user id 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 PORT=7860 \
    MEDASSIST_DB=/home/user/app/medassist.db TZ=Asia/Kolkata
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .
EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
