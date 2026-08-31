FROM node:20-alpine AS builder
WORKDIR /app

RUN apk add --no-cache postgresql-client openssl

COPY package*.json ./
COPY backend/package*.json backend/
COPY frontend/package*.json frontend/
RUN npm ci && npm ci --prefix backend && npm ci --prefix frontend

COPY . .
RUN cd backend && npx prisma generate
RUN npm run build

FROM node:20-alpine
WORKDIR /app

RUN apk add --no-cache postgresql-client openssl

COPY --from=builder /app/backend/dist ./backend/dist
COPY --from=builder /app/frontend/dist ./frontend/dist
COPY --from=builder /app/backend/node_modules ./backend/node_modules
COPY --from=builder /app/backend/package.json ./backend/package.json
COPY --from=builder /app/backend/prisma ./backend/prisma
COPY --from=builder /app/package.json ./package.json

ENV PRISMA_ENGINE_PROTOCOL=json

RUN cd backend && npx prisma generate

EXPOSE 5502

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["node", "backend/dist/src/index.js"]
