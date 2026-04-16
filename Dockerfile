FROM node:20

WORKDIR /app

COPY . .

RUN npm install

RUN chmod +x entrypoint.sh

CMD ["sh", "entrypoint.sh"]
