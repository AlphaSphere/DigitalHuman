FROM node:24-slim

WORKDIR /app

COPY Frontend/package*.json ./
RUN npm ci

COPY Frontend ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
