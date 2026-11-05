FROM node:20-alpine AS build
WORKDIR /app
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL \
    DISABLE_EMERGENT_OVERLAY=true \
    GENERATE_SOURCEMAP=false
COPY package.json yarn.lock ./
# Hapus paket khusus lingkungan pengembangan Emergent agar build 100% mandiri
RUN node -e "const f='package.json';const p=require('./'+f);for(const k of Object.keys(p.devDependencies||{})){if(k.startsWith('@emergentbase/'))delete p.devDependencies[k]}require('fs').writeFileSync(f,JSON.stringify(p,null,2))" \
 && yarn install --network-timeout 600000
COPY . .
# index.html produksi tanpa skrip/analitik lingkungan pengembangan
RUN cp public/index.prod.html public/index.html
RUN yarn build:prod

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
