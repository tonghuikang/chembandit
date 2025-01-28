# TODO - write script to update settings

"""
modal deploy main.py

modal app stop chembandit-poe && modal deploy main.py
"""

from __future__ import annotations
import os

import fastapi_poe as fp
from modal import App, Image, asgi_app

from bot_ChemBandit import JapaneseKanaBot

# NOTE: this key is here to ensure that messages actually come from Poe servers
POE_ACCESS_KEY = "A"*32

REQUIREMENTS = [
    "fastapi-poe==0.0.48", 
    "openai==1.54.4",  # WrapperBotDemo, ResumeReview
    "pandas",  # which version?
    "requests==2.31.0",  # PromotedAnswerBot, ResumeReview
    "beautifulsoup4==4.10.0",  # PromotedAnswerBot
    "pdftotext==2.2.2",  # ResumeReview
    "Pillow==9.5.0",  # ResumeReview
    "pytesseract==0.3.10",  # ResumeReview
    "python-docx",  # ResumeReview
    "tiktoken",  # tiktoken
    "trino",  # RunTrinoQuery, TrinoAgent
]
image = (
    Image.debian_slim()
    .apt_install(
        "ca-certificates",
        "fonts-liberation",
        "libasound2",
        "libatk-bridge2.0-0",
        "libatk1.0-0",
        "libc6",
        "libcairo2",
        "libcups2",
        "libdbus-1-3",
        "libexpat1",
        "libfontconfig1",
        "libgbm1",
        "libgcc1",
        "libglib2.0-0",
        "libgtk-3-0",
        "libnspr4",
        "libnss3",
        "libpango-1.0-0",
        "libpangocairo-1.0-0",
        "libstdc++6",
        "libx11-6",
        "libx11-xcb1",
        "libxcb1",
        "libxcomposite1",
        "libxcursor1",
        "libxdamage1",
        "libxext6",
        "libxfixes3",
        "libxi6",
        "libxrandr2",
        "libxrender1",
        "libxss1",
        "libxtst6",
        "lsb-release",
        "wget",
        "xdg-utils",
        "curl",
    )  # mermaid requirements
    .run_commands("curl -sL https://deb.nodesource.com/setup_18.x | bash -")
    .apt_install("nodejs")
    .run_commands("npm install -g @mermaid-js/mermaid-cli")
    .apt_install(
        "libpoppler-cpp-dev",
        "tesseract-ocr-eng",
    )  # document processing
    .pip_install(*REQUIREMENTS)
    .env(
        {
            "POE_ACCESS_KEY": POE_ACCESS_KEY,
        }
    )
    .copy_local_file("japanese_kana.csv", "/root/japanese_kana.csv")  # JapaneseKana
)
app = App("chembandit-poe")


@app.function(image=image, container_idle_timeout=1200)
@asgi_app()
def fastapi_app():
    # see https://creator.poe.com/docs/quick-start#configuring-the-access-credentials
    app = fp.make_app(JapaneseKanaBot(), access_key=POE_ACCESS_KEY)

    # If you want to deploy multiple bot at the same time
    # app = fp.make_app(
    #     [
    #         JapaneseKanaBot(path="/JapaneseKana", access_key=POE_ACCESS_KEY),
    #     ],
    # )
    return app