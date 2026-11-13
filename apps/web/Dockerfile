FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG APTURA_BACKEND_URL=http://api:8000
ENV APTURA_BACKEND_URL=${APTURA_BACKEND_URL} \
    NODE_ENV=production

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]
