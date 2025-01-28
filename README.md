# ChemBandit

To deploy

```bash
modal deploy main.py
```

When the deployment is successful, you get something like

```text
https://handle-tmp-workspace--chembandit-poe-fastapi-app.modal.run
```

You should be able to access the URL, and the page should contain text like

```text
FastAPI Poe bot server

Congratulations! Your server is running. To connect it to Poe, create a bot at https://poe.com/create_bot?server=1.
```

Copy the url to a new bot like https://poe.com/create_bot?server=1
