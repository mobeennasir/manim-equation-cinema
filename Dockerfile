# Manim needs these system libraries + a TeX install to render text.
# They are installed in the image; nothing here is your code.
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV MANIM_USE_TEX=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config \
    libcairo2-dev libpango1.0-dev \
    ffmpeg \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra \
    texlive-fonts-recommended texlive-fonts-extra dvisvgm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Koyeb / Render / Railway all set $PORT for you. Default 8000.
EXPOSE 8000
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} --timeout 900 --workers 1 app:app
