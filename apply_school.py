from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyautogui
import time

# Path to your WebDriver executable
# driver_path = "/path/to/chromedriver"

# Initialize the Chrome WebDriver
# driver = webdriver.Chrome(executable_path=driver_path)
driver = webdriver.Firefox()

# Open the webpage
driver.get("https://qrc.dlj100.cn/visit/off/apply?schId=12223&access=1")

# try:
# Wait for the page to load
time.sleep(1)

# Fill in the fields (replace the element locators as per the actual HTML)

# Visitor Name (访客姓名)
name_field = driver.find_element(By.XPATH, "//input[@placeholder='请输入真实姓名']")
name_field.send_keys("张炯梁")

# Visitor Identity (访客身份) - might be a dropdown, need to click and select
identity_dropdown = driver.find_element(By.ID, "visitor_identity")
identity_dropdown.click()
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'其他人员')]"))
).click()
driver.find_element(By.XPATH, "//a[contains(text(),'完成')]").click()
time.sleep(1)
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'其他')]"))
).click()
driver.find_element(By.XPATH, "//a[contains(text(),'完成')]").click()
# You might need to choose a value from the dropdown. This depends on the available options.

phone_field = driver.find_element(By.ID, "phone")
phone_field.send_keys("18701559282")

# ID Number (身份证)
id_field = driver.find_element(By.XPATH, "//input[@placeholder='请输入身份证号码']")
id_field.send_keys("140602199208239019")

company_field = driver.find_element(By.ID, "company_name")
company_field.send_keys("外企德科")
# Car Plate (车牌号)
# car_field = driver.find_element(By.XPATH, "//input[@placeholder='请输入来访车牌号']")
# car_field.send_keys("ABC-1234")

# Visit Time (来访时间) - You may need to handle this with JavaScript if it's a date picker
# Example for inputting a date manually:
# visit_time_field = driver.find_element(
#     By.XPATH, "//input[@placeholder='2024-10-21 10:30']"
# )
# visit_time_field.send_keys("2024-10-21 10:30")

# Visitor Purpose (来访目的) - This might be a text field or dropdown
# purpose_field = driver.find_element(By.XPATH, "//input[@placeholder='请选择']")
# purpose_field.click()
# Select the appropriate option if it's a dropdown

text_field = driver.find_element(By.ID, "remark")
text_field.send_keys("家属")

driver.find_element(By.ID, "tch").click()
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "find_tch"))
).send_keys("邹")
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, "//input[@value='邹子建']"))
).click()

time.sleep(1)
photo_field = driver.find_element(By.ID, "upload")
photo_field.click()

time.sleep(2)
pyautogui.hotkey("command", "shift", "g", interval=0.25)
time.sleep(1)
photo_path = "/Users/broliang/Pictures/selfie.jpg"
pyautogui.write(photo_path)
pyautogui.press("enter")

time.sleep(1)
pyautogui.press("enter")
time.sleep(5)

WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "confirmBtn"))
).click()
time.sleep(3)
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'OK')]"))
).click()
time.sleep(2)

# Finally, submit the form
# submit_button = driver.find_element(By.XPATH, "//a[contains(text(), '预约申请')]")
# submit_button.click()
# print(submit_button)

# Wait to observe the result
# time.sleep(5)

# finally:
#     # Close the driver
# driver.quit()
