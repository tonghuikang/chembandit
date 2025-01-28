# ChemBandit

To deploy

```bash
modal deploy main.py
```

When the deployment is successful, you get something like

```text
https://handle-tmp-workspace--chembandit-poe-fastapi-app.modal.run
```

Add the bot handle

```text
https://handle-tmp-workspace--chembandit-poe-fastapi-app.modal.run/JapaneseKana
https://handle-tmp-workspace--chembandit-poe-fastapi-app.modal.run/KnowledgeTest
```

You should be able to access the URL, and the page should contain text like

```text
FastAPI Poe bot server

Congratulations! Your server is running. To connect it to Poe, create a bot at https://poe.com/create_bot?server=1.
```

Go to https://poe.com/create_bot?server=1 and create a server bot.

The access key will be `AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`.
This access key doesn't need to be private unless you are using your own LLM provider API keys.
