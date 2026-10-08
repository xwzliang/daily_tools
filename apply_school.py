"""Fill the school visitor form, leaving final submission to the user.

Install dependency: python3 -m pip install selenium
Set APPLY_SCHOOL_NAME, APPLY_SCHOOL_PHONE, and APPLY_SCHOOL_ID_NUMBER
in ~/sync/.env.apply_school (or in your environment), then run: python3 apply_school.py --photo /path/to/photo.jpg
Keep personal values outside the Git repository.
"""

import argparse
import os
from pathlib import Path
import sys


def load_env(path):
    """Read literal KEY=VALUE settings without executing shell expressions."""
    if not path.is_file():
        return
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key.isidentifier():
            raise ValueError(f"Invalid env setting at {path}:{line_number}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path, default=Path.home() / "sync/selfie.jpg")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--env-file", type=Path,
                        default=Path.home() / "sync/.env.apply_school")
    args = parser.parse_args()
    try:
        load_env(args.env_file.expanduser())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    required = ("APPLY_SCHOOL_NAME", "APPLY_SCHOOL_PHONE", "APPLY_SCHOOL_ID_NUMBER")
    personal = {key: os.environ.get(key, "").strip() for key in required}
    missing = [key for key, value in personal.items() if not value]
    if missing:
        parser.error("Set these environment variables before running: " + ", ".join(missing))
    photo = args.photo.expanduser().resolve()
    if not photo.is_file():
        parser.error(f"Photo does not exist: {photo}. Supply --photo /path/to/photo.jpg")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException, WebDriverException
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        print("Missing Selenium. Install it with: python3 -m pip install selenium", file=sys.stderr)
        return 1

    driver = None
    step = "starting Firefox (Firefox must be installed)"
    try:
        driver = webdriver.Firefox()
        wait = WebDriverWait(driver, args.timeout)

        def clickable(by, value):
            nonlocal step
            step = f"waiting for {value}"
            return wait.until(EC.element_to_be_clickable((by, value)))

        step = "loading the application page"
        driver.get("https://qrc.dlj100.cn/visit/off/apply?schId=12223&access=1")
        name_field = clickable(By.XPATH, "//input[@placeholder='请输入真实姓名']")
        name_field.send_keys(personal["APPLY_SCHOOL_NAME"])

        identity_dropdown = clickable(By.ID, "visitor_identity")
        identity_dropdown.click()
        wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[normalize-space()='其他人员']"))
        ).click()
        clickable(By.XPATH, "//a[contains(text(),'完成')]").click()
        wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[normalize-space()='其他']"))
        ).click()
        clickable(By.XPATH, "//a[contains(text(),'完成')]").click()

        phone_field = clickable(By.ID, "phone")
        phone_field.send_keys(personal["APPLY_SCHOOL_PHONE"])

        id_field = clickable(By.XPATH, "//input[@placeholder='请输入身份证号码']")
        id_field.send_keys(personal["APPLY_SCHOOL_ID_NUMBER"])

        company_field = clickable(By.ID, "company_name")
        company_field.send_keys("外企德科")

        text_field = clickable(By.ID, "remark")
        text_field.send_keys("家属")

        clickable(By.ID, "tch").click()
        wait.until(
            EC.element_to_be_clickable((By.ID, "find_tch"))
        ).send_keys("邹")
        wait.until(
            EC.element_to_be_clickable((By.XPATH, "//input[@value='邹子建']"))
        ).click()

        step = "locating the photo upload input"
        # Selenium uploads directly, including when the input is hidden by styling.
        upload = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))
        upload.send_keys(str(photo))

        step = "confirming the photo crop"
        clickable(By.ID, "confirmBtn").click()
        step = "dismissing the photo confirmation"
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='OK']"))).click()
        print("Form filled. Review it in Firefox and submit manually if correct.")
        input("Press Enter to close Firefox after reviewing the form: ")
        return 0
    except (TimeoutException, WebDriverException) as exc:
        print(f"Failed while {step}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        return 0
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    sys.exit(main())
