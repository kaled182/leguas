FROM node:20-slim

RUN apt-get update && apt-get install -y \
    chromium \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    wget \
    curl \
    git \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    CHROME_BIN=/usr/bin/chromium

WORKDIR /wppserver

COPY deploy/dev/wppconnect/patch.js /tmp/wppconnect-patch.js

RUN git config --global http.sslVerify false \
    && git clone --depth=1 --branch main https://github.com/wppconnect-team/wppconnect-server.git . \
    && npm install --legacy-peer-deps \
    && npm run build \
    && node /tmp/wppconnect-patch.js

EXPOSE 21465

CMD ["node", "dist/server.js"]
