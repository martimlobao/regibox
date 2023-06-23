import datetime
import logging
import os
import re

import pytz
import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from dotenv import find_dotenv, load_dotenv

TIMEZONE: pytz.BaseTzInfo = pytz.timezone("Europe/Lisbon")
START: datetime.datetime = datetime.datetime.now(TIMEZONE)
LOGGER: logging.Logger = logging.getLogger("REGIBOX")
logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] - %(message)s",
    level=logging.DEBUG,
)
load_dotenv(dotenv_path=find_dotenv(usecwd=True))
DOMAIN: str = "https://www.regibox.pt/app/app_nova/"
HEADERS: dict[str, str] = {
    "Accept": "text/html, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,pt;q=0.8,pt-PT;q=0.7",
    "Connection": "keep-alive",
    "Cookie": os.environ["COOKIE"],
    "DNT": "1",
    "Host": "www.regibox.pt",
    "Referer": "https://www.regibox.pt/app/app_nova/index.php",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/114.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Not.A/Brand";v="8", "Chromium";v="114"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}


def get_enroll_params(timestamp: int) -> dict[str, str]:
    return {
        "valor1": str(timestamp),
        "type": "",
        "source": "mes",
        "scroll": "s",
        "z": "",
    }


def get_enroll_buttons(year: int, month: int, day: int) -> list[Tag]:
    timestamp: int = int(datetime.datetime(year, month, day, tzinfo=TIMEZONE).timestamp() * 1000)
    res: requests.models.Response = requests.get(
        f"{DOMAIN}php/aulas/aulas.php",
        params=get_enroll_params(timestamp),
        headers=HEADERS,
        timeout=10,
    )
    res.raise_for_status()
    soup: BeautifulSoup = BeautifulSoup(res.text, "html.parser")
    buttons: list[Tag] = soup.find_all("button")
    LOGGER.debug(
        "Found all buttons:\n\t{}".format(
            "\n\t".join([f"{button.decode()}" for button in buttons]),
        ),
    )
    buttons = [button for button in buttons if button.text == "INSCREVER"]
    LOGGER.debug(
        "Found enrollment buttons:\n\t{}".format(
            "\n\t".join([f"{button.decode()}" for button in buttons]),
        ),
    )
    return buttons


def pick_button(buttons: list[Tag], class_time: str, class_type: str) -> Tag:
    available_classes = []
    for button in buttons:
        button_time: Tag = button.find_parent().find_parent().find("div", attrs={"align": "left"})
        button_type: Tag = (
            button_time.find_parent()
            .find_parent()
            .find("div", attrs={"align": "left", "class": "col-50"})
            .text.strip()
        )
        available_classes.append(f"{button_type} @ {button_time.text}")
        if button_time.text.startswith(class_time) and button_type == class_type:
            LOGGER.info(f"Found button for '{button_type}' @ {button_time.text}")
            return button
    raise RuntimeError(
        f"Unable to find enroll button for class '{class_type}' at {class_time}. Available"
        f" classes are: {available_classes}"
    )


def get_enroll_path(button: Tag) -> str:
    onclick: str = button.attrs["onclick"]
    LOGGER.debug(f"Found button onclick action: '{onclick}")
    button_urls: list[str] = [
        part for part in onclick.split("'") if part.startswith("php/aulas/marca_aulas.php")
    ]
    if len(button_urls) != 1:
        raise RuntimeError(f"Expecting one page in button, found {len(button_urls)}: {onclick}")
    return button_urls[0]


def enroll(path: str) -> None:
    res: requests.models.Response = requests.get(DOMAIN + path, headers=HEADERS, timeout=10)
    res.raise_for_status()
    LOGGER.debug(f"Enrolled in class with response: '{res.text}'")
    soup = BeautifulSoup(res.text, "html.parser")
    responses: list[str] = re.findall(
        r"parent\.msg_toast_icon\s\(\"(.+)\",",
        soup.find_all("script")[-1].text,
    )
    if len(responses) != 1:
        raise RuntimeError(f"Couldn't parse response for enrollment: {res.text}")
    LOGGER.info(responses[0])


def main() -> None:
    LOGGER.info(f"Started at {START.isoformat()}")
    class_time: str = "12:00"
    class_type: str = "WOD RATO"
    class_day: datetime.datetime = datetime.datetime.now(TIMEZONE) + datetime.timedelta(days=1)
    buttons: list[Tag] = get_enroll_buttons(class_day.year, class_day.month, class_day.day)
    button: Tag = pick_button(buttons, class_time, class_type)
    path: str = get_enroll_path(button)
    enroll(path)
    LOGGER.info(f"Enrolled at {path}")
    LOGGER.info(f"Runtime: {datetime.datetime.now(TIMEZONE) - START:.3}")


if __name__ == "__main__":
    main()