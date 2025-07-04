
# dodger-bot
Obtains information on the top 3 batters for the Dodgers in the last 10 days when a new series begins.

Ensure you have a `.env` file containing the following variables:
- DISCORD_TOKEN:
- CHANNEL_ID:
- (Optional) ADMIN_CHANNEL_ID:

---

## Running in Production (Docker)

To build and run the production container:

```sh
docker build -t dodger-bot .
docker run --env-file .env dodger-bot
```

---

## Running in Development (VS Code Dev Container)

1. Make sure you have the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) installed in VS Code.
2. Open the project folder in VS Code.
3. When prompted, reopen in the dev container, or use the Command Palette:
   - `Dev Containers: Reopen in Container`
4. The development environment will have Python, git, and other tools pre-installed. You can run, edit, and version control your code inside the container.

Alternatively, to build and run the dev container manually:

```sh
docker build -f Dockerfile.dev -t dodger-bot-dev .
docker run -it --env-file .env -v ${PWD}:/workspace dodger-bot-dev
```

---
