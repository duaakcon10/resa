FROM node:20-alpine
WORKDIR /app
# tesseract optional for OCR captcha; mbbank default uses WASM model
RUN apk add --no-cache wget
COPY package.json package-lock.json* ./
RUN npm install --omit=dev
COPY mbbank-service.js ./
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/health || exit 1
CMD ["node", "mbbank-service.js"]
