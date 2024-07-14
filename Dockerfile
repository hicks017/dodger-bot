FROM python:3.12-slim
WORKDIR /usr/src/app

# Install the application dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the source code
COPY . .

CMD [ "python", "./bot.py" ]
