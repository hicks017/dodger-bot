# Define the source Docker image and set working directory for bot files
FROM python:3.12-slim
WORKDIR /usr/src/app

# Install the bot dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the source code and run the bot
COPY . .
CMD [ "python", "./bot.py" ]
