FROM node:24-alpine
MAINTAINER web-team
RUN apk add curl
WORKDIR /web
COPY package.json .
RUN npm install
CMD ["node", "server.js"]
