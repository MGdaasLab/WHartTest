ARG NODE_BASE_IMAGE=node:22-alpine
FROM ${NODE_BASE_IMAGE}

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmjs.org

COPY package.json ./
RUN npm config set registry "${NPM_REGISTRY}" && npm install

COPY . ./

EXPOSE 3001

CMD ["npm", "run", "start"]
