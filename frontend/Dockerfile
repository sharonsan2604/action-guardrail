FROM node:20-slim

# Set working directory
WORKDIR /app

# Copy package descriptors first to cache dependencies build step
COPY package.json package-lock.json /app/

# Install dependencies
RUN npm install

# Copy source code
COPY . /app/

# Expose Vite dev server port
EXPOSE 8501

# Run Vite dev server bound to host interface
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "8501"]
